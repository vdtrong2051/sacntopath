"""FT-05.8: conservative ChArUco-guided object isolation, read-only live data.

PDF board: 6x8, 45 mm square, 33.3 mm marker, DICT_5X5_100,
modern OpenCV pattern (setLegacyPattern(False)). The board is NOT a robot frame.
Never modify RGB/Depth/RAW, align image grids, or claim metric validation.
"""
from __future__ import annotations

from dataclasses import dataclass
from math import isfinite

import numpy as np

BOARD_SQUARES = (6, 8)
SQUARE_M = 0.045
MARKER_M = 0.0333
BOARD_M = (0.27, 0.36)


@dataclass(frozen=True, slots=True)
class CharucoIsolationConfig:
    min_corners: int = 7
    max_reprojection_px: float = 3.0
    support_tolerance_m: float = 0.012
    min_support_fraction: float = 0.16
    object_clearance_m: float = 0.015
    max_object_height_m: float = 0.30
    min_object_cells: int = 10
    sample_step: int = 3
    footprint_margin_m: float = 0.005

    def __post_init__(self):
        if (type(self.min_corners) is not int or not 6 <= self.min_corners <= 35 or
                type(self.min_object_cells) is not int or not 4 <= self.min_object_cells <= 4096 or
                type(self.sample_step) is not int or not 2 <= self.sample_step <= 12):
            raise ValueError('CHARUCO_CONFIG_INVALID')
        for name in ('max_reprojection_px', 'support_tolerance_m',
                     'min_support_fraction', 'object_clearance_m',
                     'max_object_height_m', 'footprint_margin_m'):
            x = getattr(self, name)
            if type(x) not in (float, int) or not isfinite(x) or x <= 0:
                raise ValueError('CHARUCO_CONFIG_INVALID')
        if (self.object_clearance_m <= self.support_tolerance_m or
                self.max_object_height_m <= self.object_clearance_m or
                not 0 < self.min_support_fraction < 0.9 or
                self.footprint_margin_m >= 0.02):
            raise ValueError('CHARUCO_CONFIG_INVALID')


@dataclass(frozen=True, slots=True)
class CharucoIsolationResult:
    status: str
    object_mask: np.ndarray | None
    marker_count: int
    corner_count: int
    reprojection_px: float | None
    support_fraction: float
    selected_pixels: int
    message: str

    @property
    def usable(self) -> bool:
        return self.status == 'CHARUCO_OBJECT_FOUND' and self.object_mask is not None


def _fail(code: str, markers: int = 0, corners: int = 0,
          reproj: float | None = None, support: float = 0.) -> CharucoIsolationResult:
    return CharucoIsolationResult(code, None, markers, corners, reproj,
                                  round(support, 4), 0, code)


def _camera_model(intrinsics, distortion):
    # SDK k1..k6,p1,p2 to OpenCV k1,k2,p1,p2,k3,k4,k5,k6.
    if distortion.sdk_model not in (0, 4):
        raise ValueError('CHARUCO_DISTORTION_UNSUPPORTED')
    v = tuple(distortion.k1_k6_p1_p2)
    if distortion.sdk_model == 0 and any(abs(x) > 0 for x in v):
        raise ValueError('CHARUCO_DISTORTION_UNSUPPORTED')
    k = np.array([[intrinsics.fx, 0, intrinsics.cx],
                  [0, intrinsics.fy, intrinsics.cy], [0, 0, 1]], dtype=np.float64)
    d = np.asarray((v[0], v[1], v[6], v[7], v[2], v[3], v[4], v[5]), dtype=np.float64)
    if not (np.isfinite(k).all() and np.isfinite(d).all()):
        raise ValueError('CHARUCO_CALIBRATION_INVALID')
    return k, d


def _board():
    import cv2
    if not hasattr(cv2, 'aruco') or not hasattr(cv2.aruco, 'CharucoDetector'):
        raise ImportError('opencv-contrib-python CharucoDetector unavailable')
    dictionary = cv2.aruco.getPredefinedDictionary(cv2.aruco.DICT_5X5_100)
    board = cv2.aruco.CharucoBoard(BOARD_SQUARES, SQUARE_M, MARKER_M, dictionary)
    board.setLegacyPattern(False)  # confirmed by actual uploaded PDF
    return board, cv2.aruco.CharucoDetector(board)


def detect_charuco_pose(color_rgb: np.ndarray, calibration, cfg: CharucoIsolationConfig):
    """Returns (R_C_B, t_C_B, markers, corners, reproj) or a stable failure code."""
    import cv2
    if (not isinstance(color_rgb, np.ndarray) or color_rgb.dtype != np.uint8 or
            color_rgb.ndim != 3 or color_rgb.shape[2] != 3 or
            color_rgb.shape[:2] != (calibration.color_intrinsics.height,
                                    calibration.color_intrinsics.width)):
        raise ValueError('CHARUCO_COLOR_GRID_MISMATCH')
    k, d = _camera_model(calibration.color_intrinsics, calibration.color_distortion)
    board, detector = _board()
    gray = cv2.cvtColor(np.ascontiguousarray(color_rgb), cv2.COLOR_RGB2GRAY)
    corners, ids, marker_corners, marker_ids = detector.detectBoard(gray)
    markers = 0 if marker_ids is None else len(marker_ids)
    num = 0 if ids is None else len(ids)
    if num < cfg.min_corners:
        return _fail('CHARUCO_INSUFFICIENT_CORNERS', markers, num)
    if len(np.unique(ids)) != num or ids.min() < 0 or ids.max() >= 35:
        return _fail('CHARUCO_IDS_INVALID', markers, num)
    if board.checkCharucoCornersCollinear(ids):
        return _fail('CHARUCO_CORNERS_COLLINEAR', markers, num)
    obj, img = board.matchImagePoints(corners, ids)
    success, rvec, tvec = cv2.solvePnP(obj, img, k, d, flags=cv2.SOLVEPNP_ITERATIVE)
    if not success:
        return _fail('CHARUCO_POSE_FAILED', markers, num)
    projected, _ = cv2.projectPoints(obj, rvec, tvec, k, d)
    err = float(np.sqrt(np.mean(np.sum((projected.reshape(-1, 2) -
                                      img.reshape(-1, 2)) ** 2, axis=1))))
    if not isfinite(err) or err > cfg.max_reprojection_px:
        return _fail('CHARUCO_POSE_UNTRUSTED', markers, num, err)
    R, _ = cv2.Rodrigues(rvec)
    t = np.asarray(tvec, dtype=np.float64).reshape(3)
    if not np.isfinite(R).all() or not np.isfinite(t).all() or t[2] <= 0.10:
        return _fail('CHARUCO_POSE_UNTRUSTED', markers, num, err)
    # Require 2-D spatial spread of the detected board corners, not a tight cluster.
    obj_xy = np.asarray(obj, dtype=np.float64).reshape(-1, 3)[:, :2]
    spread = np.ptp(obj_xy, axis=0)
    if spread[0] < .07 or spread[1] < .09:
        return _fail('CHARUCO_POSE_UNTRUSTED', markers, num, err)
    return R, t, markers, num, err


def _coords(depth: np.ndarray, ys, xs, intr, scale):
    z = depth[ys, xs].astype(np.float64) * scale
    return np.stack(((xs - intr.cx) / intr.fx * z,
                     (ys - intr.cy) / intr.fy * z, z), axis=-1)


def isolate_charuco_object(color_rgb: np.ndarray, depth_u16: np.ndarray,
                           calibration, *, depth_roi=None,
                           config: CharucoIsolationConfig | None = None):
    """Map calibrated RGB board plane to native Depth; produce Depth-native mask.

    Only per-frameset calibration. No temporal pose reuse, RGB/Depth pixel alignment,
    independent camera acquisition, SQLite writes, RAW mutation or semantic identity.
    """
    cfg = config or CharucoIsolationConfig()
    if (not isinstance(depth_u16, np.ndarray) or depth_u16.dtype != np.uint16 or
            depth_u16.ndim != 2 or depth_u16.size == 0 or depth_u16.size > 32_000_000 or
            calibration is None or depth_u16.shape != (calibration.depth_intrinsics.height,
                                                       calibration.depth_intrinsics.width)):
        raise ValueError('CHARUCO_DEPTH_GRID_INVALID')
    if (calibration.alignment_mode != 'disabled' or
            calibration.coordinate_frame != 'depth_optical' or
            calibration.depth_scale_m_per_unit <= 0):
        raise ValueError('CHARUCO_CALIBRATION_INVALID')
    dmod = calibration.depth_distortion
    if dmod.sdk_model not in (0, 4) or any(v != 0 for v in dmod.k1_k6_p1_p2):
        return _fail('CHARUCO_DEPTH_UNPROJECTION_UNSUPPORTED')
    height, width = depth_u16.shape
    if depth_roi is None:
        x, y, rw, rh = 0, 0, width, height
    else:
        if (not isinstance(depth_roi, tuple) or len(depth_roi) != 4 or
                any(type(v) is not int for v in depth_roi)):
            raise ValueError('CHARUCO_ROI_INVALID')
        x, y, rw, rh = depth_roi
        if x < 0 or y < 0 or rw < 4 or rh < 4 or x + rw > width or y + rh > height:
            raise ValueError('CHARUCO_ROI_INVALID')
    try:
        pose = detect_charuco_pose(color_rgb, calibration, cfg)
    except ImportError:
        return _fail('CHARUCO_OPENCV_MISSING')
    except ValueError as exc:
        return _fail(str(exc) if str(exc).startswith('CHARUCO_') else 'CHARUCO_DETECTION_INVALID')
    except Exception:
        # CV native failures should not tear down camera or RAW.
        return _fail('CHARUCO_DETECTION_FAILED')
    if isinstance(pose, CharucoIsolationResult):
        return pose
    R_CB, t_CB, markers, corners, err = pose
    R_CD = np.asarray(calibration.rotation_C_D, dtype=np.float64).reshape(3, 3)
    t_CD = np.asarray(calibration.translation_C_D_m, dtype=np.float64)
    # Choose board normal facing camera (origin of COLOR optical frame).
    normal = R_CB[:, 2]
    if float(normal @ (-t_CB)) < 0:
        normal = -normal
    k = calibration.depth_intrinsics
    scale = float(calibration.depth_scale_m_per_unit)

    def classify(ys, xs):
        pd = _coords(depth_u16, ys, xs, k, scale)
        pc = pd @ R_CD.T + t_CD  # T_color_from_depth, no RGB/Depth grid alignment
        pb = (pc - t_CB) @ R_CB   # inverse board rotation (row vectors)
        inside = ((pb[..., 0] >= -cfg.footprint_margin_m) &
                  (pb[..., 0] <= BOARD_M[0] + cfg.footprint_margin_m) &
                  (pb[..., 1] >= -cfg.footprint_margin_m) &
                  (pb[..., 1] <= BOARD_M[1] + cfg.footprint_margin_m))
        h = (pc - t_CB) @ normal
        valid = ((depth_u16[ys, xs] != 0) & (depth_u16[ys, xs] != 65535) &
                 (pd[..., 2] >= 0.18) & (pd[..., 2] <= 3.0))
        return inside & valid, h

    step = cfg.sample_step
    yy, xx = np.mgrid[y:y+rh:step, x:x+rw:step]
    inside, heights = classify(yy, xx)
    near = inside & (np.abs(heights) <= cfg.support_tolerance_m)
    fg = inside & (heights > cfg.object_clearance_m) & (heights <= cfg.max_object_height_m)
    count = int(inside.sum())
    support = float(near.sum()) / max(count, 1)
    if count < 100 or support < cfg.min_support_fraction:
        return _fail('CHARUCO_DEPTH_PLANE_UNVERIFIED', markers, corners, err, support)
    if int(fg.sum()) < cfg.min_object_cells:
        return _fail('CHARUCO_NO_RAISED_OBJECT', markers, corners, err, support)
    if float(fg.sum()) / max(count, 1) > 0.6:
        return _fail('CHARUCO_FOREGROUND_AMBIGUOUS', markers, corners, err, support)
    import cv2
    number, labels, stats, _ = cv2.connectedComponentsWithStats(
        fg.astype(np.uint8), connectivity=8)
    large = [i for i in range(1, number) if stats[i, cv2.CC_STAT_AREA] >= cfg.min_object_cells]
    if not large:
        return _fail('CHARUCO_NO_CONNECTED_OBJECT', markers, corners, err, support)
    large.sort(key=lambda i: int(stats[i, cv2.CC_STAT_AREA]), reverse=True)
    first = int(stats[large[0], cv2.CC_STAT_AREA])
    if len(large) > 1 and stats[large[1], cv2.CC_STAT_AREA] >= 0.60 * first:
        return _fail('CHARUCO_AMBIGUOUS_OBJECTS', markers, corners, err, support)
    component = labels == large[0]
    # Do not invent depth: keep only native measurements meeting plane/footprint constraints.
    expanded = np.repeat(np.repeat(component, step, 0), step, 1)[:rh, :rw]
    yf, xf = np.mgrid[y:y+rh, x:x+rw]
    good, high = classify(yf, xf)
    local = expanded & good & (high > cfg.object_clearance_m) & (high <= cfg.max_object_height_m)
    selected = int(local.sum())
    if selected < cfg.min_object_cells * 3:
        return _fail('CHARUCO_NO_CONNECTED_OBJECT', markers, corners, err, support)
    mask = np.zeros(depth_u16.shape, dtype=bool)
    mask[y:y+rh, x:x+rw] = local
    mask.setflags(write=False)
    return CharucoIsolationResult('CHARUCO_OBJECT_FOUND', mask, markers, corners, err,
                                  round(support, 4), selected, 'CHARUCO_OBJECT_FOUND')
