"""B-01 add-only, atomic diagnostic artifact; NOT a FT-07 snapshot/ProcessingRun.

Writes outside a RAW project store. Hashes every exported product. No SQLite.
"""
from __future__ import annotations
from dataclasses import asdict
from datetime import datetime, timezone
from hashlib import sha256
from pathlib import Path
from uuid import uuid4
import json
import os
import shutil
import numpy as np

from ..application.contracts import RegistrationError, RegistrationConfig, TwoViewResult


def _ply(points: np.ndarray, colors: np.ndarray | None = None) -> bytes:
    n = len(points)
    if n == 0 or n > 1_500_000 or points.shape != (n, 3) or not np.isfinite(points).all():
        raise RegistrationError('PLY_INVALID', 'Invalid bounded XYZ output')
    header = ["ply", "format binary_little_endian 1.0", "comment ScanToPath B-01 metric-unverified",
              f"element vertex {n}", "property float x", "property float y", "property float z"]
    if colors is not None:
        if colors.shape != (n, 3) or colors.dtype != np.uint8:
            raise RegistrationError('PLY_INVALID', 'Invalid RGB overlay')
        header.extend(["property uchar red", "property uchar green", "property uchar blue"])
    header.append("end_header")
    head = ('\n'.join(header) + '\n').encode('ascii')
    if colors is None:
        return head + np.ascontiguousarray(points, dtype='<f4').tobytes()
    rec = np.empty(n, dtype=[('x', '<f4'), ('y', '<f4'), ('z', '<f4'),
                             ('red', 'u1'), ('green', 'u1'), ('blue', 'u1')])
    for k, axis in enumerate(('x', 'y', 'z')):
        rec[axis] = points[:, k]
    for k, channel in enumerate(('red', 'green', 'blue')):
        rec[channel] = colors[:, k]
    return head + rec.tobytes()


def _json_bytes(record: dict) -> bytes:
    return (json.dumps(record, ensure_ascii=False, sort_keys=True, indent=2,
                       allow_nan=False) + '\n').encode('utf-8')


def write_pair_artifact(output_parent: str | Path, *, store_root: str | Path,
                        source0: dict, source1: dict, result: TwoViewResult,
                        config: RegistrationConfig, code_version: str = 'FT08.16-B01-v1') -> Path:
    parent = Path(output_parent).absolute()
    store = Path(store_root).resolve(strict=True)
    if parent.is_symlink() or (hasattr(parent, 'is_junction') and parent.is_junction()):
        raise RegistrationError('UNSAFE_OUTPUT', 'Output directory must not be a symlink/junction')
    candidate = parent.resolve(strict=False)
    # No directory creation before both forbidden destinations are rejected.
    repo = Path(__file__).resolve().parents[5]
    if (candidate == store or candidate.is_relative_to(store)
            or candidate == repo or candidate.is_relative_to(repo)):
        raise RegistrationError('UNREGISTERED_STORE_ARTIFACT',
                                'B-01 output must be outside RAW store and repository')
    parent.mkdir(parents=True, exist_ok=True)
    parent = parent.resolve(strict=True)
    if (result.accepted and (result.world_xyz_0 is None or result.world_xyz_1 is None
                             or result.T_world_depth_1 is None)):
        raise RegistrationError('OUTPUT_INVALID', 'Accepted pose/cloud missing')
    artifact_id = uuid4().hex
    path = parent / ('b01_' + artifact_id[:12])
    staging = parent / ('.b01-partial-' + artifact_id)
    staging.mkdir(exist_ok=False)
    record = {
        'schema': 'scantopath.b01.two_view.v1',
        'created_utc': datetime.now(timezone.utc).isoformat(),
        'algorithm': result.quality.method,
        'version': code_version,
        'backend': result.backend,
        'state': 'ACCEPTED' if result.accepted else 'REJECTED',
        'registration_quality': result.quality.to_json(),
        'provisional_thresholds': asdict(config),
        'source_views': [source0, source1],
        'coordinate_convention': 'T_A_B maps B->A; column homogeneous vectors',
        'world_frame': 'depth_optical_of_capture_0',
        'depth_units': 'm',
        'point_provenance': 'MEASURED_RAW transformed by REGISTERED_ESTIMATED_POSE',
        'rgb_depth_alignment': 'native grids separate; geometry from depth only',
        'metric_accuracy_verified': False,
        'AI_ESTIMATED_points': 0,
        'robot_executable': False,
        'processing_run_registered_in_sqlite': False,
        'output_sha256': {},
    }
    try:
        if result.accepted:
            p0, p1 = result.world_xyz_0, result.world_xyz_1
            merged = np.concatenate((p0, p1), axis=0)
            if len(merged) > 1_500_000:
                raise RegistrationError('OUTPUT_TOO_LARGE', 'Exceeds viewer point limit')
            overlay = np.empty((len(merged), 3), dtype=np.uint8)
            overlay[:len(p0)] = (232, 98, 72)
            overlay[len(p0):] = (65, 163, 242)
            outputs = {'registered_measured.ply': _ply(merged),
                       'debug_pair_overlay.ply': _ply(merged, overlay)}
            pose = {
                'coordinate_frame': 'world=depth_optical_of_capture_0',
                'units': 'm',
                'T_A_B_convention': 'B -> A',
                'T_world_depth_0': result.T_world_depth_0.tolist(),
                'T_world_depth_1': result.T_world_depth_1.tolist(),
                'pose_estimated': True,
                'capture_ids': [source0['capture_id'], source1['capture_id']],
            }
            outputs['poses.json'] = _json_bytes(pose)
            record['registered_measured_points'] = len(merged)
        else:
            outputs = {}
            record['registered_measured_points'] = 0
        for name, contents in outputs.items():
            (staging / name).write_bytes(contents)
            record['output_sha256'][name] = sha256(contents).hexdigest()
        (staging / 'registration_record.json').write_bytes(_json_bytes(record))
        for name, digest in record['output_sha256'].items():
            if sha256((staging / name).read_bytes()).hexdigest() != digest:
                raise RegistrationError('OUTPUT_CHECKSUM_FAILED', name)
        os.replace(staging, path)
        return path
    except BaseException:
        shutil.rmtree(staging, ignore_errors=True)
        raise
