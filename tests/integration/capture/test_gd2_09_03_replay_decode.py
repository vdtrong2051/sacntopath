"""09.03: replay from committed SQLite/RAW, then decode actual JPEG pixels."""
from __future__ import annotations

from io import BytesIO
import hashlib

import numpy as np
from PIL import Image
import pytest

from scantopath.acquisition.raw_rgbd import RawRgbdCapture
from scantopath.metadata.store import MetadataStore
from scantopath.storage.numbered import NumberedStorageRegistry
from scantopath.storage.session_store import SessionStore

from scantopath.modules.capture.application.contracts import CaptureContext
from scantopath.modules.capture.application.replay import RawReplayService
from scantopath.modules.capture.application.decoding import (
    RgbdDecodeError,
    RgbdDecoder,
)
from scantopath.modules.capture.infrastructure.raw_reader import RawReaderAdapter
from scantopath.modules.capture.infrastructure.jpeg_codec import PillowMjpegDecoder

from tests.support.raw_fixture import raw


def packet_with_jpeg(*, malformed=False):
    base = raw(
        session="t1",
        specimen="s1",
        capture_id="c1",
    )

    if malformed:
        jpeg = b"\xff\xd8fixture-is-not-decodable\xff\xd9"
    else:
        out = BytesIO()

        pixels = np.full(
            (12, 20, 3),
            (220, 10, 30),
            dtype=np.uint8,
        )

        Image.fromarray(pixels).save(
            out,
            format="JPEG",
            quality=98,
            subsampling=0,
        )

        jpeg = out.getvalue()

    meta = base.metadata.model_copy(update={
        "color": base.metadata.color.model_copy(update={
            "width": 20,
            "height": 12,
            "payload_size_bytes": len(jpeg),
        }),
        "color_intrinsics": base.metadata.color_intrinsics.model_copy(update={
            "width": 20,
            "height": 12,
        }),
    })

    return RawRgbdCapture(
        meta,
        jpeg,
        base.depth_y16_le,
    )


def seeded_store(root):
    with MetadataStore(root) as store:
        store.create_project("p1", "Project")
        store.create_specimen("s1", "p1", "Specimen")
        store.create_scan_session("t1", "s1", "Scan")


def read_decoded(root):
    context = CaptureContext(
        str(root),
        "p1",
        "s1",
        "t1",
        "c1",
    )

    raw_packet = RawReplayService(
        RawReaderAdapter()
    ).load(context)

    return RgbdDecoder(
        PillowMjpegDecoder()
    ).decode(raw_packet)


@pytest.mark.parametrize("layout", ["legacy", "numbered"])
def test_replay_and_decode_registered_raw_without_mutating_store(
    tmp_path,
    layout,
):
    seeded_store(tmp_path)

    packet = packet_with_jpeg()

    if layout == "numbered":
        NumberedStorageRegistry.migrate_database(tmp_path)

        registry = NumberedStorageRegistry(tmp_path)

        registry.reserve_capture("c1", "t1", "s1")

        location = registry.write_reserved_capture(packet)

        registry.register_reserved_capture("c1")
    else:
        location = SessionStore(tmp_path).commit_raw(packet)

        with MetadataStore(tmp_path) as store:
            store.register_capture(location)

    before_hashes = {
        p.name: hashlib.sha256(p.read_bytes()).hexdigest()
        for p in location.iterdir()
        if p.is_file()
    }

    with MetadataStore(tmp_path) as db:
        before_events = db.list_events()

    frame = read_decoded(tmp_path)

    assert frame.color_rgb.shape == (12, 20, 3)
    assert frame.depth_u16.shape == (2, 3)

    assert frame.color_rgb.dtype == np.uint8
    assert frame.depth_u16.dtype == np.uint16

    assert frame.color_rgb[6, 10, 0] > 170

    assert frame.metadata.capture_id == "c1"
    assert frame.metadata.camera_pose is None

    after_hashes = {
        p.name: hashlib.sha256(p.read_bytes()).hexdigest()
        for p in location.iterdir()
        if p.is_file()
    }

    assert after_hashes == before_hashes

    with MetadataStore(tmp_path) as db:
        assert db.list_events() == before_events
        assert db.get_capture("c1")["capture_id"] == "c1"


def test_replay_accepts_storage_integrity_but_decoder_rejects_fake_jpeg(
    tmp_path,
):
    seeded_store(tmp_path)

    packet = packet_with_jpeg(malformed=True)

    path = SessionStore(tmp_path).commit_raw(packet)

    with MetadataStore(tmp_path) as db:
        db.register_capture(path)

    with pytest.raises(RgbdDecodeError) as error:
        read_decoded(tmp_path)

    assert error.value.code == "INVALID_MJPEG"

    assert SessionStore(tmp_path).read_raw(path) == packet