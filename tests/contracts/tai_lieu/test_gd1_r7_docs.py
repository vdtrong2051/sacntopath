"""R7 documentation contracts: no Qt, native hardware, RAW writes or SQL access."""
from __future__ import annotations

import ast
from pathlib import Path
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[3]
SCRIPTS = ROOT / 'scripts'
sys.path.insert(0, str(SCRIPTS))
from r7_docs_gate import audit, BASELINE, CANONICAL, R7_DOCSTRINGS


def _check():
    return audit(ROOT)


def test_r7_canonical_docs_gate_passes():
    report = _check()
    assert report['status'] == 'PASS', report['errors']
    assert len(report['checks']) == len(CANONICAL)


def test_r7_module_docstrings_do_not_modify_executable_ast():
    for rel in R7_DOCSTRINGS:
        src = (ROOT / rel).read_text('utf-8')
        before = subprocess.check_output(['git', 'show', BASELINE + ':' + rel], cwd=ROOT).decode()
        def normalize(s):
            tree = ast.parse(s)
            tree.body.pop(0)
            return ast.dump(tree, include_attributes=False)
        assert normalize(src) == normalize(before)
        assert ast.get_docstring(ast.parse(src)) != ast.get_docstring(ast.parse(before))


def test_r7_readme_routes_to_current_docs():
    assert '[Tài liệu GĐ1 hiện hành](docs/README.md)' in (ROOT / 'README.md').read_text('utf8')


def test_r7_does_not_rewrite_historical_roadmap():
    assert (ROOT / 'docs/99-lich-su/ARCHIVE/ROADMAP_CU/ROADMAP_V1_ARCHIVED.md').is_file()
    assert '08.06.6' in (ROOT / 'docs/README.md').read_text('utf8')


def test_r7_r6_automated_is_not_overall():
    r = (ROOT / 'docs/07-nghiem-thu/records/GD1_R6_ACCEPTANCE_STATUS.md').read_text('utf8')
    assert 'R6_AUTOMATED_PASS / R6_OVERALL_PENDING' in r
    assert 'NOT_TESTED' in r and 'OPERATOR_REPORTED' in r


def test_r7_history_preserves_runner_failures():
    r = (ROOT / 'docs/99-lich-su/JOURNALS/GD1_INCIDENT_REGISTER.md').read_text('utf8')
    assert 'INC-GD1-R6-RUNNER-001' in r and 'INC-GD1-R6-RUNNER-002' in r
    assert '$args' in r and 'ExitCode' in r


def test_r7_doc_gate_rejects_modified_native_logic(tmp_path):
    # Deterministically verifies a single file is detected as changed without writing repo.
    from r7_docs_gate import _semantics
    original = b'"""original"""\nfrom __future__ import annotations\nx = 5\n'
    changed_doc = b'"""documented"""\nfrom __future__ import annotations\nx = 5\n'
    altered = b'"""documented"""\nfrom __future__ import annotations\nx = 6\n'
    assert _semantics(original) == _semantics(changed_doc)
    assert _semantics(original) != _semantics(altered)


def test_r7_history_has_stage_links():
    master = (ROOT / 'docs/99-lich-su/JOURNALS/DEVELOPMENT_MASTER_LOG.md').read_text('utf8')
    assert 'GD0_EXECUTION_JOURNAL.md' in master
    assert 'GD1_EXECUTION_JOURNAL.md' in master
    assert 'INCIDENT_REGISTER.md' in master


def test_r7_no_new_toolchain_or_runtime_dependencies():
    # Changes in R7 are documentation and standard-library tooling only.
    p = (ROOT / 'scripts/r7_docs_gate.py').read_text('utf8')
    for forbidden in ('import vtk', 'import PySide6', 'import sqlite3', 'import open3d'):
        assert forbidden not in p
