"""FT-10.20-22: measured multi-view XYZ accumulation using accepted FT-09 poses.

No pose estimation, re-registration, AI inference, mesh, Qt, camera or SQLite.
The voxel dictionary keeps one original measured point, never a centroid.
"""
from __future__ import annotations

from collections import Counter
from dataclasses import dataclass
from math import floor, isfinite
from typing import Iterable
import numpy as np

from scantopath.modules.reconstruction.application.sequence_tracking import _is_se3


class MultiviewError(ValueError):
    def __init__(self, code: str, detail: str = '') -> None:
        self.code = code
        super().__init__(f'{code}: {detail}' if detail else code)


@dataclass(frozen=True)
class AccumulationConfig:
    voxel_m: float = 0.004
    max_voxel_m: float = 0.032
    max_points: int = 200_000

    def __post_init__(self):
        if (not all(isfinite(v) and v > 0 for v in (self.voxel_m, self.max_voxel_m))
                or self.voxel_m > self.max_voxel_m
                or self.max_voxel_m > 0.05
                or type(self.max_points) is not int
                or not 1_000 <= self.max_points <= 1_500_000):
            raise MultiviewError('FT10_CONFIG_INVALID')


def validated_trajectory(record: dict) -> tuple[list[dict], list[dict]]:
    """Reject mismatched rows and untrusted pose publication before reading RAW.

    This is NOT a source integrity check: caller must separately run the
    existing B02 SHA-256 verifier before and after accumulation.
    """
    if (not isinstance(record, dict)
            or record.get('schema') != 'scantopath.ft08.17.sampled_pose_sequence.v1'
            or record.get('ft09_extension') != 'scantopath.ft09.quality_recovery.v1'
            or record.get('units') != 'm'
            or record.get('trajectory_frame') != 'depth_optical_of_sample_0'
            or record.get('matrix_convention') != 'T_A_B maps coordinates B into A; column homogeneous vectors'
            or record.get('metric_accuracy_verified') is not False
            or record.get('fusion_implemented') is not False):
        raise MultiviewError('FT10_FT09_TRAJECTORY_REQUIRED')
    rows = record.get('frames')
    n = record.get('source_frame_count')
    if type(n) is not int or not 2 <= n <= 20 or not isinstance(rows, list) or len(rows) != n:
        raise MultiviewError('FT10_SEQUENCE_COUNT_INVALID')
    accepted, skipped = [], []
    identities = set()
    last_frame = -1
    last_ts = -1
    for i, row in enumerate(rows):
        if not isinstance(row, dict) or row.get('sample_index') != i:
            raise MultiviewError('FT10_SAMPLE_ORDER_INVALID', str(i))
        capture = row.get('capture_id')
        frame = row.get('depth_frame_index')
        stamp = row.get('depth_timestamp_us')
        if (not isinstance(capture, str) or not capture or capture in identities
                or type(frame) is not int or type(stamp) is not int
                or frame <= last_frame or stamp <= last_ts):
            raise MultiviewError('FT10_CAPTURE_ORDER_INVALID', str(i))
        identities.add(capture)
        last_frame, last_ts = frame, stamp
        trusted = row.get('accepted_for_trajectory')
        state = row.get('status')
        pose = row.get('T_world_depth')
        if type(trusted) is not bool:
            raise MultiviewError('FT10_ACCEPTANCE_INVALID', str(i))
        if trusted:
            if state not in ('ANCHOR', 'TRACKING', 'RECOVERED') or not _is_se3(pose):
                raise MultiviewError('FT10_TRUSTED_POSE_INVALID', str(i))
            transform = np.asarray(pose, dtype=np.float64)
            if i == 0 and not np.allclose(transform, np.eye(4), atol=1e-8):
                raise MultiviewError('FT10_ANCHOR_INVALID')
            accepted.append(row)
        else:
            if state not in ('STATIONARY', 'DEGRADED', 'LOST') or pose is not None:
                raise MultiviewError('FT10_UNTRUSTED_POSE_PUBLISHED', str(i))
            skipped.append({'sample_index': i, 'status': state,
                            'reject_code': row.get('reject_code')})
    if record.get('accepted_poses') != len(accepted) or len(accepted) < 2:
        raise MultiviewError('FT10_INSUFFICIENT_TRUSTED_VIEWS')
    if accepted[0]['sample_index'] != 0 or accepted[0]['status'] != 'ANCHOR':
        raise MultiviewError('FT10_ANCHOR_INVALID')
    return accepted, skipped


class MeasuredVoxelAccumulator:
    """Bounded global voxel map. Coarsens progressively rather than silently dropping data."""

    def __init__(self, config: AccumulationConfig | None = None):
        self.config = config or AccumulationConfig()
        self.voxel_m = self.config.voxel_m
        self.cells: dict[tuple[int, int, int], tuple[float, float, float, int]] = {}
        self.input_points = 0
        self.promotions = 0
        self._processed_views = set()

    def _key(self, point: tuple[float, float, float, int]):
        return (floor(point[0] / self.voxel_m),
                floor(point[1] / self.voxel_m),
                floor(point[2] / self.voxel_m))

    def _coarsen(self):
        if self.voxel_m >= self.config.max_voxel_m * (1. - 1e-12):
            raise MultiviewError('FT10_RESOURCE_BUDGET_EXCEEDED',
                                 'Number of distinct voxels exceeds configured budget')
        self.voxel_m = min(self.voxel_m * 2, self.config.max_voxel_m)
        reduced = {}
        for point in self.cells.values():
            reduced.setdefault(self._key(point), point)
        self.cells = reduced
        self.promotions += 1

    def insert(self, sample_index: int, xyz_m: np.ndarray, T_world_depth: np.ndarray) -> dict:
        if sample_index in self._processed_views:
            raise MultiviewError('FT10_DUPLICATE_VIEW')
        if not _is_se3(T_world_depth):
            raise MultiviewError('FT10_POSE_INVALID')
        xyz = np.asarray(xyz_m, dtype=np.float64)
        if xyz.ndim != 2 or xyz.shape[1] != 3 or len(xyz) == 0 or not np.isfinite(xyz).all():
            raise MultiviewError('FT10_MEASURED_XYZ_INVALID')
        mapped = xyz @ T_world_depth[:3, :3].T + T_world_depth[:3, 3]
        if not np.isfinite(mapped).all():
            raise MultiviewError('FT10_TRANSFORM_OVERFLOW')
        before = len(self.cells)
        for x, y, z in mapped:
            point = (float(x), float(y), float(z), sample_index)
            self.cells.setdefault(self._key(point), point)
            if len(self.cells) > self.config.max_points:
                self._coarsen()
                # Depending on voxel distribution, one promotion may not suffice.
                while len(self.cells) > self.config.max_points:
                    self._coarsen()
        self.input_points += len(mapped)
        self._processed_views.add(sample_index)
        return {'sample_index': sample_index, 'measured_points': len(mapped),
                'accumulated_voxels_after_view': len(self.cells),
                'voxel_size_m_after_view': self.voxel_m,
                'net_voxel_delta_after_view': len(self.cells)-before}

    def result(self) -> tuple[np.ndarray, np.ndarray]:
        if len(self._processed_views) < 2 or not self.cells:
            raise MultiviewError('FT10_INSUFFICIENT_MEASURED_VIEWS')
        values = list(self.cells.values())
        xyz = np.array([(p[0],p[1],p[2]) for p in values], dtype=np.float64)
        ids = np.asarray([p[3] for p in values], dtype=np.int32)
        return xyz, ids

    def diagnostics(self, retained_ids: np.ndarray) -> dict:
        counts = Counter(int(i) for i in retained_ids)
        return {
            'raw_measured_points_total': self.input_points,
            'merged_measured_points': len(self.cells),
            'effective_voxel_m': self.voxel_m,
            'adaptive_voxel_promotions': self.promotions,
            'retained_points_by_source_sample': {str(k): v for k, v in sorted(counts.items())},
            'representative_policy': 'FIRST_MEASURED_POINT_PER_GLOBAL_VOXEL_NO_CENTROIDS',
            'voxel_collisions_total': self.input_points - len(self.cells),
            'coverage_absolute_verified': False,
        }
