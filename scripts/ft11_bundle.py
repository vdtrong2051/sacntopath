"""FT-11 portable reconstruction bundle: closed-form, verifiable, no RAW copied.

This CLI does not open a camera, mutate SQLite or create geometry. The FT09 pose
sequence remains explicitly metric-unverified; an exported bundle is NOT a
measurement certificate. All paths in the bundle are relative and fixed.
"""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
from hashlib import sha256
import json
import os
from pathlib import Path
import shutil
import sys
from uuid import uuid4

SCHEMA = 'scantopath.ft11.reconstruction.v1'
MANIFEST_SCHEMA = 'scantopath.ft11.manifest.v1'
FILES = {
    'cloud/merged_measured.ply': 'cloud',
    'cloud/debug_view_colored.ply': 'cloud_debug',
    'poses/tracking_sequence.json': 'poses',
    'reports/accumulation_report.json': 'report',
}
MAX_META_BYTES = 8 * 1024 * 1024
MAX_PLY_BYTES = 256 * 1024 * 1024


class BundleError(ValueError):
    def __init__(self, code, detail=''):
        self.code = code
        super().__init__(code + (': ' + detail if detail else ''))


def sha_file(path: Path) -> str:
    h = sha256()
    with path.open('rb') as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b''):
            h.update(chunk)
    return h.hexdigest()


def read_json(path: Path) -> dict:
    if path.is_symlink() or not path.is_file() or not 1 <= path.stat().st_size <= MAX_META_BYTES:
        raise BundleError('FT11_INVALID_METADATA', str(path))
    data = json.loads(path.read_text(encoding='utf-8'))
    if not isinstance(data, dict):
        raise BundleError('FT11_INVALID_METADATA_SHAPE')
    return data


def write_json(path: Path, data: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, sort_keys=True, ensure_ascii=False, indent=2,
                               allow_nan=False) + '\n', encoding='utf-8')


def verify_bundle(folder: Path) -> dict:
    if folder.is_symlink() or not folder.is_dir():
        raise BundleError('FT11_BUNDLE_MISSING')
    folder = folder.resolve(strict=True)
    expected = set(FILES) | {'reconstruction.json', 'sha256_manifest.json'}
    real = {str(p.relative_to(folder)).replace('\\', '/') for p in folder.rglob('*')
            if p.is_file() or p.is_symlink()}
    if real != expected:
        raise BundleError('FT11_BUNDLE_FILESET_CHANGED')
    for path in folder.rglob('*'):
        if path.is_symlink():
            raise BundleError('FT11_BUNDLE_SYMLINK_REFUSED')
    record = read_json(folder / 'reconstruction.json')
    manifest = read_json(folder / 'sha256_manifest.json')
    if record.get('schema') != SCHEMA or manifest.get('schema') != MANIFEST_SCHEMA:
        raise BundleError('FT11_SCHEMA_INVALID')
    hashes = manifest.get('files')
    if not isinstance(hashes, dict) or set(hashes) != expected - {'sha256_manifest.json'}:
        raise BundleError('FT11_MANIFEST_FILESET_INVALID')
    for name in sorted(hashes):
        p = folder / name
        if not p.is_file() or p.is_symlink() or sha_file(p) != hashes[name]:
            raise BundleError('FT11_BUNDLE_HASH_MISMATCH', name)
        if name.endswith('.ply') and (not 1 <= p.stat().st_size <= MAX_PLY_BYTES):
            raise BundleError('FT11_PLY_RESOURCE_LIMIT', name)
    report = read_json(folder/'reports/accumulation_report.json')
    tracking = read_json(folder/'poses/tracking_sequence.json')
    if report.get('schema') != 'scantopath.ft10.multiview.v1':
        raise BundleError('FT11_REPORT_SCHEMA_INVALID')
    if (report.get('source_tracking_record_sha256') != hashes['poses/tracking_sequence.json']
            or tracking.get('accepted_poses') != report.get('accepted_view_count')
            or tracking.get('source_frame_count') != report.get('source_frame_count')):
        raise BundleError('FT11_PROVENANCE_MISMATCH')
    if (record.get('points') != report.get('merged_measured_points')
            or record.get('accepted_views') != report.get('accepted_view_count')
            or record.get('world_frame') != report.get('world_frame')
            or record.get('units') != report.get('units')
            or record.get('metric_accuracy_verified') is not False):
        raise BundleError('FT11_RECONSTRUCTION_METADATA_MISMATCH')
    # Verify header and point counts using the already-established viewer preflight.
    from scantopath.modules.viewer3d.infrastructure.ply_header import inspect_ply
    a = inspect_ply(folder/'cloud/merged_measured.ply')
    b = inspect_ply(folder/'cloud/debug_view_colored.ply')
    if (a.vertex_count != record['points'] or b.vertex_count != a.vertex_count
            or a.has_rgb or not b.has_rgb):
        raise BundleError('FT11_PLY_INVALID')
    return {'artifact_dir': str(folder), 'main_ply': str(folder/'cloud/merged_measured.ply'),
            'debug_ply': str(folder/'cloud/debug_view_colored.ply'),
            'points': a.vertex_count, 'accepted_views': record['accepted_views'],
            'source_frames': tracking['source_frame_count'], 'metric_accuracy_verified': False}


def _check_path(folder: Path, *, field: str):
    if folder.is_symlink() or not folder.is_dir():
        raise BundleError('FT11_INVALID_' + field)
    if any(p.is_symlink() for p in (folder, *folder.parents)):
        raise BundleError('FT11_SYMLINK_PATH_REFUSED')
    return folder.resolve(strict=True)


def export_bundle(source_sequence: Path, source_cloud: Path, output_parent: Path) -> Path:
    source_sequence = _check_path(source_sequence, field='SEQUENCE')
    source_cloud = _check_path(source_cloud, field='CLOUD')
    from scantopath.modules.viewer3d.infrastructure.ply_header import inspect_ply
    # Verify FT-09 and FT-10 source hashes before packaging; no raw rewrites.
    from b02_live_sequence import verify_artifact
    from ft10_merge_multiview import verify_output
    verify_artifact(source_sequence)
    verify_output(source_cloud)
    tracking_file = source_sequence/'tracking_sequence.json'
    report = read_json(source_cloud/'accumulation_report.json')
    tracking = read_json(tracking_file)
    if (sha_file(tracking_file) != report.get('source_tracking_record_sha256')
            or tracking.get('accepted_poses') != report.get('accepted_view_count')):
        raise BundleError('FT11_SOURCE_POSE_CLOUD_MISMATCH')
    inspect_ply(source_cloud/'merged_measured.ply')
    if not output_parent.is_dir() or output_parent.is_symlink():
        raise BundleError('FT11_OUTPUT_PARENT_MISSING')
    parent = output_parent.resolve(strict=True)
    repo = Path(__file__).resolve().parents[1]
    if parent == repo or parent.is_relative_to(repo):
        raise BundleError('FT11_OUTPUT_INSIDE_GIT_REFUSED')
    if parent in (source_cloud, source_sequence) or parent.is_relative_to(source_cloud) or parent.is_relative_to(source_sequence):
        raise BundleError('FT11_OUTPUT_INSIDE_INPUT_REFUSED')
    token = uuid4().hex[:12]
    final = parent / ('ScanToPath_Reconstruction_' + token)
    stage = parent / ('.ft11-partial-' + token)
    if stage.exists() or final.exists():
        raise BundleError('FT11_OUTPUT_COLLISION')
    stage.mkdir()
    sources = {
        'cloud/merged_measured.ply': source_cloud/'merged_measured.ply',
        'cloud/debug_view_colored.ply': source_cloud/'debug_view_colored.ply',
        'poses/tracking_sequence.json': tracking_file,
        'reports/accumulation_report.json': source_cloud/'accumulation_report.json',
    }
    try:
        for relative, src in sources.items():
            target = stage/relative
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(src, target)
            if sha_file(target) != sha_file(src):
                raise BundleError('FT11_COPY_HASH_MISMATCH', relative)
        write_json(stage/'reconstruction.json', {
            'schema': SCHEMA,
            'created_utc': datetime.now(timezone.utc).isoformat(),
            'points': report['merged_measured_points'],
            'accepted_views': report['accepted_view_count'],
            'source_frames': report['source_frame_count'],
            'world_frame': report['world_frame'], 'units': report['units'],
            'metric_accuracy_verified': False,
            'mesh_implemented': False,
            'robot_executable': False,
            'raw_included': False,
            'pose_source': report['pose_source'],
            'source_manifest_sha256': report['source_manifest_sha256'],
        })
        write_json(stage/'sha256_manifest.json', {
            'schema': MANIFEST_SCHEMA,
            'files': {name: sha_file(stage/name) for name in
                      sorted(set(FILES) | {'reconstruction.json'})},
        })
        verify_bundle(stage)
        # Check source wasn't changed mid-copy.
        verify_artifact(source_sequence)
        verify_output(source_cloud)
        os.replace(stage, final)
        return final
    except BaseException:
        shutil.rmtree(stage, ignore_errors=True)
        raise


def main(argv=None) -> int:
    p = argparse.ArgumentParser()
    group = p.add_mutually_exclusive_group(required=True)
    group.add_argument('--verify', type=Path)
    group.add_argument('--export', action='store_true')
    p.add_argument('--source-sequence', type=Path)
    p.add_argument('--source-cloud', type=Path)
    p.add_argument('--out', type=Path)
    a = p.parse_args(argv)
    if a.verify:
        result = verify_bundle(a.verify)
    else:
        if not all((a.source_sequence, a.source_cloud, a.out)):
            p.error('Export requires --source-sequence, --source-cloud, --out')
        folder = export_bundle(a.source_sequence, a.source_cloud, a.out)
        result = verify_bundle(folder)
    print(json.dumps({'FT11_STATUS': 'VERIFIED' if a.verify else 'EXPORTED', **result},
                     ensure_ascii=False), flush=True)
    return 0


if __name__ == '__main__':
    try:
        sys.exit(main())
    except (ValueError, OSError, RuntimeError, ImportError) as exc:
        print(json.dumps({'FT11_STATUS': 'BLOCKED',
                          'code': str(getattr(exc, 'code', type(exc).__name__)),
                          'detail': str(exc)[:180]}, ensure_ascii=False), flush=True)
        sys.exit(2)
