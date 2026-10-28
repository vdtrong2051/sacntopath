"""DOC-03B: read-only audit of five long-form technical module manuals."""
from __future__ import annotations

import argparse
import csv
import json
import re
import sys
from pathlib import Path

BASELINE = '0557c0d4fed9a3df3b180fc9872c6d3293b5f0d5'
FILES = {
    'RGBD_ACQUISITION.md': ('RawRgbdCaptureMetadataV2', 'RawRgbdCapture', 'MJPEG', 'Y16', 'translation_mm', 'camera_pose', 'measured', 'NOT_TESTED'),
    'RAW_STORAGE.md': ('commit_raw', 'read_raw', 'COMMITTED', 'manifest.json', 'NumberedStorageRegistry', 'LegacyRawMigrator', 'SQLite', 'NOT_TESTED'),
    'PROJECT_WORKSPACE.md': ('ProjectWorkspaceService', 'ProjectCommands', 'metadata.sqlite3', 'ProcessingRun', 'NumberingPendingError', 'NOT_TESTED'),
    'DESKTOP_UI.md': ('ScanToPathMainWindow', 'QMainWindow', 'closeEvent', 'begin_shutdown', 'QT_QPA_PLATFORM', 'NOT_TESTED'),
    'VIEWER_3D.md': ('SceneSource', 'SceneDescriptor', 'SceneSelectionRef', 'scene_revision', 'frame_revision', 'ACK', 'vtkCellPicker', 'NOT_TESTED'),
}
# Explicitly checked against the DOC-03A Git source tree. Not fuzzy or guessed path inference.
SOURCES = (
    'src/scantopath/acquisition/orbbec_adapter.py',
    'src/scantopath/acquisition/raw_rgbd.py',
    'src/scantopath/acquisition/native.py',
    'src/scantopath/acquisition/capture_once.py',
    'src/scantopath/domain/raw_rgbd.py',
    'src/scantopath/storage/session_store.py',
    'src/scantopath/storage/numbered.py',
    'src/scantopath/storage/legacy_migration.py',
    'src/scantopath/metadata/store.py',
    'src/scantopath/modules/project_workspace/application/service.py',
    'src/scantopath/modules/project_workspace/presentation/controller.py',
    'src/scantopath/modules/viewer3d/application/scene_contracts.py',
    'src/scantopath/modules/viewer3d/infrastructure/resident_poc/async_session.py',
    'src/scantopath/modules/viewer3d/infrastructure/resident_poc/client.py',
    'src/scantopath/modules/viewer3d/infrastructure/resident_poc/host.py',
    'src/scantopath/modules/viewer3d/presentation/interactive_controller.py',
    'src/scantopath/ui/main.py',
    'src/scantopath/ui/shell/main_window.py',
    'src/scantopath/ui/shell/viewer_bootstrap.py',
    'scripts/verify.ps1',
)
TESTS = (
    'tests/contracts/camera/test_native_loader.py',
    'tests/contracts/camera/test_pre04_orbbec_adapter.py',
    'tests/unit/raw/test_raw_rgbd_contract.py',
    'tests/unit/raw/test_raw_storage.py',
    'tests/integration/storage/test_gd1_07_2_numbered_storage.py',
    'tests/integration/storage/test_gd1_07_7_legacy_migration.py',
    'tests/integration/project/test_gd1_07_3_project_services.py',
    'tests/ui/project/test_gd1_07_8_qt.py',
    'tests/ui/shell/test_gd1_06_3_ui.py',
    'tests/ui/viewer/test_gd1_r5_3_qt.py',
    'tests/native/viewer/test_gd1_r5_1_scene_geometry.py',
    'tests/native/renderer/test_gd1_r4_3_transport_lifecycle.py',
)
LINK = re.compile(r'(?<!!)\[[^\]]+\]\(([^)]+)\)')


def link_errors(root: Path, path: Path, text: str) -> list[str]:
    errs = []
    for ref in LINK.findall(text):
        ref = ref.split(' "')[0].strip()
        if ref.startswith(('http://', 'https://', 'mailto:', '#')):
            continue
        target = ref.split('#')[0].split('?')[0]
        if not target:
            continue
        if re.match(r'^[A-Za-z]:', target) or target.startswith(('/', '\\')) or '\\' in target:
            errs.append('UNSAFE_LINK:' + str(path) + ':' + ref)
            continue
        resolved = (path.parent / target).resolve()
        if not resolved.is_relative_to(root.resolve()) or not resolved.is_file():
            errs.append('BROKEN_LINK:' + str(path) + ':' + ref)
    return errs


def module_errors(name: str, content: str) -> list[str]:
    errors = []
    path = 'docs/03-modules/' + name
    headings = [int(x) for x in re.findall(r'^##\s+(\d+)\.', content, re.M)]
    if headings != list(range(1, 14)):
        errors.append('MISSING_OR_UNORDERED_13_SECTIONS:' + path + ':' + str(headings))
    if len(content) < 8500 or len(content.splitlines()) < 125:
        errors.append('INSUFFICIENT_EXPLANATION:' + path)
    for token in (BASELINE, '2026-10-28', 'owner:', 'source-of-truth:', 'manual', '```', 'tests/', 'Lỗi'):
        if token.lower() not in content.lower():
            errors.append('MISSING_REQUIRED_CONTEXT:' + path + ':' + token)
    for token in FILES[name]:
        if token not in content:
            errors.append('CONTRACT_NOT_EXPLAINED:' + path + ':' + token)
    if 'tests/test_' in content or '[CẦN BỔ SUNG]' in content:
        errors.append('OLD_FLAT_TEST_OR_TEMPLATE:' + path)
    if 'R6_OVERALL_PASS' in content and 'không' not in content.lower():
        errors.append('R6_PREMATURE_PASS_CLAIM:' + path)
    return errors


def verify(root: Path) -> dict:
    root = root.resolve(strict=True)
    errors = []
    module_dir = root / 'docs/03-modules'
    for name in FILES:
        path = module_dir / name
        if not path.is_file() or path.is_symlink():
            errors.append('MISSING_MODULE:' + name)
            continue
        try:
            content = path.read_text(encoding='utf-8')
        except UnicodeError:
            errors.append('INVALID_UTF8:' + name)
            continue
        errors.extend(module_errors(name, content))
        errors.extend(link_errors(root, path, content))
    readme = root / 'docs/README.md'
    if not readme.is_file():
        errors.append('MISSING_DOCS_PORTAL')
    else:
        body = readme.read_text(encoding='utf-8')
        errors.extend(link_errors(root, readme, body))
        for name in FILES:
            if f'03-modules/{name}' not in body:
                errors.append('PORTAL_MISSING_MODULE:' + name)
        # R7/DOC03A compatibility must remain until DOC-05.
        for token in ('DOC-03B', 'DOC-03C', 'DOC-04', 'DOC-05',
                      '7a0df7c5b596ff8750bf91f47310067c53a8b204'):
            if token not in body:
                errors.append('DOC03A_PORTAL_CONTRACT_CHANGED:' + token)
    mapping = root / 'docs/standardization/DOC02_BAN_DO_65.csv'
    if not mapping.is_file():
        errors.append('DOC02_MAPPING_MISSING')
    else:
        rows = list(csv.DictReader(mapping.open(encoding='utf-8-sig', newline='')))
        expected = {'docs/03-modules/' + name for name in FILES}
        mapped = {r['primary_target'] for r in rows if r['stage'] == 'DOC-03B'}
        if mapped != expected:
            errors.append('DOC02_MAPPING_MISMATCH:' + repr(sorted(mapped ^ expected)))
    for p in SOURCES + TESTS:
        if not (root / p).is_file():
            errors.append('EVIDENCE_PATH_MISSING:' + p)
    # All 7 R7 redirects and canonical R6 status must survive unchanged as paths.
    for p in (
        'docs/README.md', 'docs/02-kien-truc/KIEN_TRUC_HE_THONG.md',
        'docs/03-modules/VIEWER_3D.md', 'docs/03-modules/PROJECT_WORKSPACE.md',
        'docs/04-phat-trien/TIEU_CHUAN_KY_THUAT.md',
        'docs/04-phat-trien/TIEU_CHUAN_KY_THUAT.md',
        'docs/99-lich-su/ARCHIVE/ROADMAP_CU/ROADMAP_V1_ARCHIVED.md',
        'docs/07-nghiem-thu/records/GD1_R6_ACCEPTANCE_STATUS.md',
    ):
        if not (root / p).is_file():
            errors.append('HISTORICAL_COMPATIBILITY_MISSING:' + p)
    return {'schema':'scantopath-doc03b-content-v1', 'baseline':BASELINE,
            'status':'PASS' if not errors else 'FAIL', 'modules':len(FILES),
            'source_paths':len(SOURCES), 'test_paths':len(TESTS),
            'hmi_manual':'NOT_TESTED', 'errors':errors}


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser()
    p.add_argument('--project-root', type=Path, required=True)
    p.add_argument('--out-dir', type=Path, required=True)
    args = p.parse_args(argv)
    try:
        root = args.project_root.resolve(strict=True)
        out = args.out_dir.resolve()
        if out == root or out.is_relative_to(root):
            raise ValueError('EVIDENCE_MUST_BE_OUTSIDE_REPOSITORY')
        result = verify(root)
        out.mkdir(parents=True, exist_ok=True)
        (out/'DOC03B_CONTENT_GATE.json').write_text(json.dumps(result, ensure_ascii=False, indent=2)+'\n', encoding='utf-8')
        print('DOC-03B CONTENT', result['status'], 'modules', result['modules'],
              'source', result['source_paths'], 'tests', result['test_paths'],
              'errors', len(result['errors']), flush=True)
        for error in result['errors']:
            print('DOC-03B ERROR:', error, flush=True)
        return 0 if result['status']=='PASS' else 1
    except (OSError, ValueError, RuntimeError, UnicodeError) as exc:
        print('DOC-03B GATE ERROR:', str(exc), file=sys.stderr)
        return 2


if __name__ == '__main__':
    raise SystemExit(main())
