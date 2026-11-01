"""FT-05.8 synthetic geometry gates; tests no camera, Qt, RAW, SQLite or VTK."""
from __future__ import annotations
from types import SimpleNamespace as NS
import numpy as np
import cv2
import pytest
from scantopath.modules.geometry.application.live_charuco_isolation import (
    BOARD_SQUARES, SQUARE_M, MARKER_M, _board, _camera_model,
    isolate_charuco_object, detect_charuco_pose, CharucoIsolationConfig,
)


def fixture():
    board, _ = _board()
    gray_board = board.generateImage((600, 800))
    # Color and Depth are SEPARATE native grids. Color board pose has known metric size.
    t = np.array([-.14, -.17, .9], dtype=float)
    quad = np.array([[0., 0.], [.27, 0.], [.27, .36], [0., .36]])
    quad = (quad + t[:2]) / t[2] * 1400 + np.array([640, 480])
    transform = cv2.getPerspectiveTransform(
        np.array([[0, 0], [599, 0], [599, 799], [0, 799]], np.float32),
        np.array(quad, np.float32),
    )
    board_pixels = cv2.warpPerspective(gray_board, transform, (1280, 960), borderValue=200)
    area = cv2.warpPerspective(np.full_like(gray_board, 255), transform, (1280, 960))
    gray = np.full((960, 1280), 200, np.uint8)
    gray[area > 0] = board_pixels[area > 0]
    rgb = cv2.cvtColor(gray, cv2.COLOR_GRAY2RGB)
    depth = np.full((240, 320), 900, dtype=np.uint16)
    depth[102:126, 150:175] = 845  # 55 mm tall object on plane
    distortion = NS(sdk_model=0, k1_k6_p1_p2=(0.,) * 8)
    calibration = NS(
        color_intrinsics=NS(width=1280, height=960, fx=1400., fy=1400., cx=640., cy=480.),
        depth_intrinsics=NS(width=320, height=240, fx=350., fy=350., cx=160., cy=120.),
        color_distortion=distortion, depth_distortion=distortion,
        rotation_C_D=(1., 0., 0., 0., 1., 0., 0., 0., 1.),
        translation_C_D_m=(0., 0., 0.), alignment_mode='disabled',
        coordinate_frame='depth_optical', depth_scale_m_per_unit=.001,
    )
    return rgb, depth, calibration


def test_board_profile_modern_pattern_matches_geometry():
    b, _ = _board()
    assert b.getChessboardSize() == BOARD_SQUARES
    assert abs(b.getSquareLength() - SQUARE_M) < 1e-7
    assert abs(b.getMarkerLength() - MARKER_M) < 1e-7
    assert b.getLegacyPattern() is False
    assert len(b.getChessboardCorners()) == 35


def test_pose_and_metric_depth_object_mask():
    rgb, depth, cal = fixture()
    original_rgb = rgb.copy()
    original_depth = depth.copy()
    pose = detect_charuco_pose(rgb, cal, CharucoIsolationConfig())
    assert isinstance(pose, tuple)
    _, t, marker_count, corners, rmse = pose
    assert marker_count == 24 and corners == 35
    assert rmse < 1.0 and abs(t[2] - 0.9) < 0.01
    result = isolate_charuco_object(rgb, depth, cal)
    assert result.usable and result.selected_pixels == 24 * 25
    assert result.support_fraction > 0.6
    assert result.object_mask[110, 160] and not result.object_mask[75, 170]
    assert not result.object_mask.flags.writeable
    np.testing.assert_array_equal(rgb, original_rgb)
    np.testing.assert_array_equal(depth, original_depth)


def test_board_empty_fail_closed():
    rgb, depth, cal = fixture()
    depth.fill(900)
    result = isolate_charuco_object(rgb, depth, cal)
    assert not result.usable
    assert result.object_mask is None
    assert result.status == 'CHARUCO_NO_RAISED_OBJECT'


def test_board_missing_marker_fail_closed():
    rgb, depth, cal = fixture()
    rgb.fill(127)
    result = isolate_charuco_object(rgb, depth, cal)
    assert result.status == 'CHARUCO_INSUFFICIENT_CORNERS'
    assert result.object_mask is None


def test_depth_roi_preserves_native_pixel_ownership():
    rgb, depth, cal = fixture()
    result = isolate_charuco_object(rgb, depth, cal, depth_roi=(130, 90, 65, 62))
    assert result.usable and 570 <= result.object_mask.sum() <= 600
    result2 = isolate_charuco_object(rgb, depth, cal, depth_roi=(150, 102, 25, 24))
    assert not result2.usable  # no visible board support in tight crop


def test_depth_holes_remain_holes():
    rgb, depth, cal = fixture()
    depth[110, 160] = 0
    depth[112, 160] = 65535
    result = isolate_charuco_object(rgb, depth, cal)
    assert result.usable
    assert not result.object_mask[110, 160]
    assert not result.object_mask[112, 160]


def test_calibration_grid_and_distortion_fail_closed():
    rgb, depth, cal = fixture()
    with pytest.raises(ValueError, match='CHARUCO_DEPTH_GRID_INVALID'):
        isolate_charuco_object(rgb, depth[:, :20], cal)
    cal.depth_distortion = NS(sdk_model=2, k1_k6_p1_p2=(0,) * 8)
    r = isolate_charuco_object(rgb, depth, cal)
    assert r.status == 'CHARUCO_DEPTH_UNPROJECTION_UNSUPPORTED'


def test_bad_board_pose_not_reused():
    rgb, depth, cal = fixture()
    assert isolate_charuco_object(rgb, depth, cal).usable
    rgb.fill(127)
    assert not isolate_charuco_object(rgb, depth, cal).usable


def test_extrinsics_are_used_not_rgb_depth_pixel_alignment():
    rgb, depth, cal = fixture()
    assert isolate_charuco_object(rgb, depth, cal).usable
    cal.translation_C_D_m = (0.12, 0., 0.)
    result = isolate_charuco_object(rgb, depth, cal)
    assert not result.usable or result.selected_pixels < 600


def test_distortion_coefficient_order_sdk_to_opencv():
    _, _, cal = fixture()
    cal.color_distortion = NS(sdk_model=4, k1_k6_p1_p2=(1,2,3,4,5,6,7,8))
    _, d = _camera_model(cal.color_intrinsics, cal.color_distortion)
    assert d.tolist() == [1.,2.,7.,8.,3.,4.,5.,6.]
