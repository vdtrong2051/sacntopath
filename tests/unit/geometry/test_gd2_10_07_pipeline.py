"""GD2-10.07.1: injected replay/decode/geometry composition tests.

Uses the pre-existing synthetic RAW fixture; no disk, camera, Qt or SDK.
"""
from __future__ import annotations

from dataclasses import replace
from hashlib import sha256
from types import SimpleNamespace

import numpy as np
import pytest

from scantopath.acquisition.raw_rgbd import RawRgbdCapture
from scantopath.domain.raw_rgbd import RawDistortion
from scantopath.modules.capture.application.contracts import CaptureContext
from scantopath.modules.capture.application.decoding import (
    RgbdDecodeError,
    RgbdDecoder,
)
from scantopath.modules.capture.application.replay import (
    RawReplayError,
    RawReplayService,
)
from scantopath.modules.geometry.application.measurements import measure_points
from scantopath.modules.geometry.application.replay_geometry import (
    ReplayGeometryError,
    ReplayGeometryService,
)
from scantopath.modules.geometry.application.service import SingleViewXYZRGB
from scantopath.modules.geometry.application.unprojection import DepthProjectionError
from scantopath.modules.geometry.application.validity import GeometryValidityError
from tests.support.raw_fixture import raw


def selection(capture_id: str | None = "capture-a") -> CaptureContext:
    return CaptureContext(
        store_root="unused-in-memory-fixture",
        project_id="project-a",
        specimen_id="specimen-a",
        session_id="session-a",
        capture_id=capture_id,
    )


def packet() -> RawRgbdCapture:
    return raw(
        session="session-a", specimen="specimen-a", capture_id="capture-a"
    )


class MemoryReader:
    def __init__(self, payload: RawRgbdCapture) -> None:
        self.payload = payload
        self.calls = 0

    def load(self, context: CaptureContext) -> RawRgbdCapture:
        self.calls += 1
        return self.payload


class FakeJpegDecoder:
    def decode(self, payload: bytes, *, width: int, height: int) -> np.ndarray:
        assert payload.startswith(b"\xff\xd8")
        return np.full((height, width, 3), 75, dtype=np.uint8)


def service(source: RawRgbdCapture | None = None):
    reader = MemoryReader(source if source is not None else packet())
    pipeline = ReplayGeometryService(
        RawReplayService(reader), RgbdDecoder(FakeJpegDecoder())
    )
    return pipeline, reader


def test_single_capture_replay_decode_geometry_preserves_lineage_and_hashes():
    source = packet()
    pipeline, reader = service(source)
    original = (source.color_mjpeg, source.depth_y16_le)

    result = pipeline.process(selection())

    assert isinstance(result, SingleViewXYZRGB)
    assert reader.calls == 1
    assert result.source_capture_id == "capture-a"
    assert result.units == "m" and result.frame == "depth_optical"
    assert result.metric_validated is False
    assert result.source_integrity_status == "NOT_VERIFIED_BY_GEOMETRY"
    assert result.quality_stats.valid_xyz_points > 0
    assert result.quality_stats.colored_points <= result.quality_stats.valid_xyz_points
    assert result.source_raw_sha256 == tuple(sorted((
        ("color.mjpg", sha256(source.color_mjpeg).hexdigest()),
        ("depth.y16", sha256(source.depth_y16_le).hexdigest()),
    )))
    assert (source.color_mjpeg, source.depth_y16_le) == original


def test_integration_output_is_measurement_compatible_and_provisional():
    pipeline, _ = service()
    result = pipeline.process(selection())
    measurement = measure_points(result, 0, 1)
    assert measurement.source_capture_id == result.source_capture_id
    assert measurement.distance_m > 0
    assert measurement.distance_mm == pytest.approx(measurement.distance_m * 1000)
    assert measurement.status == "PROVISIONAL_NOT_METRIC_VALIDATED"


def test_missing_capture_id_fails_before_accessing_reader():
    pipeline, reader = service()
    with pytest.raises(ReplayGeometryError) as exc:
        pipeline.process(selection(None))
    assert exc.value.code == "CAPTURE_ID_REQUIRED"
    assert reader.calls == 0


def test_wrong_context_type_rejected():
    pipeline, reader = service()
    with pytest.raises(ReplayGeometryError) as exc:
        pipeline.process(object())
    assert exc.value.code == "CAPTURE_CONTEXT_INVALID"
    assert reader.calls == 0


def test_wrong_capture_lineage_is_rejected_by_real_replay_service():
    wrong = raw(
        session="session-a", specimen="specimen-a", capture_id="capture-b"
    )
    pipeline, _ = service(wrong)
    with pytest.raises(RawReplayError) as exc:
        pipeline.process(selection())
    assert exc.value.code == "CAPTURE_CONTEXT_MISMATCH"


def test_raw_integrity_error_from_reader_is_preserved():
    class RejectReader:
        def load(self, context):
            raise RawReplayError("RAW_INTEGRITY_FAILED", "synthetic failure")

    pipeline = ReplayGeometryService(
        RawReplayService(RejectReader()), RgbdDecoder(FakeJpegDecoder())
    )
    with pytest.raises(RawReplayError) as exc:
        pipeline.process(selection())
    assert exc.value.code == "RAW_INTEGRITY_FAILED"


def test_mjpeg_decode_error_is_preserved():
    class RejectJpeg:
        def decode(self, payload, *, width, height):
            raise RgbdDecodeError("INVALID_MJPEG", "synthetic decode failure")

    pipeline = ReplayGeometryService(
        RawReplayService(MemoryReader(packet())), RgbdDecoder(RejectJpeg())
    )
    with pytest.raises(RgbdDecodeError) as exc:
        pipeline.process(selection())
    assert exc.value.code == "INVALID_MJPEG"


def test_decoded_metadata_drift_is_rejected_before_geometry():
    source = packet()

    class WrongMetadataDecoder:
        def decode(self, payload):
            good = RgbdDecoder(FakeJpegDecoder()).decode(payload)
            return replace(
                good, metadata=good.metadata.model_copy(
                    update={"capture_id": "capture-other"}
                ),
            )

    pipeline = ReplayGeometryService(
        RawReplayService(MemoryReader(source)), WrongMetadataDecoder()
    )
    with pytest.raises(ReplayGeometryError) as exc:
        pipeline.process(selection())
    assert exc.value.code == "DECODE_RESULT_INVALID"


@pytest.mark.parametrize("bad_grid", ["depth_dtype", "color_shape"])
def test_malformed_decoded_grid_rejected(bad_grid):
    class BadDecoder:
        def decode(self, payload):
            good = RgbdDecoder(FakeJpegDecoder()).decode(payload)
            depth = good.depth_u16
            color = good.color_rgb
            if bad_grid == "depth_dtype":
                depth = depth.astype(np.float64)
            else:
                color = color[:, :-1, :].copy()
            return SimpleNamespace(metadata=good.metadata,
                                   depth_u16=depth, color_rgb=color)

    pipeline = ReplayGeometryService(
        RawReplayService(MemoryReader(packet())), BadDecoder()
    )
    with pytest.raises(ReplayGeometryError) as exc:
        pipeline.process(selection())
    assert exc.value.code == "DECODE_RESULT_INVALID"


def test_unsupported_depth_model_propagates_without_fallback():
    source = packet()
    invalid = source.metadata.model_copy(update={
        "depth_distortion": RawDistortion(
            sdk_model=1, k1_k6_p1_p2=(0.0,) * 8
        )
    })
    changed = RawRgbdCapture(
        metadata=invalid,
        color_mjpeg=source.color_mjpeg,
        depth_y16_le=source.depth_y16_le,
    )
    pipeline, _ = service(changed)
    with pytest.raises(DepthProjectionError) as exc:
        pipeline.process(selection())
    assert exc.value.code == "DISTORTION_MODEL_UNSUPPORTED"


def test_all_zero_depth_propagates_geometry_empty_error():
    source = packet()
    empty = RawRgbdCapture(
        metadata=source.metadata,
        color_mjpeg=source.color_mjpeg,
        depth_y16_le=bytes(len(source.depth_y16_le)),
    )
    pipeline, _ = service(empty)
    with pytest.raises(GeometryValidityError) as exc:
        pipeline.process(selection())
    assert exc.value.code == "EMPTY_VALID_DEPTH"


def test_invalid_constructor_ports_rejected():
    with pytest.raises(TypeError):
        ReplayGeometryService(object(), object())
