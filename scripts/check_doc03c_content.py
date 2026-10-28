"""DOC-03C: read-only long-form development handbook gate.

No import of scantopath, Qt, SDK or database. Evidence must stay outside repo.
This checks mechanical consistency; operator still reviews usability and Windows Full.
"""
from __future__ import annotations

import argparse
import csv
import json
from pathlib import Path
import re
import sys

BASELINE = 'a847faebe54050cd6f8bc42cc882b3927ddabfe2'
DOCS = {
    'CAI_DAT_VA_CHAY.md': ('pyproject.toml', 'cmake', 'CTest', 'Python 3.12',
                          'PySide6', 'build-orbbec', 'SCANTOPATH_BUILD_ORBBEC_SOURCE',
                          'migrate', 'NOT_TESTED'),
    'HUONG_DAN_PHAT_TRIEN.md': ('SceneDescriptor', 'PLY', 'RAW', 'SQLite',
                               'Git', 'rollback', 'git diff --cached --check',
                               'tests/', 'NOT_TESTED'),
    'TIEU_CHUAN_KY_THUAT.md': ('Python', 'C++20', 'Qt', 'ACK', 'COMMITTED',
                              'source-of-truth', 'ADR', 'NOT_TESTED'),
    'KIEM_THU_VA_NGHIEM_THU.md': ('Quick', 'Full', 'Acceptance', 'JUNIT_POLICY',
                                 'CTEST_RELEASE', 'PENDING_MANUAL', 'NOT_TESTED',
                                 'scripts/verify.ps1', 'R8_5_AUDIT'),
}
SOURCE_PATHS = (
    'pyproject.toml', 'cpp/CMakeLists.txt',
    'src/scantopath/ui/main.py', 'src/scantopath/ui/shell/main_window.py',
    'src/scantopath/cli.py', 'src/scantopath/metadata/cli.py',
    'src/scantopath/acquisition/capture_once.py',
    'src/scantopath/modules/viewer3d/application/scene_contracts.py',
    'src/scantopath/modules/viewer3d/infrastructure/resident_poc/async_session.py',
    'src/scantopath/storage/session_store.py',
    'src/scantopath/modules/project_workspace/application/service.py',
    'scripts/verify.ps1', 'scripts/r8_4_verify.py',
    'scripts/r8_5_audit.py', 'scripts/check_qt_acceptance_xml.py',
    'tests/integration/viewer/test_gd1_08_03_ply.py',
    'tests/ui/viewer/test_gd1_08_03_qt.py',
    'tests/contracts/quality/test_gd1_r8_5_audit.py',
    'tests/contracts/nghiem_thu/test_gd1_r8_3_skip_policy.py',
)
LEGACY_COMPATIBILITY = (
    'docs/README.md', 'docs/02-kien-truc/KIEN_TRUC_HE_THONG.md',
    'docs/03-modules/VIEWER_3D.md', 'docs/03-modules/PROJECT_WORKSPACE.md',
    'docs/04-phat-trien/CAI_DAT_VA_CHAY.md',
    'docs/04-phat-trien/HUONG_DAN_PHAT_TRIEN.md',
    'docs/04-phat-trien/KIEM_THU_VA_NGHIEM_THU.md',
    'docs/04-phat-trien/TIEU_CHUAN_KY_THUAT.md',
    'docs/04-phat-trien/TIEU_CHUAN_KY_THUAT.md',
    'docs/07-nghiem-thu/records/GD1_R6_ACCEPTANCE_STATUS.md',
)
LINK = re.compile(r'(?<!!)\[[^\]]+\]\(([^)]+)\)')


def markdown_link_errors(root: Path, relative: str, body: str) -> list[str]:
    errors = []
    path = root / relative
    for item in LINK.findall(body):
        ref = item.split(' "')[0].strip()
        if ref.startswith(('http://', 'https://', 'mailto:', '#')):
            continue
        target = ref.split('#', 1)[0].split('?', 1)[0]
        if not target:
            continue
        if (target.startswith(('/', '\\')) or '\\' in target or
            re.match(r'^[A-Za-z]:', target)):
            errors.append('UNSAFE_LINK:' + relative + ':' + ref)
            continue
        resolved = (path.parent / target).resolve()
        if not resolved.is_relative_to(root.resolve()):
            errors.append('LINK_ESCAPES_REPO:' + relative + ':' + ref)
        elif not resolved.is_file() or resolved.is_symlink():
            errors.append('BROKEN_LINK:' + relative + ':' + ref)
    return errors


def doc_errors(name: str, data: str) -> list[str]:
    path = 'docs/04-phat-trien/' + name
    errors = []
    if not data.startswith('# ') or len(data) < 7000 or len(data.splitlines()) < 70:
        errors.append('INSUFFICIENT_HANDBOOK:' + path)
    for term in (BASELINE, '2026-10-28', 'owner:', 'source-of-truth:',
                 'evidence_level:', 'Giới hạn', '```powershell', 'if ($LASTEXITCODE -ne 0)'):
        if term.lower() not in data.lower():
            errors.append('MISSING_HANDBOOK_ELEMENT:' + path + ':' + term)
    for term in DOCS[name]:
        if term.lower() not in data.lower():
            errors.append('MISSING_CONTRACT_CONTEXT:' + path + ':' + term)
    for forbidden in ('[CẦN BỔ SUNG]', 'R6_OVERALL_PASS', 'tests/test_',
                      'Full Windows đã PASS', 'HMI đã PASS'):
        if forbidden in data:
            errors.append('PREMATURE_OR_OBSOLETE_CLAIM:' + path + ':' + forbidden)
    return errors


def verify(root: Path) -> dict:
    root = root.resolve(strict=True)
    errors: list[str] = []
    checked = 0
    for name in DOCS:
        rel = 'docs/04-phat-trien/' + name
        path = root / rel
        if not path.is_file() or path.is_symlink():
            errors.append('MISSING_DOC:' + rel)
            continue
        try:
            data = path.read_text(encoding='utf-8')
        except UnicodeError:
            errors.append('BAD_UTF8:' + rel)
            continue
        checked += 1
        errors += doc_errors(name, data)
        errors += markdown_link_errors(root, rel, data)
    portal = root / 'docs/README.md'
    if not portal.is_file() or portal.is_symlink():
        errors.append('PORTAL_MISSING')
    else:
        data = portal.read_text(encoding='utf-8')
        errors += markdown_link_errors(root, 'docs/README.md', data)
        for name in DOCS:
            if '04-phat-trien/' + name not in data:
                errors.append('PORTAL_MISSING_DOC03C:' + name)
        for required in ('DOC-03B', 'DOC-03C', 'DOC-04', 'DOC-05',
                         '7a0df7c5b596ff8750bf91f47310067c53a8b204'):
            if required not in data:
                errors.append('OLD_PORTAL_CONTRACT_MISSING:' + required)
    for path in SOURCE_PATHS + LEGACY_COMPATIBILITY:
        p = root / path
        if not p.is_file() or p.is_symlink():
            errors.append('EVIDENCE_OR_ALIAS_MISSING:' + path)
    mapping = root / 'docs/standardization/DOC02_BAN_DO_65.csv'
    if not mapping.is_file():
        errors.append('DOC02_MAP_MISSING')
    else:
        with mapping.open(encoding='utf-8-sig', newline='') as f:
            rows = list(csv.DictReader(f))
        expected = {'docs/04-phat-trien/' + name for name in DOCS}
        actual = {x['primary_target'] for x in rows if x['stage'] == 'DOC-03C'}
        if not expected.issubset(actual):
            errors.append('DOC02_DOC03C_TARGETS_MISSING:' + str(sorted(expected - actual)))
        for doc_id in ('DOC-031', 'DOC-032', 'DOC-033', 'DOC-034', 'DOC-035', 'DOC-036'):
            if not any(x['id'] == doc_id and x['stage'] == 'DOC-03C' for x in rows):
                errors.append('DOC02_TRACE_MISSING:' + doc_id)
    report = root / 'docs/standardization/DOC03C_TRUY_VET_VA_BAN_GIAO.md'
    if not report.is_file() or report.is_symlink():
        errors.append('HANDOVER_MISSING')
    else:
        t = report.read_text('utf-8')
        errors += markdown_link_errors(root, 'docs/standardization/DOC03C_TRUY_VET_VA_BAN_GIAO.md', t)
        if BASELINE not in t or 'WINDOWS_OPERATOR_VERIFICATION_PENDING' not in t:
            errors.append('HANDOVER_PROVENANCE_MISSING')
    return {'schema': 'scantopath-doc03c-content-v1', 'source_commit': BASELINE,
            'status': 'PASS' if not errors else 'FAIL', 'docs_checked': checked,
            'source_paths_checked': len(SOURCE_PATHS), 'legacy_compatibility': len(LEGACY_COMPATIBILITY),
            'windows_full': 'NOT_TESTED', 'manual_hmi': 'NOT_TESTED', 'errors': errors}


def main() -> int:
    p = argparse.ArgumentParser(description='DOC-03C static content gate; no device/DB access')
    p.add_argument('--project-root', type=Path, required=True)
    p.add_argument('--out-dir', type=Path, required=True)
    a = p.parse_args()
    try:
        root = a.project_root.resolve(strict=True)
        out = a.out_dir.resolve()
        if out == root or out.is_relative_to(root):
            raise ValueError('EVIDENCE_MUST_BE_OUTSIDE_REPOSITORY')
        result = verify(root)
        out.mkdir(parents=True, exist_ok=True)
        (out / 'DOC03C_CONTENT_GATE.json').write_text(
            json.dumps(result, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
        print('DOC-03C', result['status'], 'docs', result['docs_checked'],
              'source', result['source_paths_checked'], 'errors', len(result['errors']), flush=True)
        for error in result['errors']:
            print('DOC03C ERROR:', error, flush=True)
        return 0 if result['status'] == 'PASS' else 1
    except (OSError, ValueError, RuntimeError, UnicodeError, KeyError, csv.Error) as exc:
        print('DOC03C GATE ERROR:', repr(exc), file=sys.stderr)
        return 2


if __name__ == '__main__':
    raise SystemExit(main())
