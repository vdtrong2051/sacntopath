"""R7-C: kiểm tra tài liệu và bất biến AST, không cần camera hoặc Qt."""
from __future__ import annotations

import ast
import json
from pathlib import Path
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]
BASE = 'f923d1e4852f8f36c6b0c7c2c20ecee4dbcf91d1'
FILES = [
    'src/scantopath/acquisition/native.py',
    'src/scantopath/storage/session_store.py',
    'src/scantopath/metadata/store.py',
    'src/scantopath/modules/project_workspace/application/service.py',
    'src/scantopath/modules/viewer3d/infrastructure/resident_poc/protocol.py',
    'src/scantopath/modules/viewer3d/infrastructure/resident_poc/client.py',
    'src/scantopath/modules/viewer3d/infrastructure/resident_poc/async_session.py',
    'src/scantopath/ui/shell/viewer_bootstrap.py',
]


def _normalized(data: bytes) -> str:
    tree = ast.parse(data.decode('utf-8-sig'))
    for node in ast.walk(tree):
        if isinstance(node, (ast.Module, ast.ClassDef, ast.FunctionDef, ast.AsyncFunctionDef)):
            if node.body and isinstance(node.body[0], ast.Expr) and isinstance(node.body[0].value, ast.Constant) and isinstance(node.body[0].value.value, str):
                node.body.pop(0)
    return ast.dump(tree, include_attributes=False)


def test_r7c_logic_ast_unchanged():
    for f in FILES:
        original = subprocess.check_output(['git', 'show', f'{BASE}:{f}'], cwd=ROOT)
        assert _normalized(original) == _normalized((ROOT / f).read_bytes()), f


def test_r7c_source_docstrings_are_vietnamese():
    for f in FILES:
        doc = ast.get_docstring(ast.parse((ROOT / f).read_text('utf-8-sig')))
        assert doc is not None, f
        assert any(ch in doc for ch in 'ăâđêôơưĂÂĐÊÔƠƯáạủệ'), f


def test_r7c_history_references_r7a_r7b_commits():
    s = (ROOT / 'docs/history/DEVELOPMENT_MASTER_LOG.md').read_text('utf-8')
    assert '8e37eba' in s and 'f923d1e' in s
    assert 'R6' in s and '618' in s and '3 SKIP' in s


def test_r7c_incident_history_preserves_both_runner_failures():
    s = (ROOT / 'docs/history/GD1/INCIDENT_REGISTER.md').read_text('utf-8')
    assert 'INC-GD1-R6-RUNNER-001' in s
    assert 'INC-GD1-R6-RUNNER-002' in s
    assert '$args' in s and 'ctest -C Release' in s


def test_r7c_does_not_claim_overall_r6_pass():
    s = (ROOT / 'docs/history/GD1/GD1_EXECUTION_JOURNAL.md').read_text('utf-8')
    assert '14/14 PASS' in s and 'PENDING' in s
    assert '100/125/150%' in s and 'C++' in s


def test_r7c_inventory_tool_is_standard_library_only():
    sys.path.insert(0, str(ROOT / 'scripts'))
    import r7c_comment_audit
    result = r7c_comment_audit.inspect(ROOT)
    count = len(list((ROOT / 'src/scantopath').rglob('*.py')))
    assert result['so_tap_python'] == count
    assert len(result['tap_tin']) == count
    assert not result['loi_doc']


def test_r7c_history_entry_is_linked_from_index():
    entry = (ROOT / 'docs/history/README.md').read_text('utf-8')
    assert 'DEVELOPMENT_MASTER_LOG.md' in entry
    assert 'QUY_UOC_GHI_NHAT_KY.md' in entry


def test_r7c_change_scope_is_documentation_only():
    s = (ROOT / 'docs/standardization/R7C_PHAM_VI_VA_DOI_CHIEU.md').read_text('utf-8')
    assert 'AST' in s and 'R6' in s
