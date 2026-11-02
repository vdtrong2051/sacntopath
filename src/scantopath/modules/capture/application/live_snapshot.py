"""FT-06: immutable single-frame Geometry snapshot and atomic disk export.

Pure application/NumPy/Pillow code: no Qt, SDK, SQLite, RAW, VTK or camera I/O.
This is a *processed sampled* geometry mask, NOT the full pre-sampling object mask.
"""
from __future__ import annotations

from dataclasses import dataclass, asdict, is_dataclass
from datetime import datetime, timezone
from hashlib import sha256
from pathlib import Path
import json
import os
import shutil
from uuid import uuid4

import numpy as np


class SnapshotError(ValueError):
    def __init__(self, code: str):
        self.code = code
        super().__init__(code)


@dataclass(frozen=True, slots=True)
class FrozenGeometry:
    cloud: object
    rgb: np.ndarray
    depth: np.ndarray
    depth_mask: np.ndarray
    generation: int
    depth_frame_index: int
    depth_timestamp_us: int
    roi: tuple[int, int, int, int] | None
    scope_mode: str
    reference_mode: str
    denoise_mode: str
    isolation_status: str
    board_corners: int
    board_reprojection_px: float | None
    board_support_fraction: float | None
    camera_name: str
    calibration_snapshot: dict | None
    color_timestamp_us: int
    depth_enhancement_mode: str = 'off'
    board_pose_source: str = 'detected'
    board_pose_age_frames: int = 0


def freeze_geometry(cloud, frame, *, roi, scope_mode: str,
                    reference_mode: str, denoise_mode: str,
                    isolation_status: str, depth_enhancement_mode: str = 'off', board_corners=0,
                    board_reprojection_px=None, board_support_fraction=None,
                    board_pose_source='detected', board_pose_age_frames=0) -> FrozenGeometry:
    """Reject cross-frame/cross-calibration data; mask corresponds exactly to PLY UV."""
    src = frame.source
    if (cloud.camera_generation <= 0 or cloud.depth_frame_index != src.depth_frame_index
            or cloud.color_frame_index != src.color_frame_index
            or cloud.depth_timestamp_us != src.depth_timestamp_us
            or src.calibration is None
            or cloud.calibration_fingerprint != src.calibration.fingerprint
            or cloud.coordinate_frame != 'depth_optical' or cloud.units != 'm'
            or cloud.metric_validated is not False):
        raise SnapshotError('SNAPSHOT_FRAME_MISMATCH')
    if (frame.depth_u16.shape != (src.depth_height, src.depth_width) or
            frame.color_rgb.shape != (src.color_height, src.color_width, 3)):
        raise SnapshotError('SNAPSHOT_DIMENSIONS_INVALID')
    if (scope_mode not in ('scene', 'object') or reference_mode not in ('charuco', 'depth') or
            denoise_mode not in ('off', 'standard') or depth_enhancement_mode not in ('off', 'visual')):
        raise SnapshotError('SNAPSHOT_MODE_INVALID')
    if roi is not None and (type(roi) is not tuple or len(roi) != 4 or
                            any(type(v) is not int for v in roi) or
                            roi[0] < 0 or roi[1] < 0 or roi[2] <= 0 or roi[3] <= 0 or
                            roi[0] + roi[2] > src.depth_width or roi[1] + roi[3] > src.depth_height):
        raise SnapshotError('SNAPSHOT_ROI_INVALID')
    uv = cloud.depth_source_uv
    xyz = cloud.points_xyz_m
    if (uv.shape[0] != xyz.shape[0] or xyz.shape[0] == 0 or xyz.shape[0] > 200000 or
            np.any(uv[:, 0] < 0) or np.any(uv[:, 0] >= src.depth_width) or
            np.any(uv[:, 1] < 0) or np.any(uv[:, 1] >= src.depth_height)):
        raise SnapshotError('SNAPSHOT_POINTS_INVALID')
    # All three arrays owned and read-only, bounded to 200k points + one RGB-D frame.
    rgb = np.array(frame.color_rgb, dtype=np.uint8, order='C', copy=True)
    depth = np.array(frame.depth_u16, dtype=np.uint16, order='C', copy=True)
    mask = np.zeros(depth.shape, dtype=np.uint8)
    mask[uv[:, 1], uv[:, 0]] = 255  # Post-filter/post-sampling lineage, not raw segmentation.
    for arr in (rgb, depth, mask):
        arr.setflags(write=False)
    return FrozenGeometry(
        cloud=cloud, rgb=rgb, depth=depth, depth_mask=mask,
        generation=cloud.camera_generation, depth_frame_index=cloud.depth_frame_index,
        depth_timestamp_us=cloud.depth_timestamp_us, roi=roi, scope_mode=scope_mode,
        reference_mode=reference_mode, denoise_mode=denoise_mode,
        isolation_status=str(isolation_status), board_corners=int(board_corners or 0),
        board_reprojection_px=(float(board_reprojection_px) if board_reprojection_px is not None else None),
        board_support_fraction=(float(board_support_fraction) if board_support_fraction is not None else None),
        camera_name=str(src.device_name),
        calibration_snapshot=asdict(src.calibration) if is_dataclass(src.calibration) else None,
        color_timestamp_us=int(src.color_timestamp_us) if hasattr(src, 'color_timestamp_us') else 0,
        depth_enhancement_mode=depth_enhancement_mode,
        board_pose_source=str(board_pose_source),
        board_pose_age_frames=int(board_pose_age_frames),
    )


def bounds_xyz_mm(frozen: FrozenGeometry) -> tuple[list[float], list[float]]:
    xyz = frozen.cloud.points_xyz_m.astype(np.float64, copy=False)
    mi = np.min(xyz, axis=0) * 1000.0
    ma = np.max(xyz, axis=0) * 1000.0
    return [round(float(x), 3) for x in mi], [round(float(x), 3) for x in ma]


def _binary_ply(xyz: np.ndarray) -> bytes:
    if (xyz.ndim != 2 or xyz.shape[1] != 3 or xyz.dtype != np.dtype('<f4') or
            xyz.shape[0] < 1 or xyz.shape[0] > 200000 or not np.isfinite(xyz).all()):
        raise SnapshotError('SNAPSHOT_PLY_INVALID')
    header = ('ply\nformat binary_little_endian 1.0\n'
              'comment ScanToPath FT-06 single-frame XYZ in depth_optical metres\n'
              f'element vertex {xyz.shape[0]}\n'
              'property float x\nproperty float y\nproperty float z\n'
              'end_header\n')
    return header.encode('ascii') + np.ascontiguousarray(xyz, dtype='<f4').tobytes()


def save_snapshot(frozen: FrozenGeometry, parent_directory: str | Path) -> Path:
    """Create complete, single snapshot directory by same-filesystem atomic rename.

    Caller owns the save-worker thread; GUI thread must not perform disk I/O.
    No modification to existing folders, RAW files or SQLite. Failed temporary
    directory is removed. Parent must exist and cannot be symlink.
    """
    if not isinstance(frozen, FrozenGeometry):
        raise SnapshotError('SNAPSHOT_NOT_FROZEN')
    parent = Path(parent_directory).expanduser()
    if not parent.is_dir() or parent.is_symlink():
        raise SnapshotError('SNAPSHOT_PARENT_INVALID')
    stamp = datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S%fZ')
    name = f'snapshot_{stamp}_g{frozen.generation}_f{frozen.depth_frame_index}'
    final = parent / name
    staging = parent / ('.' + name + '.' + uuid4().hex + '.partial')
    if final.exists():
        raise SnapshotError('SNAPSHOT_ALREADY_EXISTS')
    try:
        staging.mkdir(mode=0o700)
        ply_bytes = _binary_ply(frozen.cloud.points_xyz_m)
        (staging / 'cloud.ply').write_bytes(ply_bytes)
        from PIL import Image
        Image.fromarray(frozen.depth_mask, mode='L').save(staging / 'selected_points_mask.png')
        inferred_count = modified_count = 0
        if frozen.depth_enhancement_mode == 'visual':
            uv = frozen.cloud.depth_source_uv
            estimated = np.zeros(frozen.depth.shape, dtype=np.uint8)
            smoothed = np.zeros(frozen.depth.shape, dtype=np.uint8)
            estimate_flags = getattr(frozen.cloud, 'inferred_depth_mask', None)
            smooth_flags = getattr(frozen.cloud, 'smoothed_depth_mask', None)
            if estimate_flags is None or smooth_flags is None:
                raise SnapshotError('SNAPSHOT_VISUAL_PROVENANCE_MISSING')
            estimated[uv[estimate_flags, 1], uv[estimate_flags, 0]] = 255
            smoothed[uv[smooth_flags, 1], uv[smooth_flags, 0]] = 255
            inferred_count = int(estimate_flags.sum())
            modified_count = int(smooth_flags.sum())
            Image.fromarray(estimated, mode='L').save(staging / 'inferred_points_mask.png')
            Image.fromarray(smoothed, mode='L').save(staging / 'smoothed_points_mask.png')
        minimum, maximum = bounds_xyz_mm(frozen)
        meta = {
            'schema_version': 'ft06.snapshot.v1',
            'type': 'processed_single_frame_point_cloud',
            'created_utc': datetime.now(timezone.utc).isoformat(),
            'camera': frozen.camera_name,
            'camera_generation': frozen.generation,
            'depth_frame_index': frozen.depth_frame_index,
            'color_frame_index': frozen.cloud.color_frame_index,
            'depth_timestamp_us': frozen.depth_timestamp_us,
            'color_timestamp_us': frozen.color_timestamp_us,
            'calibration_snapshot': frozen.calibration_snapshot,
            'calibration_fingerprint_sha256': frozen.cloud.calibration_fingerprint,
            'coordinate_frame': 'depth_optical', 'units': 'm',
            'point_count': int(frozen.cloud.points_xyz_m.shape[0]),
            'bounds_min_xyz_mm': minimum, 'bounds_max_xyz_mm': maximum,
            'bbox_extent_xyz_mm': [round(b-a, 3) for a,b in zip(minimum, maximum)],
            'depth_grid_wh': [int(frozen.depth.shape[1]), int(frozen.depth.shape[0])],
            'roi_depth_xywh': list(frozen.roi) if frozen.roi else None,
            'scope_mode': frozen.scope_mode, 'reference_mode': frozen.reference_mode,
            'denoise_mode': frozen.denoise_mode,
            'depth_enhancement_mode': frozen.depth_enhancement_mode,
            'depth_enhancement_inferred_points': inferred_count,
            'depth_enhancement_smoothed_points': modified_count,
            'depth_enhancement_is_estimated_not_measured': frozen.depth_enhancement_mode == 'visual',
            'ply_includes_estimated_or_smoothed_xyz': inferred_count > 0 or modified_count > 0,
            'original_raw_depth_is_unchanged': True,
            'isolation_status': frozen.isolation_status,
            'board_corners': frozen.board_corners,
            'board_reprojection_px': frozen.board_reprojection_px,
            'board_support_fraction': frozen.board_support_fraction,
            'board_pose_source': frozen.board_pose_source,
            'board_pose_age_frames': frozen.board_pose_age_frames,
            'board_pose_is_estimated': frozen.board_pose_source == 'optical_flow_estimate',
            'mask_semantics': 'selected_post_filter_post_sampling_depth_pixels',
            'point_cloud_source': 'FT-02 processed LiveCloudFrame; not original RAW',
            'semantic_object_identity_verified': False,
            'metric_accuracy_verified': False,
            'multiview_registration': False,
            'cloud_ply_sha256': sha256(ply_bytes).hexdigest(),
        }
        mask_bytes = (staging / 'selected_points_mask.png').read_bytes()
        meta['selected_points_mask_sha256'] = sha256(mask_bytes).hexdigest()
        if frozen.depth_enhancement_mode == 'visual':
            for name in ('inferred_points_mask.png', 'smoothed_points_mask.png'):
                meta[name.replace('.', '_') + '_sha256'] = sha256((staging / name).read_bytes()).hexdigest()
        (staging / 'snapshot.json').write_text(
            json.dumps(meta, ensure_ascii=False, sort_keys=True, indent=2) + '\n', encoding='utf-8')
        # Validate bytes on disk before publish.
        if sha256((staging / 'cloud.ply').read_bytes()).hexdigest() != meta['cloud_ply_sha256']:
            raise SnapshotError('SNAPSHOT_WRITE_MISMATCH')
        os.replace(staging, final)
        return final
    except Exception:
        if staging.exists():
            shutil.rmtree(staging)
        raise
