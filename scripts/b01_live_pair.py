r"""FT-08.16 Gemini 2: direct two-view test without an old Project/RAW store.

Run from repository root:
  .venv\Scripts\python.exe -X utf8 scripts\b01_live_pair.py --check-env
  .venv\Scripts\python.exe -X utf8 scripts\b01_live_pair.py --probe
  .venv\Scripts\python.exe -X utf8 scripts\b01_live_pair.py --out E:\...\_setup\B01_Live_Results
"""
from __future__ import annotations
import argparse
from pathlib import Path
import json
import sys
from uuid import uuid4


def _status(state: str, **fields):
    print(json.dumps({'B01_LIVE_STATUS': state, **fields}, ensure_ascii=False, sort_keys=True), flush=True)


def parser():
    p = argparse.ArgumentParser(description='FT-08.16: direct Gemini 2 two-view registration')
    p.add_argument('--check-env', action='store_true', help='Check Python dependencies without opening camera')
    p.add_argument('--probe', action='store_true', help='Open camera once, read live RGB-D and close')
    p.add_argument('--verify-artifact', type=Path, help='Verify output hashes without opening camera')
    p.add_argument('--out', type=Path, help='Output parent OUTSIDE Git repo; no SQLite required')
    p.add_argument('--input-artifact', type=Path, help='Reprocess the two verified NEW Gemini RAW frames from a prior B01 Live artifact; camera remains closed')
    p.add_argument('--roi0', nargs=4, type=int, metavar=('X0','Y0','X1','Y1'),
                   help='View 0 native depth-grid ROI; default center 64%%')
    p.add_argument('--roi1', nargs=4, type=int, metavar=('X0','Y0','X1','Y1'),
                   help='View 1 native depth-grid ROI; default center 64%%')
    p.add_argument('--reference-mode', choices=('charuco', 'depth'), default='charuco',
                   help='Use existing FT05.8 ChArUco object mask (default), or existing FT05.7 depth geometry')
    p.add_argument('--min-depth-m', type=float, default=.30)
    p.add_argument('--max-depth-m', type=float, default=1.20)
    p.add_argument('--min-overlap', type=float, default=.28)
    p.add_argument('--max-rmse-m', type=float, default=.009)
    return p


def _camera():
    from scantopath.modules.capture.application.live_stream import LiveCaptureService
    from scantopath.modules.capture.infrastructure.process_camera import ProcessIsolatedCameraAdapter
    from scantopath.modules.capture.infrastructure.jpeg_codec import PillowMjpegDecoder
    return LiveCaptureService(ProcessIsolatedCameraAdapter(), PillowMjpegDecoder())


def _probe():
    service = _camera()
    service.open()
    try:
        frame = None
        for attempt in range(3):
            try:
                frame = service.read_next(per_attempt_timeout_ms=750)
                break
            except TimeoutError:
                if attempt == 2:
                    raise
        assert frame is not None
        if frame.source.calibration is None:
            raise ValueError(frame.source.calibration_error or 'LIVE_CALIBRATION_MISSING')
        _status('CAMERA_PROBE_PASS', name=frame.source.device_name,
                rgb_wh=[frame.source.color_width, frame.source.color_height],
                depth_wh=[frame.source.depth_width, frame.source.depth_height],
                depth_scale_m_per_unit=frame.source.depth_scale_m_per_unit,
                calibration_fingerprint=frame.source.calibration.fingerprint,
                depth_frame_index=frame.source.depth_frame_index)
    finally:
        service.close()
    return 0


def _capture_pair():
    # Temporary IDs for two NEW live packets ONLY, not claimed to be registered
    # Project/Session entities. Generated once so the camera port can carry them.
    tag = uuid4().hex[:16]
    session_id, specimen_id = 'b01live_' + tag, 'b01spec_' + tag
    service = _camera()
    _status('OPENING_CAMERA', note='Close ScanToPath Desktop / OrbbecViewer first; camera is exclusive')
    service.open()
    try:
        print('\n[View 0] Đặt vật đứng yên, camera nhìn góc đầu. Đặt vật gần giữa khung hình.', flush=True)
        input('Nhấn ENTER để chụp góc 0 (Ctrl+C để hủy): ')
        a = service.capture_keyframe(session_id=session_id, specimen_id=specimen_id)
        _status('VIEW0_CAPTURED', capture_id=a.metadata.capture_id,
                frame_index=a.metadata.depth.frame_index, timestamp_us=a.metadata.depth.timestamp_us)
        print('\n[View 1] GIỮ vật đứng yên; di chuyển CAMERA nhẹ ~10-20 độ, vẫn thấy phần lớn vùng cũ.', flush=True)
        input('Nhấn ENTER để chụp góc 1 (Ctrl+C để hủy): ')
        b = service.capture_keyframe(session_id=session_id, specimen_id=specimen_id)
        _status('VIEW1_CAPTURED', capture_id=b.metadata.capture_id,
                frame_index=b.metadata.depth.frame_index, timestamp_us=b.metadata.depth.timestamp_us)
        return a, b
    finally:
        service.close()



def _load_verified_new_pair(path: Path):
    """No historical store: only two checksum-verified new-camera evidence frames."""
    from scantopath.acquisition.raw_rgbd import RawRgbdCapture
    from scantopath.domain.raw_rgbd import RawRgbdCaptureMetadataV2
    from scantopath.modules.reconstruction.application.live_pair import validate_live_pair
    from scantopath.modules.reconstruction.infrastructure.live_artifact_writer import verify_live_artifact
    folder = path.resolve(strict=True)
    if folder.is_symlink():
        raise ValueError('SYMLINK_ARTIFACT_REFUSED')
    record = verify_live_artifact(folder)
    packets=[]
    for i in (0, 1):
        m=RawRgbdCaptureMetadataV2.model_validate_json((folder / f'view{i}_metadata.json').read_bytes())
        packets.append(RawRgbdCapture(
            m, (folder / f'view{i}_color.mjpg').read_bytes(),
            (folder / f'view{i}_depth.y16').read_bytes()))
    validate_live_pair(*packets)
    _status('SOURCE_VERIFIED', artifact_dir=str(folder),
            verified_files=record['verified_files'],
            capture_ids=[x.metadata.capture_id for x in packets])
    return packets[0], packets[1]

def _run(args):
    if args.out is None:
        _status('INPUT_MISSING', required='--out E:\\...\\_setup\\B01_Live_Results')
        return 2
    if not (0 < args.min_depth_m < args.max_depth_m < 50):
        raise ValueError('Invalid depth range')
    from scantopath.modules.reconstruction.application.contracts import RegistrationConfig
    from scantopath.modules.reconstruction.application.live_pair import process_live_pair
    from scantopath.modules.reconstruction.infrastructure.live_artifact_writer import (
        write_live_pair_artifact, verify_live_artifact)
    cfg = RegistrationConfig(min_overlap=args.min_overlap, max_rmse_m=args.max_rmse_m)
    raw0, raw1 = (_load_verified_new_pair(args.input_artifact)
                  if args.input_artifact else _capture_pair())
    _status('REGISTERING', message='Processing newly captured RGB-D from memory; no old store used')
    diagnostics = {}
    effective = {}
    try:
        v0, v1, result = process_live_pair(raw0, raw1,
                    roi0=tuple(args.roi0) if args.roi0 else None,
                    roi1=tuple(args.roi1) if args.roi1 else None,
                    min_depth_m=args.min_depth_m, max_depth_m=args.max_depth_m,
                    reference_mode=args.reference_mode, config=cfg,
                    diagnostics=diagnostics, effective_config=effective)
    except Exception:
        if diagnostics:
            _status('OBJECT_DIAGNOSTICS', **diagnostics)
        raise
    if diagnostics:
        _status('OBJECT_DIAGNOSTICS', **diagnostics)
    if args.input_artifact:
        v0.source_ref['reprocessed_from_verified_live_artifact'] = str(args.input_artifact.resolve())
        v1.source_ref['reprocessed_from_verified_live_artifact'] = str(args.input_artifact.resolve())
    folder = write_live_pair_artifact(args.out, packet0=raw0, packet1=raw1,
                                      view0=v0, view1=v1, result=result, config=effective['config'])
    verified = verify_live_artifact(folder)
    _status('ACCEPTED' if result.accepted else 'REJECTED',
            artifact_dir=str(folder), verified_files=verified['verified_files'],
            backend=result.backend, reference_mode=args.reference_mode,
            isolation_statuses=[v0.source_ref['isolation_status'], v1.source_ref['isolation_status']],
            backend_object_isolation=[v0.source_ref['isolation_source'],v1.source_ref['isolation_source']],
            overlap=result.quality.overlap,
            inlier_rmse_m=result.quality.inlier_rmse_m,
            motion_translation_m=result.quality.translation_m,
            motion_rotation_deg=result.quality.rotation_deg,
            reject_reasons=result.quality.reject_reasons,
            measured_roi_points=[v0.selected_points, v1.selected_points],
            ui_reopen_pending=True, metric_accuracy_verified=False)
    return 0 if result.accepted else 3


def main(argv=None):
    args = parser().parse_args(argv)
    sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'src'))
    try:
        if args.check_env:
            import numpy as np
            from PIL import Image
            from scantopath.modules.reconstruction.application.two_view_registration import BACKEND
            from scantopath.modules.capture.infrastructure.process_camera import ProcessIsolatedCameraAdapter
            if args.reference_mode == 'charuco':
                import cv2
                if not hasattr(cv2, 'aruco') or not hasattr(cv2.aruco, 'CharucoDetector'):
                    raise RuntimeError('FT05.8_OPENCV_CONTRIB_CHARUCO_MISSING')
            _status('ENV_READY', numpy=np.__version__, pillow=Image.__version__,
                    backend=BACKEND, reference_mode=args.reference_mode,
                    isolation_source=('FT05.8_CHARUCO' if args.reference_mode == 'charuco' else 'FT05.7_DEPTH_GEOMETRIC'),
                    camera_adapter='ProcessIsolatedCameraAdapter',
                    requires_store=False, requires_cuda=False)
            return 0
        if args.verify_artifact:
            from scantopath.modules.reconstruction.infrastructure.live_artifact_writer import verify_live_artifact
            _status('ARTIFACT_VERIFIED', **verify_live_artifact(args.verify_artifact))
            return 0
        if args.probe:
            return _probe()
        return _run(args)
    except KeyboardInterrupt:
        _status('CANCELLED', reason='OPERATOR_CANCELLED')
        return 130
    except (ValueError, RuntimeError, OSError, ImportError, TimeoutError, KeyError, TypeError) as exc:
        _status('BLOCKED', code=getattr(exc, 'code', type(exc).__name__),
                error=str(exc)[:350])
        return 2


if __name__ == '__main__':
    raise SystemExit(main())
