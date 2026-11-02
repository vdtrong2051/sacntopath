"""FT-08.16 / B-01: explicit two-view geometry and pose contracts.

T_A_B maps coordinates from B into A. No field claims metric validation.
"""
from __future__ import annotations
from dataclasses import dataclass, asdict
from math import isfinite
from typing import Literal
import numpy as np


class RegistrationError(RuntimeError):
    def __init__(self, code: str, message: str) -> None:
        self.code = code
        super().__init__(message)


@dataclass(frozen=True)
class RegistrationConfig:
    # Provisional, adjustable baseline thresholds; NOT a millimetre acceptance gate.
    voxel_scales_m: tuple[float, float, float] = (0.020, 0.010, 0.005)
    correspondences_m: tuple[float, float, float] = (0.050, 0.025, 0.0125)
    iterations: tuple[int, int, int] = (12, 18, 24)
    max_points_per_scale: int = 3200
    max_output_points_per_view: int = 75000
    min_input_points: int = 350
    min_correspondences: int = 80
    min_overlap: float = 0.28
    max_rmse_m: float = 0.009
    max_motion_m: float = 0.40
    min_distinct_view_translation_m: float = 0.006
    min_distinct_view_rotation_deg: float = 1.0
    max_rotation_deg: float = 40.0
    # For very planar or nearly line-like data: do not report a trustworthy 6DoF.
    min_covariance_ratio: float = 0.0015
    coarse_seed_deg: float = 14.0

    def __post_init__(self) -> None:
        if (len(self.voxel_scales_m) != 3 or len(self.correspondences_m) != 3
                or len(self.iterations) != 3):
            raise ValueError("Three ICP scales are required")
        positive = (*self.voxel_scales_m, *self.correspondences_m,
                    self.max_rmse_m, self.max_motion_m, self.coarse_seed_deg,
                    self.min_distinct_view_translation_m, self.min_distinct_view_rotation_deg)
        if any(not isfinite(float(x)) or float(x) <= 0 for x in positive):
            raise ValueError("Invalid registration configuration")
        if not 0 < self.min_overlap <= 1 or not 0 < self.min_covariance_ratio < 1:
            raise ValueError("Invalid overlap/degeneracy configuration")
        if (self.max_points_per_scale < 500 or self.max_output_points_per_view < 500
                or self.min_input_points < 40 or self.min_correspondences < 20
                or any(n < 1 or n > 100 for n in self.iterations)):
            raise ValueError("Unsafe computational bounds")


@dataclass(frozen=True)
class InputCloud:
    capture_id: str
    xyz_depth_m: np.ndarray
    calibration_fingerprint: str
    source_raw_sha256: tuple[tuple[str, str], ...]
    depth_source_uv: np.ndarray | None = None

    def __post_init__(self) -> None:
        points = np.asarray(self.xyz_depth_m)
        if points.ndim != 2 or points.shape[1] != 3 or not np.issubdtype(points.dtype, np.floating):
            raise RegistrationError("CLOUD_INVALID", "Expected floating XYZ Nx3")
        if points.size == 0 or not np.isfinite(points).all():
            raise RegistrationError("CLOUD_INVALID", "Empty or nonfinite depth cloud")
        if not self.capture_id or len(self.calibration_fingerprint) != 64:
            raise RegistrationError("PROVENANCE_INVALID", "Missing capture/calibration identity")
        if self.depth_source_uv is not None:
            uv = np.asarray(self.depth_source_uv)
            if uv.shape != (len(points), 2) or uv.dtype != np.int32:
                raise RegistrationError("PROVENANCE_INVALID", "UV does not match depth points")


@dataclass(frozen=True)
class PairQuality:
    fitness_source: float
    coverage_target: float
    overlap: float
    inlier_rmse_m: float | None
    inlier_count: int
    source_points: int
    target_points: int
    condition_ratio_source: float
    condition_ratio_target: float
    translation_m: float
    rotation_deg: float
    accepted: bool
    reject_reasons: tuple[str, ...]
    method: str = "cpu.multiscale.trimmed_point_to_point_icp"

    def to_json(self) -> dict:
        return asdict(self)


@dataclass(frozen=True)
class TwoViewResult:
    quality: PairQuality
    T_world_depth_0: np.ndarray
    T_world_depth_1: np.ndarray | None
    world_xyz_0: np.ndarray | None
    world_xyz_1: np.ndarray | None
    backend: Literal["scipy_ckdtree", "numpy_bounded_bruteforce"]

    @property
    def accepted(self) -> bool:
        return self.quality.accepted
