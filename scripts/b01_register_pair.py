"""FT-08.16 / B-01 CLI. Always requires two explicitly selected RAW Capture IDs.

Examples (PowerShell):
  python -X utf8 scripts/b01_register_pair.py --check-env
  python -X utf8 scripts/b01_register_pair.py --store ... --project ... --list-captures
  python -X utf8 scripts/b01_register_pair.py --store ... --project ... --specimen ... \
      --session ... --capture0 ... --capture1 ... --roi0 100 100 700 650 \
      --roi1 120 100 720 650 --out E:\\...\\_setup\\B01_Results
"""
from __future__ import annotations
import argparse
import json
from pathlib import Path
import sys
import traceback


def build_parser():
    p = argparse.ArgumentParser(description='ScanToPath FT-08.16: two-view, RAW-measured registration')
    p.add_argument('--check-env', action='store_true', help='Noninvasive dependency check')
    p.add_argument('--list-captures', action='store_true', help='Read-only list RAW capture IDs by project')
    p.add_argument('--store', type=Path, help='Existing ScanToPath store with metadata.sqlite3')
    p.add_argument('--project', help='Project ID')
    p.add_argument('--specimen', help='Specimen ID')
    p.add_argument('--session', help='ScanSession ID')
    p.add_argument('--capture0', help='Reference RAW capture ID')
    p.add_argument('--capture1', help='Moving RAW capture ID')
    p.add_argument('--roi0', type=int, nargs=4, metavar=('X0','Y0','X1','Y1'),
                   help='Native Depth-grid object rectangle of capture0 (exclusive X1,Y1)')
    p.add_argument('--roi1', type=int, nargs=4, metavar=('X0','Y0','X1','Y1'),
                   help='Native Depth-grid object rectangle of capture1')
    p.add_argument('--min-depth-m', type=float, default=0.25)
    p.add_argument('--max-depth-m', type=float, default=1.50)
    p.add_argument('--min-overlap', type=float, default=0.28, help='PROVISIONAL geometry quality threshold')
    p.add_argument('--max-rmse-m', type=float, default=0.009, help='PROVISIONAL quality threshold, not mm gate')
    p.add_argument('--initial-pose-json', type=Path, help='Optional existing pose JSON with T_world_depth_1')
    p.add_argument('--out', type=Path, help='Output parent outside RAW store and Git repo')
    return p


def _print_status(status, **details):
    print(json.dumps({'B01_STATUS': status, **details}, ensure_ascii=False, sort_keys=True))


def _env():
    import numpy as np
    import pydantic
    from PIL import Image
    from scantopath.modules.reconstruction.application.two_view_registration import BACKEND
    _print_status('ENV_READY', python=sys.version.split()[0], numpy=np.__version__,
                  pydantic=pydantic.__version__, pillow=Image.__version__,
                  backend=BACKEND, requires_nvidia=False, requires_open3d=False)
    return 0


def _list_captures(args):
    if args.store is None or not args.project:
        raise ValueError('--store and --project are required to list captures')
    from scantopath.modules.project_workspace.application.service import ProjectWorkspaceService
    tree = ProjectWorkspaceService(args.store).get_project_tree(args.project)
    for node in tree.specimens:
        if args.specimen and node.specimen.specimen_id != args.specimen:
            continue
        for session in node.sessions:
            if args.session and session.session_id != args.session:
                continue
            for capture in session.captures:
                print(json.dumps({'specimen_id': node.specimen.specimen_id,
                                  'session_id': session.session_id,
                                  'capture_id': capture.capture_id,
                                  'raw_schema_version': capture.schema_version},
                                 ensure_ascii=False))
    return 0


def _load_initial(path):
    import numpy as np
    obj = json.loads(path.read_text(encoding='utf-8'))
    if not isinstance(obj, dict) or 'T_world_depth_1' not in obj:
        raise ValueError('Expected JSON object with T_world_depth_1')
    return np.asarray(obj['T_world_depth_1'], dtype=np.float64)


def main(argv=None):
    args = build_parser().parse_args(argv)
    # script is valid from source checkout, without pip editable install.
    sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'src'))
    try:
        if args.check_env:
            return _env()
        if args.list_captures:
            return _list_captures(args)
        required = ('store','project','specimen','session','capture0','capture1','roi0','roi1','out')
        missing = [f'--{k.replace("_", "-")}' for k in required if getattr(args,k) is None]
        if missing:
            _print_status('INPUT_MISSING', required=missing)
            return 2
        from scantopath.modules.capture.application.contracts import CaptureContext
        from scantopath.modules.reconstruction.application.contracts import RegistrationConfig
        from scantopath.modules.reconstruction.application.two_view_service import process_two_captures
        from scantopath.modules.reconstruction.infrastructure.artifact_writer import write_pair_artifact
        import numpy as np
        cfg = RegistrationConfig(min_overlap=args.min_overlap, max_rmse_m=args.max_rmse_m)
        ctx = dict(store_root=str(args.store.resolve(strict=True)),
                   project_id=args.project, specimen_id=args.specimen, session_id=args.session)
        pair0 = CaptureContext(**ctx, capture_id=args.capture0)
        pair1 = CaptureContext(**ctx, capture_id=args.capture1)
        initial = _load_initial(args.initial_pose_json) if args.initial_pose_json else None
        first, second, result = process_two_captures(pair0, pair1, roi0=tuple(args.roi0),
                          roi1=tuple(args.roi1), min_depth_m=args.min_depth_m,
                          max_depth_m=args.max_depth_m, config=cfg,
                          initial_T_world_depth1=initial)
        folder = write_pair_artifact(args.out, store_root=args.store,
                      source0=first.source_ref, source1=second.source_ref,
                      result=result, config=cfg)
        _print_status('ACCEPTED' if result.accepted else 'REJECTED',
                      artifact_dir=str(folder), overlap=result.quality.overlap,
                      inlier_rmse_m=result.quality.inlier_rmse_m,
                      reject_reasons=result.quality.reject_reasons,
                      captured_measured_points=[first.selected_points, second.selected_points],
                      registered_measured_points=(len(result.world_xyz_0) + len(result.world_xyz_1))
                           if result.accepted else 0)
        return 0 if result.accepted else 3
    except (ValueError, RuntimeError, OSError, ImportError, KeyError) as exc:
        _print_status('BLOCKED', code=getattr(exc, 'code', type(exc).__name__),
                      message=str(exc)[:500])
        return 2


if __name__ == '__main__':
    raise SystemExit(main())
