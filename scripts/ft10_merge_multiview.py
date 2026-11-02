"""FT-10.20/21/22: checksum-verified FT-09 trajectory -> bounded measured multi-view PLY.

Runs offline; does not open camera, change Qt/VTK, modify RAW, commit or use SQLite.
Example: python -X utf8 scripts/ft10_merge_multiview.py --input-sequence E:\\...\\FT09_Results\\b02_sequence_<id> --out E:\\...\\FT10_Results
"""
from __future__ import annotations

import argparse
import colorsys
from datetime import datetime, timezone
from hashlib import sha256
import json
import os
from pathlib import Path
import shutil
import sys
from uuid import uuid4

import numpy as np

from scantopath.modules.reconstruction.application.multiview_accumulation import (
    AccumulationConfig, MeasuredVoxelAccumulator, MultiviewError, validated_trajectory,
)


def status(code: str, **kw):
    print(json.dumps({'FT10_STATUS': code, **kw}, ensure_ascii=False, sort_keys=True), flush=True)


def parser():
    p = argparse.ArgumentParser(description='FT-10 measured point cloud accumulation')
    p.add_argument('--check-env', action='store_true')
    p.add_argument('--verify-output', type=Path)
    p.add_argument('--input-sequence', type=Path, help='Checksum-verified FT09 B02 sequence directory')
    p.add_argument('--out', type=Path, help='Parent output directory, outside git and input artifact')
    p.add_argument('--voxel-mm', type=float, default=4.0)
    p.add_argument('--max-voxel-mm', type=float, default=32.0)
    p.add_argument('--max-points', type=int, default=200000)
    p.add_argument('--min-depth-m', type=float, default=0.30)
    p.add_argument('--max-depth-m', type=float, default=1.20)
    return p


def _json_bytes(d):
    return (json.dumps(d, indent=2, ensure_ascii=False, sort_keys=True,
                       allow_nan=False) + '\n').encode('utf-8')


def _sha(path: Path):
    hasher = sha256()
    with path.open('rb') as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b''):
            hasher.update(chunk)
    return hasher.hexdigest()


def _ply_bytes(xyz: np.ndarray, source_ids: np.ndarray | None = None) -> bytes:
    """Reuse B-01's established little-endian XYZ(+RGB) PLY encoder."""
    from scantopath.modules.reconstruction.infrastructure.artifact_writer import _ply
    if not 1 <= len(xyz) <= 1_500_000:
        raise MultiviewError('FT10_VIEWER_VERTEX_LIMIT')
    colors = None
    if source_ids is not None:
        colors = np.empty((len(source_ids), 3), dtype=np.uint8)
        for i in np.unique(source_ids):
            rgb = colorsys.hsv_to_rgb((int(i) * 0.618033988749895) % 1.0, 0.75, 0.97)
            colors[source_ids == i] = np.asarray([round(255*v) for v in rgb], dtype=np.uint8)
    blob = _ply(xyz, colors)
    # Retain B-01's proven PLY header/packing; identify FT-10 explicitly.
    blob = blob.replace(b'comment ScanToPath B-01 metric-unverified',
                        b'comment ScanToPath FT-10 measured-XYZ pose-estimated metric-unverified', 1)
    if len(blob) > 256 * 1024 * 1024:
        raise MultiviewError('FT10_VIEWER_BYTE_LIMIT')
    return blob


def _read_trusted_packet(root: Path, row: dict, source_hashes: dict[str, str]):
    from scantopath.acquisition.raw_rgbd import RawRgbdCapture
    from scantopath.domain.raw_rgbd import RawRgbdCaptureMetadataV2
    i = row['sample_index']
    stem = f'frame_{i:02d}'
    names = [stem + suffix for suffix in ('_color.mjpg', '_depth.y16', '_metadata.json')]
    data = []
    for name in names:
        contents = (root / name).read_bytes()
        if sha256(contents).hexdigest() != source_hashes.get(name):
            raise MultiviewError('FT10_RAW_CHANGED_AFTER_SOURCE_VERIFICATION', name)
        data.append(contents)
    metadata = RawRgbdCaptureMetadataV2.model_validate_json(data[2])
    if (not metadata.measured or metadata.capture_id != row['capture_id']
            or metadata.depth.frame_index != row['depth_frame_index']
            or metadata.depth.timestamp_us != row['depth_timestamp_us']):
        raise MultiviewError('FT10_POSE_RAW_IDENTITY_MISMATCH', stem)
    return RawRgbdCapture(metadata, data[0], data[1])


def verify_output(root: Path) -> dict:
    if root.is_symlink():
        raise MultiviewError('FT10_OUTPUT_SYMLINK_REFUSED')
    folder = root.resolve(strict=True)
    manifest = json.loads((folder / 'sha256_manifest.json').read_text(encoding='utf-8'))
    if manifest.get('schema') != 'scantopath.ft10.sha256_manifest.v1':
        raise MultiviewError('FT10_MANIFEST_INVALID')
    hashes = manifest.get('files')
    if not isinstance(hashes, dict) or set(hashes) != {
        'merged_measured.ply','debug_view_colored.ply','accumulation_report.json'}:
        raise MultiviewError('FT10_OUTPUT_FILESET_INVALID')
    if {p.name for p in folder.iterdir()} != set(hashes) | {'sha256_manifest.json'}:
        raise MultiviewError('FT10_OUTPUT_FILESET_CHANGED')
    for name, digest in hashes.items():
        p = folder / name
        if not p.is_file() or p.is_symlink() or _sha(p) != digest:
            raise MultiviewError('FT10_OUTPUT_CHECKSUM_FAILED', name)
    report = json.loads((folder / 'accumulation_report.json').read_text(encoding='utf-8'))
    if report.get('schema') != 'scantopath.ft10.multiview.v1':
        raise MultiviewError('FT10_REPORT_SCHEMA_INVALID')
    from scantopath.modules.viewer3d.infrastructure.ply_header import inspect_ply
    one = inspect_ply(folder/'merged_measured.ply')
    two = inspect_ply(folder/'debug_view_colored.ply')
    if (one.vertex_count != two.vertex_count or one.vertex_count != report['merged_measured_points']
            or one.has_rgb or not two.has_rgb):
        raise MultiviewError('FT10_PLY_HEADER_MISMATCH')
    return {'verified_files':len(hashes), 'points':one.vertex_count,
            'accepted_views': report['accepted_view_count'],
            'source_frames':report['source_frame_count']}


def process(input_folder: Path, output_parent: Path, *, config: AccumulationConfig,
            min_depth_m: float, max_depth_m: float,
            cloud_extractor=None) -> Path:
    from b02_live_sequence import verify_artifact
    from scantopath.modules.reconstruction.infrastructure.live_artifact_writer import _safe_output_parent
    if not (0 < min_depth_m < max_depth_m < 50):
        raise MultiviewError('FT10_DEPTH_RANGE_INVALID')
    if input_folder.is_symlink():
        raise MultiviewError('FT10_INPUT_SYMLINK_REFUSED')
    source = input_folder.resolve(strict=True)
    # All RAW files + FT09 tracking record must be checksum-verified before use.
    verification = verify_artifact(source)
    record_bytes = (source / 'tracking_sequence.json').read_bytes()
    record = json.loads(record_bytes)
    accepted, skipped = validated_trajectory(record)
    status('SOURCE_VERIFIED', source_frames=record['source_frame_count'],
           accepted_views=len(accepted), skipped_views=len(skipped),
           verified_files=verification['verified_files'], source_dir=str(source))
    if (verification['accepted_poses'] != len(accepted)
            or verification['source_frame_count'] != len(record['frames'])):
        raise MultiviewError('FT10_VERIFIED_RECORD_INCONSISTENT')
    source_manifest = json.loads((source / 'sha256_manifest.json').read_text(encoding='utf-8'))
    hashes = source_manifest['files']
    if sha256(record_bytes).hexdigest() != hashes['tracking_sequence.json']:
        raise MultiviewError('FT10_RECORD_CHANGED_AFTER_SOURCE_VERIFICATION')
    target = output_parent.resolve(strict=False)
    if target == source or target.is_relative_to(source):
        raise MultiviewError('FT10_OUTPUT_INSIDE_SOURCE_REFUSED')
    accumulator = MeasuredVoxelAccumulator(config)
    extractor = cloud_extractor
    if extractor is None:
        from scantopath.modules.reconstruction.application.live_pair import cloud_from_live_packet
        extractor = cloud_from_live_packet
    details = []
    for row in accepted:
        packet = _read_trusted_packet(source, row, hashes)
        view = extractor(packet, roi=None, min_depth_m=min_depth_m,
                         max_depth_m=max_depth_m, reference_mode='charuco')
        if (view.cloud.capture_id != row['capture_id'] or
                view.source_ref.get('isolation_source') != 'FT-05.8_CHARUCO' or
                view.source_ref.get('isolation_status') != 'CHARUCO_OBJECT_FOUND'):
            raise MultiviewError('FT10_OBJECT_ISOLATION_UNVERIFIED', str(row['sample_index']))
        info = accumulator.insert(row['sample_index'], view.cloud.xyz_depth_m,
                                  np.asarray(row['T_world_depth'], dtype=np.float64))
        info.update({'capture_id':row['capture_id'], 'isolation_source':'FT-05.8_CHARUCO',
                     'depth_points_from_sensor':view.selected_points,
                     'registration_status':row['status']})
        details.append(info)
        status('VIEW_ACCUMULATED', sample=row['sample_index'],
               input_points=info['measured_points'], merged_voxels=info['accumulated_voxels_after_view'],
               voxel_mm=round(accumulator.voxel_m * 1000, 2))
        del packet, view
    # Detect source changes while processing. A mismatch prevents any publication.
    verify_artifact(source)
    xyz, origins = accumulator.result()
    output = _safe_output_parent(output_parent)
    tag = uuid4().hex[:12]
    final = output / ('multiview_' + tag)
    stage = output / ('.ft10-partial-' + tag)
    if final.exists() or stage.exists():
        raise MultiviewError('FT10_OUTPUT_COLLISION')
    summary = accumulator.diagnostics(origins)
    summary.update({
        'schema':'scantopath.ft10.multiview.v1',
        'created_utc':datetime.now(timezone.utc).isoformat(),
        'source_artifact_dir':str(source),
        'source_manifest_sha256':_sha(source/'sha256_manifest.json'),
        'source_tracking_record_sha256':hashes['tracking_sequence.json'],
        'source_frame_count':record['source_frame_count'],
        'accepted_view_count':len(accepted),
        'used_source_samples':[r['sample_index'] for r in accepted],
        'skipped_frames':skipped,
        'views':details,
        'world_frame':'depth_optical_of_sample_0',
        'matrix_convention':record['matrix_convention'],
        'units':'m',
        'bounds_world_xyz_m':{'min':xyz.min(axis=0).tolist(), 'max':xyz.max(axis=0).tolist()},
        'source':'checksum_verified_FT09_accepted_measured_RAW',
        'pose_source':'FT09_ACCEPTED_SE3_NOT_METRIC_VERIFIED',
        'geometry_source':'FT05.8_CHARUCO_OBJECT_MASK_VIA_B01',
        'voxel_config':{'initial_voxel_m':config.voxel_m,
                        'maximum_voxel_m':config.max_voxel_m,
                        'max_output_points':config.max_points},
        'depth_filter_m':[min_depth_m,max_depth_m],
        'sensor_measured_points_only':True,
        'AI_ESTIMATED_points':0,
        'metric_accuracy_verified':False,
        'meshing_implemented':False,
        'robot_executable':False,
        'processing_run_registered_in_sqlite':False,
        'viewer_point_limit':1500000,
        'viewer_byte_limit':256*1024*1024,
    })
    if len(xyz) > config.max_points:
        raise MultiviewError('FT10_RESOURCE_BUDGET_EXCEEDED')
    try:
        stage.mkdir()
        files = {
            'merged_measured.ply':_ply_bytes(xyz),
            'debug_view_colored.ply':_ply_bytes(xyz, origins),
            'accumulation_report.json':_json_bytes(summary),
        }
        for name, payload in files.items():
            (stage/name).write_bytes(payload)
        manifest = {
            'schema':'scantopath.ft10.sha256_manifest.v1',
            'created_utc':datetime.now(timezone.utc).isoformat(),
            'files':{name:_sha(stage/name) for name in files},
        }
        (stage/'sha256_manifest.json').write_bytes(_json_bytes(manifest))
        verify_output(stage)
        # FT-09 source must remain intact until atomic publication.
        verify_artifact(source)
        os.replace(stage, final)
    except BaseException:
        shutil.rmtree(stage, ignore_errors=True)
        raise
    return final


def main(argv=None):
    a = parser().parse_args(argv)
    if a.check_env:
        import cv2
        from scantopath.modules.reconstruction.application.live_pair import cloud_from_live_packet
        from scantopath.modules.viewer3d.infrastructure.ply_header import inspect_ply
        if not hasattr(cv2, 'aruco') or not hasattr(cv2.aruco, 'CharucoDetector'):
            raise MultiviewError('FT10_CHARUCO_DEPENDENCY_MISSING')
        status('ENV_READY', numpy=np.__version__, opencv=cv2.__version__,
               ft058_reused=True, ft09_reused=True, native_cpp_build_required=False,
               sqlite_required=False, camera_required=False)
        return 0
    if a.verify_output is not None:
        status('OUTPUT_VERIFIED', artifact_dir=str(a.verify_output), **verify_output(a.verify_output))
        return 0
    if not a.input_sequence or not a.out:
        status('INPUT_MISSING', required='--input-sequence <FT09_artifact> --out <external_directory>')
        return 2
    cfg = AccumulationConfig(voxel_m=a.voxel_mm / 1000,
                             max_voxel_m=a.max_voxel_mm / 1000,
                             max_points=a.max_points)
    folder = process(a.input_sequence,a.out,config=cfg,
                     min_depth_m=a.min_depth_m,max_depth_m=a.max_depth_m)
    status('ACCEPTED', artifact_dir=str(folder), **verify_output(folder),
           metric_accuracy_verified=False, ui_reopen_pending=True)
    return 0


if __name__ == '__main__':
    try:
        sys.exit(main())
    except (ValueError, OSError, RuntimeError) as exc:
        status('BLOCKED', code=getattr(exc,'code',type(exc).__name__), detail=str(exc)[:280])
        sys.exit(2)
