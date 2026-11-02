r"""FT-08.17: bounded direct Gemini 2 sampled freehand 6DoF trajectory.

    .venv\Scripts\python.exe -X utf8 scripts\b02_live_sequence.py --check-env
    .venv\Scripts\python.exe -X utf8 scripts\b02_live_sequence.py --out E:\...\_setup\B02_Results --frames 8
    .venv\Scripts\python.exe -X utf8 scripts\b02_live_sequence.py --input-artifact E:\...\b01_live_... --out E:\...\B02_Results

No Project/SQLite, camera SDK lives in existing crash-isolated child.
This is a sparse sampled-frame proof, NOT real-time frame-rate visual odometry.
"""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
from hashlib import sha256
import json
from pathlib import Path
import shutil
import sys
from time import monotonic, sleep
from uuid import uuid4


def emit(state: str, **kwargs) -> None:
    print(json.dumps({'FT08_17_STATUS': state, **kwargs}, ensure_ascii=False,
                     sort_keys=True, default=str), flush=True)


def parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(description='FT08.17 sampled Gemini 2 freehand 6DoF')
    p.add_argument('--check-env', action='store_true')
    p.add_argument('--verify-artifact', type=Path)
    p.add_argument('--input-artifact', type=Path,
                   help='Reuse two verified B01 new-frame artifacts, NO camera')
    p.add_argument('--input-sequence-artifact', type=Path,
                   help='Re-evaluate checksum-verified FT-08.17 B02 RAW sequence with FT-09 recovery, no camera')
    p.add_argument('--frames', type=int, default=8, help='New camera samples, 2..96; default 8')
    p.add_argument('--interval-ms', type=int, default=350, help='Delay between capture calls, 150..2000')
    p.add_argument('--out', type=Path, help='Parent output outside Git working tree')
    p.add_argument('--min-depth-m', type=float, default=.30)
    p.add_argument('--max-depth-m', type=float, default=1.20)
    return p


def _camera():
    from scantopath.modules.capture.application.live_stream import LiveCaptureService
    from scantopath.modules.capture.infrastructure.process_camera import ProcessIsolatedCameraAdapter
    from scantopath.modules.capture.infrastructure.jpeg_codec import PillowMjpegDecoder
    return LiveCaptureService(ProcessIsolatedCameraAdapter(), PillowMjpegDecoder())


def _capture(frames: int, interval_ms: int):
    tag = uuid4().hex[:16]
    session, specimen = 'b02live_' + tag, 'b02spec_' + tag
    service = _camera()
    packets = []
    emit('OPENING_CAMERA', frames=frames, interval_ms=interval_ms,
         camera_exclusive=True, note='Close ScanToPath and OrbbecViewer')
    service.open()
    try:
        for i in range(frames):
            begin = monotonic()
            packet = service.capture_keyframe(session_id=session, specimen_id=specimen)
            packets.append(packet)
            emit('CAPTURED', sample=i, depth_frame_index=packet.metadata.depth.frame_index,
                 capture_id=packet.metadata.capture_id)
            if i < frames - 1:
                sleep(max(0, interval_ms / 1000 - (monotonic() - begin)))
    finally:
        service.close()
    return packets


def _verified_b01_pair(path: Path):
    from scantopath.modules.reconstruction.infrastructure.live_artifact_writer import verify_live_artifact
    from scantopath.modules.reconstruction.application.live_pair import validate_live_pair
    from scantopath.acquisition.raw_rgbd import RawRgbdCapture
    from scantopath.domain.raw_rgbd import RawRgbdCaptureMetadataV2
    record = verify_live_artifact(path)
    packets = []
    for i in range(2):
        m = RawRgbdCaptureMetadataV2.model_validate_json((path / f'view{i}_metadata.json').read_bytes())
        packets.append(RawRgbdCapture(m, (path / f'view{i}_color.mjpg').read_bytes(),
                                      (path / f'view{i}_depth.y16').read_bytes()))
    validate_live_pair(packets[0], packets[1])
    emit('SOURCE_VERIFIED', capture_ids=[x.metadata.capture_id for x in packets],
         verified_files=record['verified_files'])
    return packets



def _verified_b02_sequence(path: Path):
    """Replay only a checksum-verified B02 evidence folder, never old Project/SQLite.

    A NEW output is created. The original RAW bytes and manifest remain intact.
    """
    from scantopath.acquisition.raw_rgbd import RawRgbdCapture
    from scantopath.domain.raw_rgbd import RawRgbdCaptureMetadataV2
    from scantopath.modules.reconstruction.application.live_pair import validate_live_pair
    original = path.resolve(strict=True)
    if path.is_symlink():
        raise ValueError('B02_SOURCE_SYMLINK_REFUSED')
    check = verify_artifact(original)
    frames = []
    for i in range(check['source_frame_count']):
        stem = f'frame_{i:02d}'
        meta = RawRgbdCaptureMetadataV2.model_validate_json(
            (original / (stem + '_metadata.json')).read_bytes())
        packet = RawRgbdCapture(
            meta, (original / (stem + '_color.mjpg')).read_bytes(),
            (original / (stem + '_depth.y16')).read_bytes())
        if frames:
            validate_live_pair(frames[0], packet)
            if (packet.metadata.depth.frame_index <= frames[-1].metadata.depth.frame_index
                    or packet.metadata.depth.timestamp_us <= frames[-1].metadata.depth.timestamp_us):
                raise ValueError('B02_SOURCE_NON_MONOTONIC')
        frames.append(packet)
    # Fail closed if an artifact changed during loading.
    verify_artifact(original)
    emit('SOURCE_VERIFIED', source_kind='B02_CHECKSUM_VERIFIED_SEQUENCE',
         source_frames=len(frames), verified_files=check['verified_files'],
         artifact_dir=str(original))
    return frames


def _dump(obj: object) -> bytes:
    return (json.dumps(obj, ensure_ascii=False, sort_keys=True, allow_nan=False,
                       indent=2) + '\n').encode('utf-8')


def _hash_file(path: Path) -> str:
    h = sha256()
    with path.open('rb') as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b''):
            h.update(chunk)
    return h.hexdigest()


def verify_artifact(root: Path) -> dict:
    if root.is_symlink():
        raise ValueError('B02_ARTIFACT_SYMLINK_REFUSED')
    folder = root.resolve(strict=True)
    if not folder.is_dir() or folder.is_symlink():
        raise ValueError('B02_ARTIFACT_NOT_DIRECTORY')
    manifest = json.loads((folder / 'sha256_manifest.json').read_text(encoding='utf-8'))
    if manifest.get('schema') != 'scantopath.ft08.17.sha256_manifest.v1':
        raise ValueError('B02_MANIFEST_SCHEMA_INVALID')
    files = manifest.get('files')
    if not isinstance(files, dict) or not files:
        raise ValueError('B02_MANIFEST_INVALID')
    expected = set(files) | {'sha256_manifest.json'}
    if {p.name for p in folder.iterdir()} != expected:
        raise ValueError('B02_ARTIFACT_FILESET_CHANGED')
    for name, digest in files.items():
        if name in ('', '.', '..') or Path(name).name != name or '\\' in name or '/' in name:
            raise ValueError('B02_UNSAFE_ARTIFACT_NAME')
        p = folder / name
        if not p.is_file() or p.is_symlink() or _hash_file(p) != digest:
            raise ValueError('B02_ARTIFACT_INTEGRITY_FAILED: ' + name)
    record = json.loads((folder / 'tracking_sequence.json').read_text(encoding='utf-8'))
    if record.get('schema') != 'scantopath.ft08.17.sampled_pose_sequence.v1':
        raise ValueError('B02_RECORD_SCHEMA_INVALID')
    n = record.get('source_frame_count')
    if type(n) is not int or n < 2 or n > 96 or len(files) != 3 * n + 1:
        raise ValueError('B02_ARTIFACT_COUNT_INVALID')
    return {'verified_files': len(files), 'accepted_poses': record['accepted_poses'],
            'source_frame_count': n, 'status': record['status']}


def save_evidence(parent: Path, packets: list, record: dict) -> Path:
    # Reuse the established safe output parent validator from B-01; no new store.
    from scantopath.modules.reconstruction.infrastructure.live_artifact_writer import _safe_output_parent
    output = _safe_output_parent(parent)
    tag = uuid4().hex[:12]
    final = output / ('b02_sequence_' + tag)
    staging = output / ('.b02-sequence-' + tag + '.partial')
    if final.exists() or staging.exists():
        raise ValueError('B02_OUTPUT_COLLISION')
    hashes: dict[str, str] = {}
    try:
        staging.mkdir()
        for i, packet in enumerate(packets):
            files = {
                f'frame_{i:02d}_color.mjpg': packet.color_mjpeg,
                f'frame_{i:02d}_depth.y16': packet.depth_y16_le,
                f'frame_{i:02d}_metadata.json': (
                    packet.metadata.model_dump_json(indent=2) + '\n').encode('utf-8'),
            }
            for name, data in files.items():
                (staging / name).write_bytes(data)
                hashes[name] = sha256(data).hexdigest()
        (staging / 'tracking_sequence.json').write_bytes(_dump(record))
        hashes['tracking_sequence.json'] = _hash_file(staging / 'tracking_sequence.json')
        manifest = {'schema': 'scantopath.ft08.17.sha256_manifest.v1',
                    'created_utc': datetime.now(timezone.utc).isoformat(),
                    'files': hashes}
        (staging / 'sha256_manifest.json').write_bytes(_dump(manifest))
        verify_artifact(staging)
        staging.rename(final)
        return final
    except BaseException:
        shutil.rmtree(staging, ignore_errors=True)
        raise


def main(argv=None) -> int:
    args = parser().parse_args(argv)
    if args.check_env:
        import cv2
        import numpy as np
        from scantopath.modules.reconstruction.application.two_view_registration import BACKEND
        if not hasattr(cv2, 'aruco') or not hasattr(cv2.aruco, 'CharucoDetector'):
            raise RuntimeError('OPENCV_CONTRIB_CHARUCO_REQUIRED')
        emit('ENV_READY', backend=BACKEND, numpy=np.__version__, opencv=cv2.__version__,
             ft058_reused=True, ft0816_reused=True, sqlite_required=False,
             native_cpp_build_required=False)
        return 0
    if args.verify_artifact is not None:
        emit('ARTIFACT_VERIFIED', **verify_artifact(args.verify_artifact))
        return 0
    if args.out is None:
        emit('INPUT_MISSING', required='--out <external_directory>')
        return 2
    if not 2 <= args.frames <= 96 or not 150 <= args.interval_ms <= 2000:
        raise ValueError('B02_FRAMES_OR_CADENCE_OUT_OF_RANGE')
    if not 0 < args.min_depth_m < args.max_depth_m < 50:
        raise ValueError('B02_DEPTH_RANGE_INVALID')
    if args.input_artifact and args.input_sequence_artifact:
        raise ValueError('B02_INPUT_MODES_MUTUALLY_EXCLUSIVE')
    if args.input_sequence_artifact:
        packets = _verified_b02_sequence(args.input_sequence_artifact)
        source_mode = 'CHECKSUM_VERIFIED_FT0817_SEQUENCE_REEVALUATED_FT09'
    elif args.input_artifact:
        packets = _verified_b01_pair(args.input_artifact)
        source_mode = 'CHECKSUM_VERIFIED_B01_EVIDENCE'
    else:
        packets = _capture(args.frames, args.interval_ms)
        source_mode = 'NEW_GEMINI2_SAMPLED_CAPTURE'
    emit('TRACKING_OFFLINE', frames=len(packets), reference_mode='charuco',
         method='FT05.8 + B01 ICP', note='No additional pose estimator')
    from scantopath.modules.reconstruction.application.sequence_tracking import track_sequence
    def event(item: dict):
        emit(item['status'], sample=item['sample_index'],
             capture_id=item['capture_id'], reject_code=item.get('reject_code'),
             overlap=(item.get('quality') or {}).get('overlap'),
             rmse_m=(item.get('quality') or {}).get('inlier_rmse_m'))
    record = track_sequence(packets, min_depth_m=args.min_depth_m,
                            max_depth_m=args.max_depth_m, on_event=event)
    record['source_mode'] = source_mode
    record['capture_interval_requested_ms'] = (args.interval_ms if not (args.input_artifact or args.input_sequence_artifact) else None)
    folder = save_evidence(args.out, packets, record)
    verified = verify_artifact(folder)
    emit('FINISHED', artifact_dir=str(folder), **verified, metric_accuracy_verified=False,
         ui_integration_pending=True)
    return 0 if verified['status'] == 'TRACKING' and verified['accepted_poses'] >= 2 else 3


if __name__ == '__main__':
    try:
        sys.exit(main())
    except (ValueError, RuntimeError, OSError) as exc:
        emit('BLOCKED', code=str(getattr(exc, 'code', type(exc).__name__)),
             detail=str(exc)[:250])
        sys.exit(2)
