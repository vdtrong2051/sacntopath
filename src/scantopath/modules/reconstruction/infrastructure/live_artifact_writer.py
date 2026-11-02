"""Atomic, store-independent evidence for two *new* Gemini 2 live frames.

Not a Project Capture/FT07 snapshot. Never writes SQLite or existing RAW trees.
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

from scantopath.acquisition.raw_rgbd import RawRgbdCapture
from scantopath.modules.reconstruction.application.contracts import (
    RegistrationError, RegistrationConfig, TwoViewResult,
)
from scantopath.modules.reconstruction.application.live_pair import LivePairView
from scantopath.modules.reconstruction.infrastructure.artifact_writer import _json_bytes, _ply


def _safe_output_parent(path: str | Path) -> Path:
    requested = Path(path).absolute()
    repo = Path(__file__).resolve().parents[5]
    resolved = requested.resolve(strict=False)
    if resolved == repo or resolved.is_relative_to(repo):
        raise RegistrationError('UNSAFE_OUTPUT', 'Live evidence must be saved outside Git worktree')
    for ancestor in (requested, *requested.parents):
        if ancestor.is_symlink() or (hasattr(ancestor, 'is_junction') and ancestor.is_junction()):
            raise RegistrationError('UNSAFE_OUTPUT', 'Symlink or junction output path not allowed')
    requested.mkdir(parents=True, exist_ok=True)
    return requested.resolve(strict=True)


def _write(staging: Path, name: str, contents: bytes, hashes: dict[str, str]):
    if '/' in name or '\\' in name or name in ('', '.', '..'):
        raise RegistrationError('UNSAFE_ARTIFACT_NAME', 'Invalid evidence filename')
    target = staging / name
    with target.open('xb') as f:
        f.write(contents)
    digest = sha256(contents).hexdigest()
    if sha256(target.read_bytes()).hexdigest() != digest:
        raise RegistrationError('OUTPUT_CHECKSUM_FAILED', name)
    hashes[name] = digest


def write_live_pair_artifact(output_parent: str | Path, *,
                             packet0: RawRgbdCapture, packet1: RawRgbdCapture,
                             view0: LivePairView, view1: LivePairView,
                             result: TwoViewResult, config: RegistrationConfig) -> Path:
    parent = _safe_output_parent(output_parent)
    artifact_id = uuid4().hex
    path = parent / ('b01_live_' + artifact_id[:12])
    staging = parent / ('.b01-live-partial-' + artifact_id)
    staging.mkdir(exist_ok=False)
    hashes: dict[str, str] = {}
    status = 'ACCEPTED' if result.accepted else 'REJECTED'
    try:
        # Preserve exactly the newly acquired sensor bytes, so a REJECT can be
        # independently analyzed/replayed without using any pre-existing store.
        for n, packet in enumerate((packet0, packet1)):
            _write(staging, f'view{n}_color.mjpg', packet.color_mjpeg, hashes)
            _write(staging, f'view{n}_depth.y16', packet.depth_y16_le, hashes)
            _write(staging, f'view{n}_metadata.json',
                   (packet.metadata.model_dump_json(indent=2) + '\n').encode('utf-8'), hashes)
        if result.accepted:
            if result.world_xyz_0 is None or result.world_xyz_1 is None or result.T_world_depth_1 is None:
                raise RegistrationError('OUTPUT_INVALID', 'Accepted pair lacks transform/cloud')
            p0, p1 = result.world_xyz_0, result.world_xyz_1
            merged = np.concatenate((p0, p1), axis=0)
            if len(merged) > 1_500_000:
                raise RegistrationError('OUTPUT_TOO_LARGE', 'PLY exceeds Qt viewer limit')
            colors = np.empty((len(merged), 3), dtype=np.uint8)
            colors[:len(p0)] = (232, 98, 72)
            colors[len(p0):] = (65, 163, 242)
            _write(staging, 'registered_measured.ply', _ply(merged), hashes)
            _write(staging, 'debug_pair_overlay.ply', _ply(merged, colors), hashes)
            _write(staging, 'poses.json', _json_bytes({
                'coordinate_convention': 'T_A_B maps B to A, column homogeneous vectors',
                'world_frame': 'depth_optical_of_view0', 'units': 'm',
                'pose_estimated': True, 'metric_accuracy_verified': False,
                'T_world_depth_0': result.T_world_depth_0.tolist(),
                'T_world_depth_1': result.T_world_depth_1.tolist(),
                'capture_ids': [packet0.metadata.capture_id, packet1.metadata.capture_id],
            }), hashes)
        record = {
            'schema': 'scantopath.b01.live_pair.v1',
            'created_utc': datetime.now(timezone.utc).isoformat(),
            'status': status,
            'registered_measured_points': (
                int(len(result.world_xyz_0) + len(result.world_xyz_1)) if result.accepted else 0),
            'live_capture': True,
            'source': 'two newly acquired Gemini 2 RAW-v2 in-memory captures; locally copied for evidence',
            'registered_in_project_store': False,
            'processing_run_registered_in_sqlite': False,
            'source_views': [view0.source_ref, view1.source_ref],
            'quality': result.quality.to_json(),
            'provisional_thresholds': asdict(config),
            'registration_backend': result.backend,
            'pose_source': 'estimated_rigid_icp',
            'depth_units': 'm',
            'measured_depth_priority': True,
            'AI_ESTIMATED_points': 0,
            'metric_accuracy_verified': False,
            'robot_executable': False,
            'output_sha256': hashes,
        }
        (staging / 'registration_record.json').write_bytes(_json_bytes(record))
        os.replace(staging, path)
        return path
    except BaseException:
        shutil.rmtree(staging, ignore_errors=True)
        raise


def verify_live_artifact(folder: str | Path) -> dict:
    root = Path(folder).resolve(strict=True)
    if not root.is_dir():
        raise RegistrationError('ARTIFACT_MISSING', 'Expected a live artifact directory')
    meta = root / 'registration_record.json'
    if not meta.is_file():
        raise RegistrationError('ARTIFACT_MISSING', 'registration_record.json missing')
    record = json.loads(meta.read_text(encoding='utf-8'))
    if record.get('schema') != 'scantopath.b01.live_pair.v1':
        raise RegistrationError('ARTIFACT_SCHEMA_INVALID', 'Unknown artifact schema')
    hashes = record.get('output_sha256')
    if not isinstance(hashes, dict) or len(hashes) < 6:
        raise RegistrationError('ARTIFACT_HASHES_INVALID', 'Incomplete source bytes')
    for name, digest in hashes.items():
        if '/' in name or '\\' in name or name in ('.', '..') or not isinstance(digest, str):
            raise RegistrationError('ARTIFACT_HASHES_INVALID', 'Unexpected artifact member')
        member = root / name
        if not member.is_file() or member.is_symlink() or sha256(member.read_bytes()).hexdigest() != digest:
            raise RegistrationError('ARTIFACT_HASH_MISMATCH', name)
    return {'status': record['status'], 'verified_files': len(hashes),
            'artifact_dir': str(root), 'source_capture_ids': [
                x['capture_id'] for x in record['source_views']]}
