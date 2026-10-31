"""GD2-10.07.2: real temporary RAW-v2/SQLite -> Replay -> Decode -> Geometry.

All files are confined to pytest tmp_path. No operator H6, camera, Qt or VTK.
The fixture is SYNTHETIC; successful tests are NOT hardware/metric validation.
"""
from __future__ import annotations

from hashlib import sha256
from io import BytesIO
import json
import sqlite3

import numpy as np
from PIL import Image
import pytest

from scantopath.acquisition.raw_rgbd import RawRgbdCapture
from scantopath.domain.raw_rgbd import RawDistortion
from scantopath.metadata.store import MetadataStore
from scantopath.modules.capture.application.contracts import CaptureContext
from scantopath.modules.capture.application.decoding import RgbdDecodeError, RgbdDecoder
from scantopath.modules.capture.application.replay import RawReplayError, RawReplayService
from scantopath.modules.capture.infrastructure.jpeg_codec import PillowMjpegDecoder
from scantopath.modules.capture.infrastructure.raw_reader import RawReaderAdapter
from scantopath.modules.geometry.application.measurements import (
    MeasurementError, measure_points, measure_selected_points, select_measurement_point,
)
from scantopath.modules.geometry.application.replay_geometry import (
    ReplayGeometryError, ReplayGeometryService,
)
from scantopath.modules.geometry.application.unprojection import DepthProjectionError
from scantopath.modules.geometry.application.validity import GeometryValidityError
from scantopath.storage.numbered import NumberedStorageRegistry
from scantopath.storage.session_store import SessionStore
from tests.support.raw_fixture import raw


def _packet(capture_id="c1", *, bad_jpeg=False, zero_depth=False, depth_model=4):
    base = raw(session="t1", specimen="s1", capture_id=capture_id)
    if bad_jpeg:
        jpeg = b"\xff\xd8invalid-jpeg\xff\xd9"
    else:
        pixels = np.full((4, 5, 3), (160, 70, 40), dtype=np.uint8)
        buffer = BytesIO()
        Image.fromarray(pixels, mode="RGB").save(
            buffer, format="JPEG", quality=95, subsampling=0,
        )
        jpeg = buffer.getvalue()

    metadata = base.metadata.model_copy(update={
        "color": base.metadata.color.model_copy(update={
            "payload_size_bytes": len(jpeg),
        }),
        "depth_distortion": RawDistortion(
            sdk_model=depth_model, k1_k6_p1_p2=(0.0,) * 8,
        ),
        "color_distortion": RawDistortion(
            sdk_model=4,
            k1_k6_p1_p2=(0.2, 0.0, 0.0, 0.1, 0.0, 0.0, 0.0, 0.0),
        ),
    })
    depth = bytes(len(base.depth_y16_le)) if zero_depth else base.depth_y16_le
    return RawRgbdCapture(metadata, jpeg, depth)


def _seed(root, layout):
    with MetadataStore(root) as db:
        db.create_project("p1", "Synthetic project")
        db.create_specimen("s1", "p1", "Synthetic specimen")
        db.create_scan_session("t1", "s1", "Synthetic session")
    if layout == "numbered":
        NumberedStorageRegistry.migrate_database(root)


def _commit(root, layout, packet):
    if layout == "numbered":
        registry = NumberedStorageRegistry(root)
        registry.reserve_capture(packet.metadata.capture_id, "t1", "s1")
        path = registry.write_reserved_capture(packet)
        registry.register_reserved_capture(packet.metadata.capture_id)
        return path
    path = SessionStore(root).commit_raw(packet)
    with MetadataStore(root) as db:
        db.register_capture(path)
    return path


def _context(root, capture_id="c1", **change):
    data = dict(
        store_root=str(root), project_id="p1", specimen_id="s1",
        session_id="t1", capture_id=capture_id,
    )
    data.update(change)
    return CaptureContext(**data)


def _pipeline():
    return ReplayGeometryService(
        RawReplayService(RawReaderAdapter()),
        RgbdDecoder(PillowMjpegDecoder()),
    )


def _hashes(path):
    return {p.name: sha256(p.read_bytes()).hexdigest()
            for p in path.iterdir() if p.is_file()}


def _db_state(root):
    db = sqlite3.connect((root / "metadata.sqlite3").as_uri() + "?mode=ro", uri=True)
    try:
        db.execute("PRAGMA query_only=ON")
        return tuple(db.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]
                     for table in ("captures", "audit_events", "processing_runs"))
    finally:
        db.close()


@pytest.fixture(params=("legacy", "numbered"))
def prepared(tmp_path, request):
    layout = request.param
    _seed(tmp_path, layout)
    path = _commit(tmp_path, layout, _packet())
    return tmp_path, layout, path


def test_real_sqlite_verified_replay_jpeg_k6_and_measurement(prepared):
    root, _, path = prepared
    files_before, db_before = _hashes(path), _db_state(root)

    view = _pipeline().process(_context(root))
    distance = measure_points(view, 0, 1)

    assert view.source_capture_id == "c1"
    assert view.units == "m" and view.frame == "depth_optical"
    assert view.points_xyz_m.shape == (5, 3)
    assert 0 < view.quality_stats.colored_points <= 5
    assert view.metric_validated is False
    assert view.source_integrity_status == "NOT_VERIFIED_BY_GEOMETRY"
    assert dict(view.source_raw_sha256) == {
        "color.mjpg": files_before["color.mjpg"],
        "depth.y16": files_before["depth.y16"],
    }
    assert distance.distance_m > 0
    assert distance.distance_mm == pytest.approx(distance.distance_m * 1000)
    assert distance.status == "PROVISIONAL_NOT_METRIC_VALIDATED"
    assert _hashes(path) == files_before
    assert _db_state(root) == db_before


def test_repeat_process_is_deterministic_and_read_only(prepared):
    root, _, path = prepared
    before = (_hashes(path), _db_state(root))
    first, second = (_pipeline().process(_context(root)) for _ in range(2))
    np.testing.assert_array_equal(first.points_xyz_m, second.points_xyz_m)
    np.testing.assert_array_equal(first.colors_rgb, second.colors_rgb)
    assert first.calibration_fingerprint == second.calibration_fingerprint
    assert first.source_raw_sha256 == second.source_raw_sha256
    assert (_hashes(path), _db_state(root)) == before


@pytest.mark.parametrize("target", ("color.mjpg", "depth.y16", "metadata.json"))
def test_corrupt_raw_bytes_are_rejected_before_geometry(prepared, target):
    root, _, path = prepared
    source = path / target
    data = bytearray(source.read_bytes())
    data[-1] ^= 1  # Only the isolated pytest tmp_path fixture is modified.
    source.write_bytes(data)
    with pytest.raises(RawReplayError) as error:
        _pipeline().process(_context(root))
    assert error.value.code == "RAW_INTEGRITY_FAILED"


def test_corrupt_manifest_hash_rejected(prepared):
    root, _, path = prepared
    manifest = path / "manifest.json"
    contents = json.loads(manifest.read_text("utf-8"))
    contents["files"]["depth.y16"]["sha256"] = "0" * 64
    manifest.write_text(json.dumps(contents), encoding="utf-8")
    with pytest.raises(RawReplayError) as error:
        _pipeline().process(_context(root))
    assert error.value.code == "RAW_INTEGRITY_FAILED"


@pytest.mark.parametrize("change", (
    {"project_id": "other"}, {"specimen_id": "other"},
    {"session_id": "other"}, {"capture_id": "other"},
))
def test_wrong_registered_context_is_rejected(prepared, change):
    root, _, _ = prepared
    with pytest.raises(RawReplayError) as error:
        _pipeline().process(_context(root, **change))
    assert error.value.code in ("CAPTURE_CONTEXT_MISMATCH", "CAPTURE_NOT_REGISTERED")


def test_missing_capture_id_rejected_without_replay(prepared):
    root, _, _ = prepared
    with pytest.raises(ReplayGeometryError) as error:
        _pipeline().process(_context(root, capture_id=None))
    assert error.value.code == "CAPTURE_ID_REQUIRED"


def test_verified_raw_with_invalid_jpeg_still_fails_decode(tmp_path):
    _seed(tmp_path, "legacy")
    _commit(tmp_path, "legacy", _packet(bad_jpeg=True))
    with pytest.raises(RgbdDecodeError) as error:
        _pipeline().process(_context(tmp_path))
    assert error.value.code == "INVALID_MJPEG"


def test_verified_raw_with_empty_depth_fails_geometry(tmp_path):
    _seed(tmp_path, "legacy")
    _commit(tmp_path, "legacy", _packet(zero_depth=True))
    with pytest.raises(GeometryValidityError) as error:
        _pipeline().process(_context(tmp_path))
    assert error.value.code == "EMPTY_VALID_DEPTH"


def test_verified_raw_with_unsupported_depth_distortion_fails_closed(tmp_path):
    _seed(tmp_path, "legacy")
    _commit(tmp_path, "legacy", _packet(depth_model=1))
    with pytest.raises(DepthProjectionError) as error:
        _pipeline().process(_context(tmp_path))
    assert error.value.code == "DISTORTION_MODEL_UNSUPPORTED"


def test_two_captures_cannot_share_measurement_selection(tmp_path):
    _seed(tmp_path, "legacy")
    _commit(tmp_path, "legacy", _packet("c1"))
    _commit(tmp_path, "legacy", _packet("c2"))
    pipeline = _pipeline()
    first = select_measurement_point(pipeline.process(_context(tmp_path, "c1")), 0)
    second = select_measurement_point(pipeline.process(_context(tmp_path, "c2")), 1)
    with pytest.raises(MeasurementError) as error:
        measure_selected_points(first, second)
    assert error.value.code == "MEASUREMENT_FRAME_MISMATCH"
