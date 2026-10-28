"""DOC-04 documentation-only content gate; no camera/SQLite/native access.

Reads docs, DOC-02 CSV and source path existence. Writes a JSON receipt only
outside the repo; never upgrades acceptance status or modifies source.
"""
from __future__ import annotations

import argparse
import csv
import json
import re
import sys
from pathlib import Path

BASELINE = '81da5d2050324b1dc4a65ffbca9a38ed1ebba10a'
SCHEMA = 'scantopath-doc04-content-v1'
FILES = (
    'docs/05-quan-ly/TASK_REGISTER.md',
    'docs/05-quan-ly/TRANG_THAI_DU_AN.md',
    'docs/05-quan-ly/QUYET_DINH_KY_THUAT.md',
    'docs/05-quan-ly/INCIDENT_REGISTER.md',
    'docs/06-giai-doan/GD0_SOFTWARE_FOUNDATION.md',
    'docs/06-giai-doan/GD1_DESKTOP_VIEWER.md',
    'docs/06-giai-doan/SESSION_CROSSWALK.md',
    'docs/07-nghiem-thu/GD0_ACCEPTANCE.md',
    'docs/07-nghiem-thu/GD1_ACCEPTANCE.md',
    'docs/07-nghiem-thu/EVIDENCE_INDEX.md',
    'docs/07-nghiem-thu/records/GD1_R6_ACCEPTANCE_STATUS.md',
)
REQUIRED_SOURCE_PATHS = (
    'docs/standardization/DOC02_BAN_DO_65.csv',
    'docs/standardization/DOC02_TRUY_VET_43.csv',
    'docs/standardization/DOC02_QUYET_DINH_20.csv',
    'docs/archive/GD0/PRE/PRE_06_GD0_ACCEPTANCE.md',
    'docs/acceptance/GD1_R6_ACCEPTANCE_STATUS.md',
    'docs/archive/GD1/08/08_06_5_DEFECT_DISPOSITION_AND_HMI_WAIVER.md',
    'docs/decisions/ADR_001_UI_FIRST.md',
    'docs/decisions/ADR_002_NUMBERED_STORAGE_LAYOUT.md',
    'docs/history/GD1/INCIDENT_REGISTER.md',
    'docs/04-phat-trien/TIEU_CHUAN_KY_THUAT.md',
    'docs/01-tong-quan/LO_TRINH_PHAT_TRIEN.md',
    'src/scantopath/storage/numbered.py',
    'src/scantopath/storage/legacy_migration.py',
    'src/scantopath/metadata/store.py',
    'src/scantopath/modules/viewer3d/application/scene_contracts.py',
    'scripts/verify.ps1',
    'scripts/r8_4_verify.py',
    'scripts/r8_5_audit.py',
    'tests/contracts/tai_lieu/test_doc03c_content.py',
)
PORTAL = 'docs/README.md'
HANDOVER = 'docs/standardization/DOC04_TRUY_VET_VA_BAN_GIAO.md'
STANDARD = 'docs/04-phat-trien/TIEU_CHUAN_KY_THUAT.md'
LINK = re.compile(r'(?<!!)\[[^\]]+\]\(([^)]+)\)')
EXPECTED_MAPPED_TARGETS = {
    'docs/05-quan-ly/TASK_REGISTER.md',
    'docs/05-quan-ly/TRANG_THAI_DU_AN.md',
    'docs/05-quan-ly/QUYET_DINH_KY_THUAT.md',
    'docs/05-quan-ly/INCIDENT_REGISTER.md',
    'docs/06-giai-doan/GD0_SOFTWARE_FOUNDATION.md',
    'docs/06-giai-doan/GD1_DESKTOP_VIEWER.md',
    'docs/06-giai-doan/SESSION_CROSSWALK.md',
    'docs/07-nghiem-thu/GD0_ACCEPTANCE.md',
    'docs/07-nghiem-thu/GD1_ACCEPTANCE.md',
    'docs/04-phat-trien/TIEU_CHUAN_KY_THUAT.md',
    'docs/01-tong-quan/LO_TRINH_PHAT_TRIEN.md',
    'docs/99-lich-su/ADR/ADR_001_UI_FIRST.md',
    'docs/99-lich-su/ADR/ADR_002_NUMBERED_STORAGE_LAYOUT.md',
    'docs/99-lich-su/JOURNALS/DEVELOPMENT_MASTER_LOG.md',
    'docs/99-lich-su/JOURNALS/GD0_EXECUTION_JOURNAL.md',
    'docs/99-lich-su/JOURNALS/GD1_EXECUTION_JOURNAL.md',
    'docs/99-lich-su/HO_SO_CU_VA_TRUY_VET.md',
    'docs/99-lich-su/README.md',
    'docs/02-kien-truc/CONG_NGHE_VA_PHU_THUOC.md',
}
REQUIRED = {
    FILES[0]: ('GD1-08-06-6', 'DOC-05', 'HW-CURRENT-BASELINE', 'acceptance_criteria', 'updated_at', 'owner', 'BLOCKED'),
    FILES[1]: ('R8_TEST_INFRA', 'DOCUMENTATION_V2', 'physical_manual_verification', 'GD1_OVERALL_PENDING', 'METRIC_SINGLE_VIEW_GD2'),
    FILES[2]: ('ADR-001', 'ADR-002', 'DEC-HW-CURRENT', 'OPEN_REQUIRED_SOURCE_DECISION', 'PARTIALLY_APPLIED'),
    FILES[3]: ('INC-GD1-R6-RUNNER-001', 'INC-GD1-R6-RUNNER-002', 'RISK-NATIVE-BUSY', 'RISK-GPU-PRESENT'),
    FILES[4]: ('PRE-06', '80 PASS', '2/2', 'measured', 'ProcessingRun'),
    FILES[5]: ('R4.5', 'R5.3', 'R8.5', '08.06.6', 'GD1_OVERALL_PENDING'),
    FILES[6]: ('01', '20+', '14', '15', '19', 'TASK_REGISTER'),
    FILES[7]: ('GD0-PYTEST', 'GD0-CAPTURE', 'GD0-SQLITE', '1 SKIP'),
    FILES[8]: ('HMI_DPI_100_125_150', 'CPP_NATIVE_BUSY_CLOSE', 'CPP_NATIVE_FAULT_ISOLATION', 'GPU_VRAM_MEASURED', 'INPUT_TO_PHYSICAL_PRESENT_LATENCY', 'NOT_TESTED', 'PENDING'),
    FILES[9]: ('E-GD0-PRE06', 'E-GD1-R6', 'E-GD1-08066', 'evidence_id', 'source_sha'),
    FILES[10]: ('618', '3 skipped', 'R6_AUTOMATED_PASS', 'R6_OVERALL_PENDING', 'NOT_TESTED'),
}


def markdown_link_errors(root: Path, path: Path, content: str) -> list[str]:
    errors = []
    absolute_root = root.resolve()
    for raw in LINK.findall(content):
        target = raw.split(' "', 1)[0].strip()
        if target.startswith(('https://', 'http://', 'mailto:', '#')):
            continue
        target = target.split('#', 1)[0].split('?', 1)[0]
        if not target:
            continue
        if target.startswith(('/', '\\')) or '\\' in target or re.match(r'^[A-Za-z]:', target):
            errors.append('UNSAFE_LINK:' + str(path) + ':' + raw)
            continue
        try:
            resolved = (path.parent / target).resolve()
            if not resolved.is_relative_to(absolute_root):
                errors.append('LINK_ESCAPES_REPO:' + str(path) + ':' + raw)
            elif not resolved.is_file():
                errors.append('BROKEN_LINK:' + str(path) + ':' + raw)
        except OSError as exc:
            errors.append('LINK_ERROR:' + str(path) + ':' + repr(exc))
    return errors


def document_errors(path: str, text: str) -> list[str]:
    errors = []
    if not text.startswith('# ') or len(text) < 1550 or text.count('## ') < 3:
        errors.append('TOO_SHORT_OR_UNSTRUCTURED:' + path)
    for token in (BASELINE, '2026-10-28', 'owner:', 'scope:', 'source-of-truth:', 'evidence_level:', 'Giới hạn'):
        if token.lower() not in text.lower():
            errors.append('MISSING_METADATA:' + path + ':' + token)
    for token in REQUIRED.get(path, ()):
        if token not in text:
            errors.append('MISSING_CONTRACT:' + path + ':' + token)
    if any(t in text for t in ('[CẦN BỔ SUNG]', 'R6_OVERALL_PASS', 'FINAL_ACCEPTANCE_PASS')):
        errors.append('TEMPLATE_OR_PREMATURE_PASS:' + path)
    return errors


def task_ids(text: str) -> list[str]:
    ids: list[str] = []
    for line in text.splitlines():
        if not line.startswith('| `'):
            continue
        m = re.match(r'^\| `([A-Z][A-Z0-9]*(?:-[A-Z0-9]+)+)` \|', line)
        if m:
            ids.append(m.group(1))
    return ids


def ledger_errors(texts: dict[str, str]) -> list[str]:
    errors = []
    register = texts.get(FILES[0], '')
    ids = task_ids(register)
    if len(ids) < 12 or len(set(ids)) != len(ids):
        errors.append('TASK_UNIQUE_ID_VIOLATION:' + repr(ids))
    for required in ('GD1-08-06-6', 'DOC-04', 'DOC-05', 'HW-CURRENT-BASELINE'):
        if required not in ids:
            errors.append('TASK_ID_MISSING:' + required)
    for path in (FILES[1], FILES[4], FILES[5], FILES[8]):
        body = texts.get(path, '')
        if not any(x in body for x in ('PENDING', 'NOT_TESTED', 'BLOCKED')):
            errors.append('MANUAL_BOUNDARY_MISSING:' + path)
    return errors


def mapping_errors(root: Path) -> list[str]:
    """Reconcile DOC-02 primary destinations, secondary route and CW trace.

    DOC-004 places the Task Register in its additional destination column.
    CW-24 owns the two stage dossiers; they were never primary destinations
    in the frozen DOC02_BAN_DO_65.csv. Never alter that frozen CSV to make
    a stage-local gate pass, and never waive a missing primary target.
    """
    mapping = root / 'docs/standardization/DOC02_BAN_DO_65.csv'
    trace = root / 'docs/standardization/DOC02_TRUY_VET_43.csv'
    with mapping.open('r', encoding='utf-8-sig', newline='') as stream:
        rows = list(csv.DictReader(stream))
    with trace.open('r', encoding='utf-8-sig', newline='') as stream:
        traces = list(csv.DictReader(stream))

    task = 'docs/05-quan-ly/TASK_REGISTER.md'
    gd0 = 'docs/06-giai-doan/GD0_SOFTWARE_FOUNDATION.md'
    gd1 = 'docs/06-giai-doan/GD1_DESKTOP_VIEWER.md'
    traced_targets = {task, gd0, gd1}
    primary = {r['primary_target'] for r in rows if r.get('stage') == 'DOC-04'}
    errors = []
    missing_primary = (EXPECTED_MAPPED_TARGETS - traced_targets) - primary
    if missing_primary:
        errors.append('DOC02_EXPECTED_PRIMARY_TARGET_ABSENT:' + ','.join(sorted(missing_primary)))

    # DOC-004: the Task Register is explicitly a secondary destination.
    parent = next((r for r in rows if r.get('id') == 'DOC-004' and
                   r.get('stage') == 'DOC-04'), None)
    if not parent or task not in parent.get('additional_destination_or_rule', ''):
        errors.append('DOC02_TASK_SECONDARY_DESTINATION_MISSING:' + task)

    # CW-22 and CW-24 are DOC-02's authoritative content-trace rows.
    for trace_id, expected in (('CW-22', {task}), ('CW-24', {gd0, gd1})):
        row = next((r for r in traces if r.get('id') == trace_id and
                    r.get('stage') == 'DOC-04' and r.get('type') == 'CONTENT'), None)
        actual = (set(row.get('target_documents', '').split(';')) if row else set())
        missing = expected - actual
        if missing:
            errors.append('DOC02_CONTENT_TRACE_MISSING:' + trace_id + ':' +
                          ','.join(sorted(missing)))
    return errors


def verify(root: Path) -> dict:
    root = root.resolve(strict=True)
    errors = []
    data: dict[str, str] = {}
    for name in (*FILES, PORTAL, HANDOVER, STANDARD):
        path = root / name
        if not path.is_file() or path.is_symlink():
            errors.append('FILE_MISSING_OR_SYMLINK:' + name)
            continue
        try:
            content = path.read_text(encoding='utf-8-sig')
        except UnicodeError:
            errors.append('BAD_UTF8:' + name)
            continue
        data[name] = content
        errors.extend(markdown_link_errors(root, path, content))
        if name in FILES or name == HANDOVER:
            errors.extend(document_errors(name, content))
    for path in REQUIRED_SOURCE_PATHS:
        target = root / path
        if not target.is_file() or target.is_symlink():
            errors.append('SOURCE_PATH_MISSING:' + path)
    errors.extend(ledger_errors(data))
    portal = data.get(PORTAL, '')
    for token in ('DOC-03B', 'DOC-03C', 'DOC-04', 'DOC-05',
                  '7a0df7c5b596ff8750bf91f47310067c53a8b204',
                  '05-quan-ly/TASK_REGISTER.md', '06-giai-doan/GD1_DESKTOP_VIEWER.md',
                  '07-nghiem-thu/GD1_ACCEPTANCE.md'):
        if token not in portal:
            errors.append('PORTAL_REGRESSION:' + token)
    standard = data.get(STANDARD, '')
    for token in ('## 10. Quy tắc ghi nhật ký', 'R6_OVERALL_PENDING', 'GD1_OVERALL_PENDING', 'DOC-04'):
        if token not in standard:
            errors.append('JOURNAL_STANDARD_MISSING:' + token)
    try:
        errors.extend(mapping_errors(root))
    except (OSError, csv.Error, KeyError) as exc:
        errors.append('MAPPING_ERROR:' + repr(exc))
    for path in ('docs/INDEX.md', 'docs/architecture/CURRENT_GD1_ARCHITECTURE.md',
                 'docs/modules/VIEWER3D.md', 'docs/modules/PROJECT_WORKSPACE.md',
                 'docs/development/ENGINEERING_STANDARDS.md',
                 'docs/development/R7_DOCUMENTATION_POLICY.md',
                 'docs/roadmap/ROADMAP_V1_ARCHIVED.md'):
        if not (root / path).is_file():
            errors.append('R7_COMPAT_ALIAS_MISSING:' + path)
    return {
        'schema': SCHEMA, 'baseline': BASELINE, 'status': 'PASS' if not errors else 'FAIL',
        'files_checked': len(FILES), 'source_paths_checked': len(REQUIRED_SOURCE_PATHS),
        'manual_hmi': 'NOT_TESTED', 'gd1_overall': 'PENDING_08_06_6', 'errors': errors,
    }


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser()
    p.add_argument('--project-root', required=True, type=Path)
    p.add_argument('--out-dir', required=True, type=Path)
    a = p.parse_args(argv)
    try:
        root = a.project_root.resolve(strict=True)
        output = a.out_dir.resolve()
        if output == root or output.is_relative_to(root):
            raise ValueError('EVIDENCE_MUST_BE_OUTSIDE_REPOSITORY')
        result = verify(root)
        output.mkdir(parents=True, exist_ok=True)
        (output / 'DOC04_CONTENT_GATE.json').write_text(
            json.dumps(result, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
        print('DOC04 CONTENT', result['status'], 'documents', result['files_checked'],
              'errors', len(result['errors']), flush=True)
        for error in result['errors']:
            print('DOC04 ERROR:', error, flush=True)
        return 0 if result['status'] == 'PASS' else 1
    except (OSError, ValueError, RuntimeError) as exc:
        print('DOC04 GATE ERROR:', repr(exc), file=sys.stderr)
        return 2


if __name__ == '__main__':
    raise SystemExit(main())
