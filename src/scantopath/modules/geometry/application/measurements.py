
"""GD2-10.06: provisional two-point distance in a single depth-optical cloud.

No object dimensions, camera pose, UI, storage or physical accuracy claims.
"""
from __future__ import annotations

from dataclasses import dataclass
from hashlib import sha256
from math import dist, isfinite

import numpy as np

from .validity import ValidGeometry
from .service import SingleViewXYZRGB


class MeasurementError(ValueError):
    def __init__(self, code: str, message: str) -> None:
        self.code = code
        super().__init__(message)


@dataclass(frozen=True, slots=True)
class PointSelection:
    point_index: int
    xyz_m: tuple[float, float, float]
    source_capture_id: str
    cloud_revision_sha256: str
    frame: str
    units: str


@dataclass(frozen=True, slots=True)
class MeasurementResult:
    source_capture_id: str
    cloud_revision_sha256: str
    point_indices: tuple[int, int]
    first_xyz_m: tuple[float, float, float]
    second_xyz_m: tuple[float, float, float]
    distance_m: float
    distance_mm: float
    frame: str = "depth_optical"
    units: str = "m"
    status: str = "PROVISIONAL_NOT_METRIC_VALIDATED"
    warning: str = (
        "Single-view camera-frame point distance; not a validated physical "
        "dimension or whole-object measurement."
    )


def _geometry(
    source: ValidGeometry | SingleViewXYZRGB,
) -> ValidGeometry:
    if isinstance(source, SingleViewXYZRGB):
        return source.geometry

    if isinstance(source, ValidGeometry):
        return source

    raise MeasurementError(
        "MEASUREMENT_INPUT_INVALID",
        "Expected a geometry cloud",
    )


def select_measurement_point(
    cloud: ValidGeometry | SingleViewXYZRGB,
    point_index: int,
) -> PointSelection:
    """Snapshot a validated point with a content-derived cloud revision."""

    geometry = _geometry(cloud)

    xyz = geometry.points_xyz_m
    uv = geometry.depth_source_uv
    mask = geometry.depth_valid

    if (
        not isinstance(xyz, np.ndarray)
        or xyz.dtype != np.float64
        or xyz.ndim != 2
        or xyz.shape[1] != 3
        or xyz.shape[0] == 0
        or not xyz.flags.c_contiguous
        or not isinstance(uv, np.ndarray)
        or uv.dtype != np.int32
        or uv.shape != (xyz.shape[0], 2)
        or not uv.flags.c_contiguous
        or not isinstance(mask, np.ndarray)
        or mask.dtype != np.bool_
        or mask.ndim != 2
        or not mask.flags.c_contiguous
        or geometry.frame != "depth_optical"
        or geometry.units != "m"
        or not isinstance(geometry.source_capture_id, str)
        or not geometry.source_capture_id
        or geometry.provenance != "RAW_V2_PER_CAPTURE"
        or not isfinite(geometry.depth_scale_m_per_unit)
        or geometry.depth_scale_m_per_unit <= 0
    ):
        raise MeasurementError(
            "MEASUREMENT_INPUT_INVALID",
            "Invalid metric cloud contract",
        )

    if (
        type(point_index) is not int
        or not 0 <= point_index < xyz.shape[0]
    ):
        raise MeasurementError(
            "MEASUREMENT_POINT_INVALID",
            "Point index outside cloud",
        )

    p = xyz[point_index]
    u, v = (int(value) for value in uv[point_index])

    if (
        not np.isfinite(p).all()
        or p[2] <= 0
        or u < 0
        or v < 0
        or v >= mask.shape[0]
        or u >= mask.shape[1]
        or not mask[v, u]
    ):
        raise MeasurementError(
            "MEASUREMENT_POINT_INVALID",
            "Invalid selected point",
        )

    # Include the whole geometry and Depth-pixel lineage.
    # A changed point cloud invalidates selections from the prior revision.
    h = sha256()

    for value in (
        "GD2-10.06-geometry-v1",
        geometry.source_capture_id,
        geometry.frame,
        geometry.units,
        geometry.provenance,
        repr(float(geometry.depth_scale_m_per_unit)),
        repr(geometry.depth_policy.min_depth_m),
        repr(geometry.depth_policy.max_depth_m),
    ):
        h.update(value.encode("utf-8") + b"\0")

    for array in (xyz, uv, mask):
        h.update(repr(array.shape).encode("ascii") + b"\0")
        h.update(memoryview(array).cast("B"))

    return PointSelection(
        point_index=point_index,
        xyz_m=tuple(float(value) for value in p),
        source_capture_id=geometry.source_capture_id,
        cloud_revision_sha256=h.hexdigest(),
        frame=geometry.frame,
        units=geometry.units,
    )


def measure_selected_points(
    first: PointSelection,
    second: PointSelection,
) -> MeasurementResult:
    """Reject mixed Capture/frame/units/revision or stale selections."""

    if (
        not isinstance(first, PointSelection)
        or not isinstance(second, PointSelection)
    ):
        raise MeasurementError(
            "MEASUREMENT_INPUT_INVALID",
            "Expected two point selections",
        )

    if (
        not first.source_capture_id
        or first.source_capture_id != second.source_capture_id
        or first.frame != "depth_optical"
        or second.frame != "depth_optical"
        or first.units != "m"
        or second.units != "m"
        or len(first.cloud_revision_sha256) != 64
        or first.cloud_revision_sha256 != second.cloud_revision_sha256
    ):
        raise MeasurementError(
            "MEASUREMENT_FRAME_MISMATCH",
            "Selections must belong to the same cloud revision",
        )

    if (
        any(
            type(s.point_index) is not int or s.point_index < 0
            for s in (first, second)
        )
        or any(
            len(s.xyz_m) != 3
            or not all(isfinite(v) for v in s.xyz_m)
            or s.xyz_m[2] <= 0
            for s in (first, second)
        )
    ):
        raise MeasurementError(
            "MEASUREMENT_POINT_INVALID",
            "Invalid selection coordinates",
        )

    distance_m = dist(first.xyz_m, second.xyz_m)
    distance_mm = distance_m * 1000.0

    if not isfinite(distance_m) or not isfinite(distance_mm):
        raise MeasurementError(
            "MEASUREMENT_NONFINITE",
            "Distance is not finite",
        )

    return MeasurementResult(
        source_capture_id=first.source_capture_id,
        cloud_revision_sha256=first.cloud_revision_sha256,
        point_indices=(first.point_index, second.point_index),
        first_xyz_m=first.xyz_m,
        second_xyz_m=second.xyz_m,
        distance_m=distance_m,
        distance_mm=distance_mm,
    )


def measure_points(
    cloud: ValidGeometry | SingleViewXYZRGB,
    first_index: int,
    second_index: int,
) -> MeasurementResult:
    """Convenience API: both indices are resolved from the same cloud."""

    return measure_selected_points(
        select_measurement_point(cloud, first_index),
        select_measurement_point(cloud, second_index),
    )
