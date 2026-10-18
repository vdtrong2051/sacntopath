"""PRE-02 contract regression tests. All payloads are SYNTHETIC fixtures.

No camera, SDK, storage, GPU, network, or C++ native import needed.
"""
from dataclasses import FrozenInstanceError
from datetime import datetime
import math

import numpy as np
import pytest
from pydantic import ValidationError

from scantopath.acquisition.raw_rgbd import RawRgbdCapture
from scantopath.domain.models import CaptureKind
from scantopath.domain.raw_rgbd import (
    RawDepthToColorExtrinsics,
    RawDeviceInfo,
    RawDistortion,
    RawIntrinsics,
    RawRgbdCaptureMetadataV2,
    RawStreamInfo,
    RawPixelEncoding,
)


JPEG_FIXTURE = b"\xff\xd8synthetic-jpeg-payload\xff\xd9"
DEPTH_FIXTURE = np.array([[1000, 0, 65535], [12, 13, 14]], dtype="<u2")


def example_metadata(**changes):
    fields = dict(
        session_id="session-1",
        specimen_id="specimen-1",
        kind=CaptureKind.SYNTHETIC,
        measured=False,
        device=RawDeviceInfo(name="SYNTHETIC_RAW_CONTRACT_FIXTURE"),
        color=RawStreamInfo(
            encoding=RawPixelEncoding.MJPEG, width=5, height=4, frame_index=11,
            timestamp_us=100_000, payload_size_bytes=len(JPEG_FIXTURE),
        ),
        depth=RawStreamInfo(
            encoding=RawPixelEncoding.Y16, width=3, height=2, frame_index=7,
            timestamp_us=103_308, payload_size_bytes=DEPTH_FIXTURE.nbytes,
        ),
        color_intrinsics=RawIntrinsics(width=5, height=4, fx=4.5, fy=4.6, cx=2.0, cy=1.5),
        depth_intrinsics=RawIntrinsics(width=3, height=2, fx=3.5, fy=3.6, cx=1.0, cy=0.5),
        color_distortion=RawDistortion(sdk_model=1, k1_k6_p1_p2=(0., 0., 0., 0., 0., 0., 0., 0.)),
        depth_distortion=RawDistortion(sdk_model=2, k1_k6_p1_p2=(0.1, 0., 0., 0., 0., 0., 0., 0.)),
        depth_to_color=RawDepthToColorExtrinsics(
            rotation=(1., 0., 0., 0., 1., 0., 0., 0., 1.),
            translation_mm=(-13.787516, -0.104090, -1.982521),
        ),
        depth_scale_m_per_unit=0.001,
    )
    fields.update(changes)
    return RawRgbdCaptureMetadataV2(**fields)


def example_capture(**changes):
    return RawRgbdCapture(example_metadata(**changes), JPEG_FIXTURE, DEPTH_FIXTURE.tobytes())


def test_unaligned_independent_pixel_grids_and_sensor_metadata():
    capture = example_capture()
    m = capture.metadata
    assert m.schema_version == 2 and m.alignment_mode == "disabled"
    assert (m.color.width, m.color.height) == (5, 4)
    assert (m.depth.width, m.depth.height) == (3, 2)
    assert m.observed_timestamp_delta_us == 3308
    assert m.timestamp_domain == "sdk_reported_unverified"
    assert m.camera_pose is None and m.coordinate_frame == "depth_optical"
    assert m.depth_to_color.translation_mm[0] == pytest.approx(-13.787516)
    assert m.depth_scale_m_per_unit == 0.001
    assert m.measured is False


def test_lossless_metadata_json_roundtrip():
    before = example_metadata()
    after = RawRgbdCaptureMetadataV2.model_validate_json(before.model_dump_json())
    assert before == after
    assert after.color_intrinsics != after.depth_intrinsics
    assert after.color_distortion.sdk_model != after.depth_distortion.sdk_model
    assert after.depth_to_color.translation_mm == before.depth_to_color.translation_mm
    assert after.captured_at.tzinfo is not None


def test_lossless_depth_values_copy_after_buffer_lifetime():
    capture = example_capture()
    copied = capture.depth_u16_copy()
    assert copied.dtype == np.uint16 and copied.shape == (2, 3)
    np.testing.assert_array_equal(copied, DEPTH_FIXTURE)
    assert copied.flags.owndata
    copied[0, 0] = 4321
    assert capture.depth_u16_copy()[0, 0] == 1000


def test_reject_wrong_payload_sizes():
    m = example_metadata()
    with pytest.raises(ValueError, match="MJPEG payload length"):
        RawRgbdCapture(m, JPEG_FIXTURE[:-1], DEPTH_FIXTURE.tobytes())
    with pytest.raises(ValueError, match="Y16 payload length"):
        RawRgbdCapture(m, JPEG_FIXTURE, DEPTH_FIXTURE.tobytes()[:-1])


def test_reject_mutable_vendor_buffers_and_invalid_jpeg_header():
    m = example_metadata()
    with pytest.raises(TypeError, match="immutable"):
        RawRgbdCapture(m, bytearray(JPEG_FIXTURE), DEPTH_FIXTURE.tobytes())
    with pytest.raises(TypeError, match="immutable"):
        RawRgbdCapture(m, JPEG_FIXTURE, memoryview(DEPTH_FIXTURE.tobytes()))
    with pytest.raises(ValueError, match="JPEG SOI"):
        RawRgbdCapture(m, b"BAD" + JPEG_FIXTURE[3:], DEPTH_FIXTURE.tobytes())


def test_reject_misrepresented_alignment_and_camera_pose():
    with pytest.raises(ValidationError):
        example_metadata(alignment_mode="depth_to_color")
    with pytest.raises(ValidationError):
        example_metadata(camera_pose={"theta_deg": 0.0})
    with pytest.raises(ValidationError):
        example_metadata(stage_pose={"theta_deg": 0.0})


def test_reject_incorrect_alignment_grid_calibration():
    bad = RawIntrinsics(width=4, height=4, fx=4., fy=4., cx=2., cy=2.)
    with pytest.raises(ValidationError, match="Color intrinsics"):
        example_metadata(color_intrinsics=bad)
    bad_depth = RawIntrinsics(width=4, height=2, fx=4., fy=4., cx=2., cy=1.)
    with pytest.raises(ValidationError, match="Depth intrinsics"):
        example_metadata(depth_intrinsics=bad_depth)


def test_reject_incorrect_encoding_and_y16_byte_count():
    with pytest.raises(ValidationError):
        example_metadata(color=RawStreamInfo(
            encoding=RawPixelEncoding.Y16, width=5, height=4, frame_index=11,
            timestamp_us=100, payload_size_bytes=len(JPEG_FIXTURE),
        ))
    with pytest.raises(ValidationError):
        example_metadata(depth=RawStreamInfo(
            encoding=RawPixelEncoding.Y16, width=3, height=2, frame_index=7,
            timestamp_us=101, payload_size_bytes=11,
        ))


def test_reject_provenance_inversion():
    with pytest.raises(ValidationError, match="Synthetic RAW"):
        example_metadata(measured=True)
    with pytest.raises(ValidationError, match="Orbbec source"):
        example_metadata(kind=CaptureKind.ORBBEC, measured=False)
    valid_sensor = example_metadata(kind=CaptureKind.ORBBEC, measured=True,
                                    device=RawDeviceInfo(name="Orbbec Gemini 2"))
    assert valid_sensor.measured is True
    with pytest.raises(ValidationError):
        example_metadata(kind=CaptureKind.REPLAY)


def test_reject_non_finite_calibration_and_scale():
    with pytest.raises(ValidationError):
        example_metadata(depth_scale_m_per_unit=math.nan)
    with pytest.raises(ValidationError):
        RawIntrinsics(width=3, height=2, fx=math.inf, fy=3., cx=1., cy=1.)
    with pytest.raises(ValidationError, match="Distortion coefficients"):
        RawDistortion(sdk_model=0, k1_k6_p1_p2=(math.nan, 0., 0., 0., 0., 0., 0., 0.))
    with pytest.raises(ValidationError, match="Extrinsic components"):
        RawDepthToColorExtrinsics(
            rotation=(1., 0., 0., 0., math.inf, 0., 0., 0., 1.),
            translation_mm=(0., 0., 0.),
        )


def test_reject_invalid_ids_and_naive_host_time():
    with pytest.raises(ValidationError):
        example_metadata(session_id="../evil")
    with pytest.raises(ValidationError):
        example_metadata(specimen_id="../../bad")
    with pytest.raises(ValidationError, match="timezone"):
        example_metadata(captured_at=datetime(2026, 10, 18, 10, 0, 0))


def test_v2_metadata_is_frozen_no_v1_mutation():
    m = example_metadata()
    with pytest.raises(ValidationError):
        m.measured = True
    with pytest.raises(FrozenInstanceError):
        example_capture().depth_y16_le = b""
    from scantopath.domain.models import CaptureMetadata
    assert 1 == CaptureMetadata.model_fields["schema_version"].default


def test_gemini2_raw_stream_dimensions_fixture_not_hardware():
    """2 MB synthetic Y16 fixture matching Gemini 2 RAW stream layout."""
    fake_mjpeg = b"\xff\xd8\xff\xd9"  # Contract marker only, not a decoded image.
    fake_depth = np.full((800, 1280), 1000, dtype="<u2").tobytes()
    m = example_metadata(
        color=RawStreamInfo(
            encoding=RawPixelEncoding.MJPEG, width=1920, height=1080,
            frame_index=1, timestamp_us=200_000, payload_size_bytes=len(fake_mjpeg),
        ),
        depth=RawStreamInfo(
            encoding=RawPixelEncoding.Y16, width=1280, height=800,
            frame_index=2, timestamp_us=203_308, payload_size_bytes=len(fake_depth),
        ),
        color_intrinsics=RawIntrinsics(
            width=1920, height=1080, fx=1030.94, fy=1031.01, cx=965.81, cy=537.89,
        ),
        depth_intrinsics=RawIntrinsics(
            width=1280, height=800, fx=610.908264, fy=610.908264,
            cx=640.787842, cy=397.602814,
        ),
    )
    capture = RawRgbdCapture(m, fake_mjpeg, fake_depth)
    assert (capture.metadata.color.width, capture.metadata.depth.width) == (1920, 1280)
    assert capture.depth_u16_copy().shape == (800, 1280)
    assert capture.depth_u16_copy()[0, 0] == 1000
    assert capture.metadata.measured is False
