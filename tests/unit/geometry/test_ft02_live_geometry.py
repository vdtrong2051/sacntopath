"""FT-02 synthetic geometry/calibration tests; never opens camera or VTK."""
from __future__ import annotations

from dataclasses import replace
import pickle
from types import SimpleNamespace as NS

import numpy as np
import pytest

from scantopath.modules.capture.application.live_calibration import (
    LiveCalibrationError, LiveCalibrationSnapshot,
)
from scantopath.modules.capture.application.live_stream import LiveNativeFrame, LiveRgbdFrame
from scantopath.modules.geometry.application.live_geometry import LiveGeometryError, LiveGeometryService
from scantopath.modules.geometry.application.calibration import CalibrationContract
from scantopath.modules.geometry.application.unprojection import unproject_depth
from tests.support.raw_fixture import raw


def packet():
    return NS(
        depth=NS(width=3, height=2), color=NS(width=5, height=4),
        depth_intrinsics=NS(width=3, height=2, fx=3.0, fy=3.0, cx=1.0, cy=1.0),
        color_intrinsics=NS(width=5, height=4, fx=5.0, fy=5.0, cx=2.0, cy=2.0),
        depth_distortion=NS(sdk_model=0, k1_k6_p1_p2=[0.0] * 8),
        color_distortion=NS(sdk_model=3, k1_k6_p1_p2=[0.0] * 8),
        depth_to_color=NS(rotation=[1., 0., 0., 0., 1., 0., 0., 0., 1.],
                          translation_mm=[-13.7, 0.0, 0.0]),
        depth_scale_m_per_unit=0.001, align_disabled=True,
    )


def live_frame(depth=None, p=None):
    if depth is None:
        depth = np.array([[0, 99, 100], [100, 900, 1000]], dtype="<u2")
    if p is None:
        p = packet()
    c = LiveCalibrationSnapshot.from_native_packet(p)
    raw_frame = LiveNativeFrame(
        color_mjpeg=b"jpeg", depth_y16_le=depth.tobytes(),
        color_width=5, color_height=4, depth_width=3, depth_height=2,
        color_frame_index=4, depth_frame_index=5,
        color_timestamp_us=1000, depth_timestamp_us=1100,
        depth_scale_m_per_unit=0.001, device_name="Orbbec Gemini 2", firmware="fake",
        calibration=c,
    )
    return LiveRgbdFrame(raw_frame, np.zeros((4, 5, 3), dtype=np.uint8), depth)


def test_cal_01_05_snapshot_same_frame_immutable_pickle_and_meters():
    c = LiveCalibrationSnapshot.from_native_packet(packet())
    assert c.depth_intrinsics.width == 3 and c.color_intrinsics.width == 5
    assert c.translation_C_D_m[0] == pytest.approx(-0.0137)
    assert c.fingerprint == pickle.loads(pickle.dumps(c)).fingerprint
    with pytest.raises(Exception):
        c.depth_scale_m_per_unit = 4.0


def test_cal_02_reject_grid_mismatch():
    p = packet()
    p.depth_intrinsics.width = 8
    with pytest.raises(LiveCalibrationError) as exc:
        LiveCalibrationSnapshot.from_native_packet(p)
    assert exc.value.code == "INTRINSICS_INVALID"


@pytest.mark.parametrize("fx", [0, -1, float("nan"), float("inf")])
def test_cal_03_invalid_intrinsics(fx):
    p = packet()
    p.depth_intrinsics.fx = fx
    with pytest.raises(LiveCalibrationError) as exc:
        LiveCalibrationSnapshot.from_native_packet(p)
    assert exc.value.code == "INTRINSICS_INVALID"


@pytest.mark.parametrize("scale", [0, -0.01, float("nan"), float("inf")])
def test_cal_04_invalid_scale(scale):
    p = packet()
    p.depth_scale_m_per_unit = scale
    with pytest.raises(LiveCalibrationError) as exc:
        LiveCalibrationSnapshot.from_native_packet(p)
    assert exc.value.code == "DEPTH_SCALE_INVALID"


def test_cal_06_extrinsics_must_be_proper_rotation():
    p = packet()
    p.depth_to_color.rotation[0] = -1
    with pytest.raises(LiveCalibrationError) as exc:
        LiveCalibrationSnapshot.from_native_packet(p)
    assert exc.value.code == "EXTRINSICS_INVALID"


@pytest.mark.parametrize("model,first_coeff", [(1, 0.0), (4, 0.02), (3, 0.0)])
def test_cal_07_unsupported_depth_distortion(model, first_coeff):
    p = packet()
    p.depth_distortion.sdk_model = model
    p.depth_distortion.k1_k6_p1_p2[0] = first_coeff
    with pytest.raises(LiveGeometryError) as exc:
        LiveGeometryService.process(live_frame(p=p), camera_generation=1)
    assert exc.value.code == "DISTORTION_MODEL_UNSUPPORTED"


def test_geo_01_02_unprojection_meters_pixel_center_and_depth_zero():
    cloud = LiveGeometryService.process(live_frame(), camera_generation=9)
    assert cloud.points_xyz_m.dtype == np.dtype("<f4")
    assert cloud.points_xyz_m.shape == (5, 3)
    assert cloud.points_xyz_m[3] == pytest.approx([0, 0, 0.9], abs=1e-7)
    assert cloud.statistics.missing_depth == 1
    assert cloud.coordinate_frame == "depth_optical" and cloud.units == "m"
    assert cloud.color_status == "XYZ_ONLY" and not cloud.metric_validated
    assert not cloud.points_xyz_m.flags.writeable and not cloud.depth_source_uv.flags.writeable


def test_geo_04_roi_preserves_uv_and_rejects_out_of_bounds():
    cloud = LiveGeometryService.process(live_frame(), camera_generation=1, depth_roi=(1, 0, 2, 2))
    np.testing.assert_array_equal(cloud.depth_source_uv, [[1, 0], [2, 0], [1, 1], [2, 1]])
    assert cloud.statistics.roi_pixels == 4
    with pytest.raises(LiveGeometryError) as exc:
        LiveGeometryService.process(live_frame(), camera_generation=1, depth_roi=(2, 1, 2, 2))
    assert exc.value.code == "ROI_INVALID"


def test_geo_05_depth_range_inclusive_and_empty():
    a = LiveGeometryService.process(live_frame(), camera_generation=1,
                                    min_depth_m=0.1, max_depth_m=0.9)
    assert a.statistics.output_points == 3
    with pytest.raises(LiveGeometryError) as exc:
        LiveGeometryService.process(live_frame(), camera_generation=1,
                                    min_depth_m=5., max_depth_m=10.)
    assert exc.value.code == "EMPTY_VALID_DEPTH"


def test_geo_06_parity_with_gd2_10_same_calibration():
    source = raw()
    m = source.metadata
    depth = source.depth_u16_copy()
    c = CalibrationContract.from_metadata(m)
    # Derive live snapshot from the SAME reference intrinsics and extrinsics.
    p = NS(
        depth=NS(width=m.depth.width, height=m.depth.height),
        color=NS(width=m.color.width, height=m.color.height),
        depth_intrinsics=NS(**vars(m.depth_intrinsics)) if hasattr(m.depth_intrinsics, "__dict__") else
            NS(width=m.depth_intrinsics.width, height=m.depth_intrinsics.height,
               fx=m.depth_intrinsics.fx, fy=m.depth_intrinsics.fy,
               cx=m.depth_intrinsics.cx, cy=m.depth_intrinsics.cy),
        color_intrinsics=NS(width=m.color_intrinsics.width, height=m.color_intrinsics.height,
                            fx=m.color_intrinsics.fx, fy=m.color_intrinsics.fy,
                            cx=m.color_intrinsics.cx, cy=m.color_intrinsics.cy),
        depth_distortion=NS(sdk_model=m.depth_distortion.sdk_model,
                            k1_k6_p1_p2=list(m.depth_distortion.k1_k6_p1_p2)),
        color_distortion=NS(sdk_model=m.color_distortion.sdk_model,
                            k1_k6_p1_p2=list(m.color_distortion.k1_k6_p1_p2)),
        depth_to_color=NS(rotation=list(m.depth_to_color.rotation),
                          translation_mm=list(m.depth_to_color.translation_mm)),
        depth_scale_m_per_unit=m.depth_scale_m_per_unit, align_disabled=True,
    )
    native = LiveNativeFrame(
        color_mjpeg=b"jpeg", depth_y16_le=depth.tobytes(),
        color_width=m.color.width, color_height=m.color.height,
        depth_width=m.depth.width, depth_height=m.depth.height,
        color_frame_index=4, depth_frame_index=5, color_timestamp_us=100, depth_timestamp_us=101,
        depth_scale_m_per_unit=m.depth_scale_m_per_unit, device_name="Orbbec Gemini 2", firmware="fake",
        calibration=LiveCalibrationSnapshot.from_native_packet(p),
    )
    frame = LiveRgbdFrame(native,
                          np.zeros((m.color.height, m.color.width, 3), dtype=np.uint8), depth)
    ref = unproject_depth(depth, calibration=c, capture_id=c.capture_id)
    actual = LiveGeometryService.process(frame, camera_generation=1)
    expected = ref.xyz_m[ref.depth_valid_mask]
    np.testing.assert_allclose(actual.points_xyz_m, expected.astype(np.float32), rtol=1e-6, atol=1e-7)
    rows, cols = np.nonzero(ref.depth_valid_mask)
    np.testing.assert_array_equal(actual.depth_source_uv, np.column_stack((cols, rows)))


def test_geo_07_does_not_color_from_mismatched_grids():
    c = LiveGeometryService.process(live_frame(), camera_generation=1)
    assert c.color_status == "XYZ_ONLY"
    assert not hasattr(c, "colors_rgb")


def test_sampling_is_bounded_deterministic_and_owned():
    d = np.full((2, 3), 1000, dtype=np.uint16)
    frame = live_frame(d)
    a = LiveGeometryService.process(frame, camera_generation=1, point_budget=2)
    b = LiveGeometryService.process(frame, camera_generation=1, point_budget=2)
    assert a.statistics.output_points == 2 and a.statistics.skipped_for_sampling == 4
    np.testing.assert_array_equal(a.points_xyz_m, b.points_xyz_m)
    np.testing.assert_array_equal(a.depth_source_uv, b.depth_source_uv)
    assert not np.shares_memory(a.points_xyz_m, frame.depth_u16)


def test_missing_calibration_keeps_preview_but_geometry_rejects():
    f = live_frame()
    src = replace(f.source, calibration=None, calibration_error="LIVE_CALIBRATION_MISSING")
    no_cal = LiveRgbdFrame(src, f.color_rgb, f.depth_u16)
    assert no_cal.color_rgb.shape == (4, 5, 3)
    with pytest.raises(LiveGeometryError) as exc:
        LiveGeometryService.process(no_cal, camera_generation=1)
    assert exc.value.code == "LIVE_CALIBRATION_MISSING"


def test_snapshot_refuses_wrong_scale_and_sample_generation():
    f = live_frame()
    with pytest.raises(ValueError):
        replace(f.source, depth_scale_m_per_unit=0.002)
    with pytest.raises(LiveGeometryError) as exc:
        LiveGeometryService.process(f, camera_generation=0)
    assert exc.value.code == "LIVE_FRAME_KEY_INVALID"
