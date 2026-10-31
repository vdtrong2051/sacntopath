
"""GD2-10.03: select valid metric XYZ with native-depth pixel lineage.

Pure NumPy; no camera, storage, color mapping, segmentation or RAW writes.
"""
from __future__ import annotations

from dataclasses import dataclass
from math import isfinite

import numpy as np

from .calibration import CalibrationContract
from .unprojection import DepthProjection


class GeometryValidityError(ValueError):
    def __init__(self, code: str, message: str) -> None:
        self.code = code
        super().__init__(message)


@dataclass(frozen=True, slots=True)
class DepthRangePolicy:
    """Optional inclusive depth limits in metres; not accuracy claims."""

    min_depth_m: float = 0.0
    max_depth_m: float | None = None

    def __post_init__(self) -> None:
        def finite_number(value: object) -> bool:
            return type(value) in (int, float) and isfinite(value)

        if not finite_number(self.min_depth_m) or self.min_depth_m < 0:
            raise GeometryValidityError(
                "DEPTH_RANGE_INVALID", "Invalid minimum depth"
            )

        if self.max_depth_m is not None and (
            not finite_number(self.max_depth_m)
            or self.max_depth_m <= self.min_depth_m
        ):
            raise GeometryValidityError(
                "DEPTH_RANGE_INVALID", "Invalid maximum depth"
            )


@dataclass(frozen=True, slots=True)
class GeometryStatistics:
    total_pixels: int
    accepted_points: int
    missing_depth: int
    invalid_geometry: int
    below_min_depth: int
    above_max_depth: int

    @property
    def rejected_points(self) -> int:
        return self.total_pixels - self.accepted_points


@dataclass(frozen=True, slots=True)
class ValidGeometry:
    source_capture_id: str
    points_xyz_m: np.ndarray       # (N,3) float64
    depth_source_uv: np.ndarray    # (N,2) int32, (u,v)
    depth_valid: np.ndarray        # (H,W) bool
    depth_scale_m_per_unit: float
    statistics: GeometryStatistics
    depth_policy: DepthRangePolicy
    provenance: str = "RAW_V2_PER_CAPTURE"
    units: str = "m"
    frame: str = "depth_optical"

    @property
    def invalid_counts(self) -> dict[str, int]:
        return {
            "missing_depth": self.statistics.missing_depth,
            "invalid_geometry": self.statistics.invalid_geometry,
            "below_min_depth": self.statistics.below_min_depth,
            "above_max_depth": self.statistics.above_max_depth,
        }


def select_valid_geometry(
    projection: DepthProjection,
    *,
    calibration: CalibrationContract,
    policy: DepthRangePolicy | None = None,
) -> ValidGeometry:
    """Compact 10.02 XYZ while preserving each accepted depth pixel."""

    if not isinstance(projection, DepthProjection):
        raise GeometryValidityError(
            "PROJECTION_INVALID", "Expected 10.02 DepthProjection"
        )

    if not isinstance(calibration, CalibrationContract):
        raise GeometryValidityError(
            "CALIBRATION_INVALID", "Expected 10.01 calibration"
        )

    if (
        projection.capture_id != calibration.capture_id
        or not projection.capture_id
    ):
        raise GeometryValidityError(
            "CAPTURE_CONTEXT_MISMATCH", "Capture IDs differ"
        )

    if (
        projection.units != "m"
        or projection.frame != "depth_optical"
        or calibration.units != "m"
        or calibration.frame != "depth_optical"
        or calibration.source != "RAW_V2_PER_CAPTURE"
        or not isfinite(calibration.depth_scale_m_per_unit)
        or calibration.depth_scale_m_per_unit <= 0
    ):
        raise GeometryValidityError(
            "CALIBRATION_INVALID", "Unsupported unit/frame/source"
        )

    if policy is None:
        policy = DepthRangePolicy()

    if not isinstance(policy, DepthRangePolicy):
        raise GeometryValidityError(
            "DEPTH_RANGE_INVALID", "Expected DepthRangePolicy"
        )

    xyz = projection.xyz_m
    depth = projection.depth_m
    source_mask = projection.depth_valid_mask
    shape = (
        calibration.depth_K.height,
        calibration.depth_K.width,
    )

    if (
        not isinstance(xyz, np.ndarray)
        or xyz.dtype != np.float64
        or xyz.shape != (*shape, 3)
        or not isinstance(depth, np.ndarray)
        or depth.dtype != np.float64
        or depth.shape != shape
        or not isinstance(source_mask, np.ndarray)
        or source_mask.dtype != np.bool_
        or source_mask.shape != shape
    ):
        raise GeometryValidityError(
            "PROJECTION_INVALID", "Incorrect array shape or dtype"
        )

    if max(shape) >= 2**31:
        raise GeometryValidityError(
            "RESOURCE_LIMIT_EXCEEDED",
            "Pixel index exceeds int32",
        )

    # Distinct rejection categories.
    finite = np.isfinite(depth) & np.isfinite(xyz).all(axis=2)

    consistent_z = np.isclose(
        xyz[..., 2],
        depth,
        rtol=1e-12,
        atol=1e-12,
    )

    geometric = (
        source_mask
        & finite
        & consistent_z
        & (depth > 0)
        & (xyz[..., 2] > 0)
    )

    below = geometric & (depth < policy.min_depth_m)

    if policy.max_depth_m is None:
        above = np.zeros(shape, dtype=np.bool_)
    else:
        above = (
            geometric
            & ~below
            & (depth > policy.max_depth_m)
        )

    accepted = geometric & ~below & ~above

    # np.nonzero returns pixels in stable row-major order.
    rows, cols = np.nonzero(accepted)

    if rows.size == 0:
        raise GeometryValidityError(
            "EMPTY_VALID_DEPTH",
            "No valid metric Depth remains",
        )

    points = np.ascontiguousarray(
        xyz[rows, cols],
        dtype=np.float64,
    )

    uv = np.ascontiguousarray(
        np.column_stack((cols, rows)),
        dtype=np.int32,
    )

    mask = np.array(
        accepted,
        dtype=np.bool_,
        order="C",
        copy=True,
    )

    for array in (points, uv, mask):
        array.setflags(write=False)

    stats = GeometryStatistics(
        total_pixels=int(source_mask.size),
        accepted_points=int(rows.size),
        missing_depth=int(np.count_nonzero(~source_mask)),
        invalid_geometry=int(
            np.count_nonzero(source_mask & ~geometric)
        ),
        below_min_depth=int(np.count_nonzero(below)),
        above_max_depth=int(np.count_nonzero(above)),
    )

    classified = (
        stats.accepted_points
        + stats.missing_depth
        + stats.invalid_geometry
        + stats.below_min_depth
        + stats.above_max_depth
    )

    if classified != stats.total_pixels:
        raise GeometryValidityError(
            "PROJECTION_INVALID",
            "Pixel counts do not partition frame",
        )

    return ValidGeometry(
        source_capture_id=projection.capture_id,
        points_xyz_m=points,
        depth_source_uv=uv,
        depth_valid=mask,
        depth_scale_m_per_unit=calibration.depth_scale_m_per_unit,
        statistics=stats,
        depth_policy=policy,
    )
