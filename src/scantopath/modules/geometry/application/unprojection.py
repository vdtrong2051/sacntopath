
"""GD2-10.02: vectorized metric unprojection on the native Depth grid.

Only rectilinear (Orbbec distortion NONE=0) Depth images are supported here.
Color projection, invalid-point compaction and external camera pose are out of scope.
"""
from __future__ import annotations

from dataclasses import dataclass
from math import isfinite

import numpy as np

from .calibration import CalibrationContract


class DepthProjectionError(ValueError):
    """Stable failure code for the depth-to-XYZ boundary."""

    def __init__(self, code: str, message: str) -> None:
        self.code = code
        super().__init__(message)


@dataclass(frozen=True, slots=True)
class DepthProjection:
    """Dense HxWx3 XYZ grid; invalid Depth pixels contain NaN, not a 3D point.

    Arrays are marked read-only; the original Depth array is never modified.
    The source pixel for each XYZ point is exactly the same [v, u] index.
    """

    capture_id: str
    xyz_m: np.ndarray             # float64, shape (H, W, 3)
    depth_m: np.ndarray           # float64, shape (H, W); zero for missing Depth
    depth_valid_mask: np.ndarray  # bool, shape (H, W); Depth > 0
    units: str = "m"
    frame: str = "depth_optical"


def unproject_depth(
    depth_u16: np.ndarray,
    *,
    calibration: CalibrationContract,
    capture_id: str,
) -> DepthProjection:
    """Convert raw native-grid Y16 Depth to XYZ in depth_optical metres.

    Fail closed if depth lens distortion needs correction; a pinhole equation
    must not be applied to distorted pixels without a supported inverse model.
    10.03 will compact/filter this dense projection into valid geometry.
    """
    if not isinstance(calibration, CalibrationContract):
        raise DepthProjectionError(
            "CALIBRATION_INVALID", "Expected validated CalibrationContract"
        )
    if (
        type(capture_id) is not str
        or capture_id != calibration.capture_id
        or not capture_id
    ):
        raise DepthProjectionError(
            "CAPTURE_CONTEXT_MISMATCH",
            "Depth and calibration Capture IDs differ",
        )
    if calibration.frame != "depth_optical" or calibration.units != "m":
        raise DepthProjectionError(
            "CALIBRATION_INVALID", "Unsupported coordinate frame or unit"
        )
    if calibration.depth_distortion.sdk_model != 0:
        raise DepthProjectionError(
            "DISTORTION_MODEL_UNSUPPORTED",
            "Depth lens distortion requires a separately verified inverse model",
        )
    if any(
        value != 0.0
        for value in calibration.depth_distortion.k1_k6_p1_p2
    ):
        raise DepthProjectionError(
            "DISTORTION_COEFFICIENTS_INVALID",
            "NONE model has nonzero coefficients",
        )

    k = calibration.depth_K
    scale = calibration.depth_scale_m_per_unit
    if (
        not all(
            isfinite(v) for v in (k.fx, k.fy, k.cx, k.cy, scale)
        )
        or k.fx <= 0
        or k.fy <= 0
        or scale <= 0
    ):
        raise DepthProjectionError(
            "CALIBRATION_INVALID",
            "Invalid intrinsics or depth scale",
        )
    if (
        not isinstance(depth_u16, np.ndarray)
        or depth_u16.dtype != np.uint16
        or depth_u16.ndim != 2
        or depth_u16.shape != (k.height, k.width)
        or not depth_u16.flags.c_contiguous
    ):
        raise DepthProjectionError(
            "DEPTH_ARRAY_INVALID",
            "Expected native-grid contiguous uint16 HxW Depth",
        )

    height, width = depth_u16.shape
    mask = depth_u16 != 0
    rows, cols = np.nonzero(mask)

    xyz = np.full(
        (height, width, 3),
        np.nan,
        dtype=np.float64,
    )
    depth_m = np.zeros(
        (height, width),
        dtype=np.float64,
    )

    with np.errstate(
        over="ignore",
        invalid="ignore",
        divide="ignore",
    ):
        z = depth_u16[rows, cols].astype(np.float64) * scale
        x = ((cols.astype(np.float64) - k.cx) / k.fx) * z
        y = ((rows.astype(np.float64) - k.cy) / k.fy) * z

    if (
        not all(
            np.isfinite(component).all()
            for component in (x, y, z)
        )
        or np.any(z <= 0)
    ):
        raise DepthProjectionError(
            "NONFINITE_PROJECTION",
            "Metric projection overflow or underflow",
        )

    xyz[rows, cols, 0] = x
    xyz[rows, cols, 1] = y
    xyz[rows, cols, 2] = z
    depth_m[rows, cols] = z

    for array in (xyz, depth_m, mask):
        array.setflags(write=False)

    return DepthProjection(
        capture_id=capture_id,
        xyz_m=xyz,
        depth_m=depth_m,
        depth_valid_mask=mask,
    )
