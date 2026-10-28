"""R8.3: cổng tĩnh bảo vệ scope, cấu trúc test và chính sách SKIP."""
from __future__ import annotations

import argparse
import ast
import json
from pathlib import Path
import subprocess
import sys

from check_qt_acceptance_xml import REQUIRED, _ALLOWED
from r8_2_structure_gate import verify as verify_r82

BASE = 'c4bbf11145626b07e27950b4c720bd6fffcfadb2'
R52 = 'tests/ui/viewer/test_gd1_r5_2_live_viewer.py'


def _git(root: Path, *args: str) -> str:
    proc = subprocess.run(['git', *args], cwd=root, capture_output=True, text=True,
                          encoding='utf-8', errors='replace')
    if proc.returncode:
        raise RuntimeError('GIT_FAILED:' + ' '.join(args) + ':' + proc.stderr[:150])
    return proc.stdout


def _tests(source: str) -> list[str]:
    return sorted(n.name for n in ast.walk(ast.parse(source))
                  if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef))
                  and n.name.startswith('test_'))


def verify(root: Path) -> dict:
    root = root.resolve(strict=True)
    errors: list[str] = []
    structure = verify_r82(root)
    if structure['status'] != 'PASS':
        errors.append('R82_GATE:' + ';'.join(structure['errors'][:4]))
    if len(REQUIRED) != 4 or len(_ALLOWED) != 3 or len(set(_ALLOWED)) != 3:
        errors.append('SKIP_POLICY_COUNT_CHANGED')
    try:
        previous = _git(root, 'show', f'{BASE}:{R52}')
        current = (root / R52).read_text(encoding='utf-8-sig')
        if _tests(previous) != _tests(current):
            errors.append('R52_OLD_TEST_NAMES_CHANGED')
        target = next(n for n in ast.parse(current).body
                      if isinstance(n, ast.FunctionDef)
                      and n.name == 'test_r52_composition_root_contains_bounded_close_gate')
        if not any(isinstance(x, ast.Call) and isinstance(x.func, ast.Attribute)
                   and x.func.attr == 'parse' for x in ast.walk(target)):
            errors.append('R52_EXPECTS_AST_CONTRACT')
        if "assert 'LiveViewer3DController(' in bootstrap" in ast.get_source_segment(current, target):
            errors.append('R52_STILL_TEXT_COUPLED')
    except (ValueError, StopIteration, OSError, SyntaxError) as exc:
        errors.append('R52_CHECK_ERROR:' + repr(exc))
    try:
        for p in ('tests/support/raw_fixture.py', 'tests/support/project_seed.py'):
            tree = ast.parse((root / p).read_text('utf-8'))
            if any(isinstance(n, ast.ImportFrom) and (n.module or '').startswith('test_')
                   for n in ast.walk(tree)):
                errors.append('FIXTURE_IMPORTS_TEST:' + p)
        for p in ('tests/contracts/nghiem_thu/test_gd1_r8_3_skip_policy.py',
                  'tests/contracts/quality/test_gd1_r8_3_contracts.py'):
            if not (root / p).is_file():
                errors.append('MISSING_R83_TEST:' + p)
    except (OSError, SyntaxError) as exc:
        errors.append('R83_SUPPORT_ERROR:' + repr(exc))
    return {'schema': 'scantopath-r8-3-contract-gate-v1',
            'baseline': BASE, 'status': 'PASS' if not errors else 'FAIL',
            'r82_test_count_static': structure['test_functions_static'],
            'allowed_skip_ids': len(_ALLOWED), 'errors': errors}


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument('--project-root', type=Path, required=True)
    ap.add_argument('--out-dir', type=Path, required=True)
    a = ap.parse_args()
    root = a.project_root.resolve(strict=True)
    out = a.out_dir.resolve()
    if out == root or out.is_relative_to(root):
        raise RuntimeError('EVIDENCE_MUST_BE_OUTSIDE_REPOSITORY')
    result = verify(root)
    out.mkdir(parents=True, exist_ok=True)
    (out / 'R83_CONTRACT_GATE.json').write_text(
        json.dumps(result, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    print('R8.3 CONTRACT GATE:', result['status'], 'issues', len(result['errors']))
    for error in result['errors']:
        print('R8.3 ISSUE:', error)
    return 0 if result['status'] == 'PASS' else 1


if __name__ == '__main__':
    try:
        sys.exit(main())
    except (OSError, ValueError, RuntimeError, SyntaxError) as exc:
        print('R8.3 GATE FAILED:', repr(exc))
        sys.exit(1)
