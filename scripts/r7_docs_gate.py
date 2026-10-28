"""R7 documentation gate: canonical links, history, AST-semantic invariance.

No Qt, VTK, camera or persistent store is opened. It never edits repository files.
"""
from __future__ import annotations

import argparse
import ast
import json
import io
import tokenize
from pathlib import Path
import re
import subprocess
from datetime import datetime, timezone

BASELINE = 'ff45ccf87ce770e25eedf6e12df6bb5aaa958734'
R7_LOCK = 'b6369dfc07a3e0f9551408219815a9ff980085f5'
CANONICAL = (
    'docs/README.md',
    'docs/02-kien-truc/KIEN_TRUC_HE_THONG.md',
    'docs/03-modules/VIEWER_3D.md',
    'docs/03-modules/PROJECT_WORKSPACE.md',
    'docs/04-phat-trien/TIEU_CHUAN_KY_THUAT.md',
    'docs/04-phat-trien/KIEM_THU_VA_NGHIEM_THU.md',
    'docs/05-quan-ly/QUYET_DINH_KY_THUAT.md',
    'docs/07-nghiem-thu/records/GD1_R6_ACCEPTANCE_STATUS.md',
    'docs/99-lich-su/JOURNALS/DEVELOPMENT_MASTER_LOG.md',
    'docs/99-lich-su/JOURNALS/GD0_EXECUTION_JOURNAL.md',
    'docs/99-lich-su/JOURNALS/GD1_EXECUTION_JOURNAL.md',
    'docs/99-lich-su/JOURNALS/GD1_INCIDENT_REGISTER.md',
)
# DOC-05: v1 canonical paths stay intact for legacy R7 test contracts.
# Validate the additional v2 routes independently; never change checks length.
CANONICAL_V2 = (
    'docs/README.md',
    'docs/99-lich-su/README.md',
    'docs/99-lich-su/STANDARDIZATION/README.md',
    'docs/99-lich-su/ADR/ADR_001_UI_FIRST.md',
    'docs/05-quan-ly/TRANG_THAI_DU_AN.md',
    'docs/07-nghiem-thu/GD1_ACCEPTANCE.md',
)
R7_DOCSTRINGS = (
    'src/scantopath/ui/shell/main_window.py',
    'src/scantopath/modules/viewer3d/presentation/interactive_controller.py',
)
LINK_RE = re.compile(r'(?<!!)\[[^\]]+\]\(([^\s)]+)(?:\s+[^)]*)?\)')


def _git(root: Path, *args: str) -> bytes:
    proc = subprocess.run(['git', *args], cwd=root, stdout=subprocess.PIPE,
                          stderr=subprocess.PIPE, check=False)
    if proc.returncode:
        raise RuntimeError('git ' + ' '.join(args) + ': ' + proc.stderr.decode(errors='replace')[:180])
    return proc.stdout


def _semantics(raw: bytes) -> str:
    tree = ast.parse(raw.decode('utf-8-sig'))
    if tree.body and isinstance(tree.body[0], ast.Expr) and isinstance(tree.body[0].value, ast.Constant) and isinstance(tree.body[0].value.value, str):
        tree.body.pop(0)
    return ast.dump(tree, annotate_fields=True, include_attributes=False)


def audit(root: Path) -> dict:
    root = root.resolve(strict=True)
    errors: list[str] = []
    checks = {}
    git_root = Path(_git(root, 'rev-parse', '--show-toplevel').decode().strip()).resolve()
    if git_root != root:
        errors.append('PROJECT_ROOT_NOT_GIT_ROOT')
    initial = _git(root, 'rev-parse', BASELINE + '^{commit}').decode().strip()
    if initial != BASELINE:
        errors.append('BASELINE_NOT_PRESENT')

    for rel in CANONICAL:
        path = root / rel
        if not path.is_file() or path.is_symlink():
            errors.append('MISSING_OR_SYMLINK:' + rel)
            continue
        content = path.read_text(encoding='utf-8-sig')
        checks[rel] = {'bytes': len(path.read_bytes()), 'links': 0}
        if not content.startswith('# ') or '\ufffd' in content:
            errors.append('MARKDOWN_ENCODING_OR_TITLE:' + rel)
        if any(mark in content for mark in ('<<<<<<< ', '=======\n', '>>>>>>> ')):
            errors.append('MERGE_CONFLICT:' + rel)
        for target in LINK_RE.findall(content):
            if target.startswith(('http:', 'https:', 'mailto:', '#')):
                continue
            filepath = target.split('#', 1)[0].split('?', 1)[0]
            if not filepath:
                continue
            link = (path.parent / filepath).resolve()
            if not link.is_relative_to(root) or not link.is_file():
                errors.append('BROKEN_LINK:' + rel + ' -> ' + target)
            checks[rel]['links'] += 1
    v2_checks = {}
    for rel in CANONICAL_V2:
        path = root / rel
        if not path.is_file() or path.is_symlink():
            errors.append('V2_MISSING_OR_SYMLINK:' + rel)
            continue
        body = path.read_text(encoding='utf-8-sig')
        v2_checks[rel] = {'bytes': len(path.read_bytes()), 'links': 0}
        if not body.startswith('# ') or '\ufffd' in body:
            errors.append('V2_MARKDOWN_ENCODING_OR_TITLE:' + rel)
        for target in LINK_RE.findall(body):
            if target.startswith(('http:', 'https:', 'mailto:', '#')):
                continue
            target_path = target.split('#', 1)[0].split('?', 1)[0]
            if not target_path:
                continue
            link = (path.parent / target_path).resolve()
            if not link.is_relative_to(root) or not link.is_file():
                errors.append('V2_BROKEN_LINK:' + rel + ' -> ' + target)
            v2_checks[rel]['links'] += 1
    summary = (root / 'docs/07-nghiem-thu/records/GD1_R6_ACCEPTANCE_STATUS.md').read_text(encoding='utf-8')
    for mark in ('14/14', '618', '3 skipped', '2/2', 'PENDING', 'NOT_TESTED', 'OPERATOR_REPORTED'):
        if mark not in summary:
            errors.append('R6_EVIDENCE_STATUS_MISSING:' + mark)
    master = (root / 'docs/99-lich-su/JOURNALS/DEVELOPMENT_MASTER_LOG.md').read_text(encoding='utf-8')
    for mark in ('R4.1', 'R5.1', 'R5.2', 'R5.3', 'R6', 'R7', 'R8', 'ff45ccf'):
        if mark not in master:
            errors.append('HISTORY_MILESTONE_MISSING:' + mark)
    incident = (root / 'docs/99-lich-su/JOURNALS/GD1_INCIDENT_REGISTER.md').read_text(encoding='utf-8')
    for mark in ('INC-GD1-R6-RUNNER-001', 'INC-GD1-R6-RUNNER-002', 'INC-GD1-R5-001'):
        if mark not in incident:
            errors.append('INCIDENT_MISSING:' + mark)
    readme = (root / 'README.md').read_text(encoding='utf-8')
    if '[Tài liệu GĐ1 hiện hành](docs/README.md)' not in readme:
        errors.append('README_CANONICAL_LINK_MISSING')
    # Verify historical R7 documentation-only semantics, not later runtime changes.
    for rel in R7_DOCSTRINGS:
        r7_content = _git(root, 'show', R7_LOCK + ':' + rel)
        original = _git(root, 'show', BASELINE + ':' + rel)
        if _semantics(r7_content) != _semantics(original):
            errors.append('EXECUTABLE_AST_CHANGED:' + rel)
        if ast.get_docstring(ast.parse(r7_content.decode('utf-8-sig'))) == ast.get_docstring(ast.parse(original.decode('utf-8-sig'))):
            errors.append('R7_DOCSTRING_NOT_UPDATED:' + rel)
    return {'schema': 'scantopath-r7-documentation-gate-v1', 'baseline_sha': BASELINE,
            'timestamp_utc': datetime.now(timezone.utc).isoformat(),
            'status': 'PASS' if not errors else 'FAIL', 'checks': checks, 'v2_checks': v2_checks,
            'ast_docstring_only': not any(x.startswith('EXECUTABLE_AST_CHANGED') for x in errors),
            'errors': errors, 'limitations': 'Static metadata and AST gate only; no Windows HMI, source audit completeness or external evidence verification.'}


def comment_inventory(root: Path) -> dict:
    """Audit only: count existing source docs/comments without rewriting code."""
    folder = root / 'src/scantopath'
    files = sorted(folder.rglob('*.py'))
    rows = []
    total_comments = 0
    missing = []
    for path in files:
        rel = path.relative_to(root).as_posix()
        data = path.read_bytes()
        try:
            tree = ast.parse(data.decode('utf-8-sig'))
            comments = sum(tok.type == tokenize.COMMENT for tok in tokenize.tokenize(io.BytesIO(data).readline))
        except (SyntaxError, UnicodeDecodeError, tokenize.TokenError) as exc:
            missing.append({'file': rel, 'parse_error': type(exc).__name__})
            continue
        documented = ast.get_docstring(tree) is not None
        rows.append({'file': rel, 'lines': len(data.splitlines()),
                     'comment_tokens': comments, 'has_module_docstring': documented})
        total_comments += comments
    return {'source_python_files': len(files), 'analyzed': len(rows),
            'comment_tokens': total_comments,
            'module_docstrings': sum(row['has_module_docstring'] for row in rows),
            'missing_module_docstrings': sorted(row['file'] for row in rows if not row['has_module_docstring']),
            'highest_comment_counts': sorted(rows, key=lambda v: (-v['comment_tokens'], v['file']))[:20],
            'parse_failures': missing,
            'limitation': 'Inventory only. Comment quantity is not an SRP/quality score; do not delete safety comments automatically.'}


def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument('--project-root', required=True, type=Path)
    p.add_argument('--out-dir', required=True, type=Path)
    a = p.parse_args()
    result = audit(a.project_root)
    inventory = comment_inventory(a.project_root)
    a.out_dir.mkdir(parents=True, exist_ok=True)
    (a.out_dir / 'R7_COMMENT_INVENTORY.json').write_text(
        json.dumps(inventory, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    output = a.out_dir / 'R7_DOC_GATE.json'
    output.write_text(json.dumps(result, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    print('R7 SOURCE INVENTORY', inventory['source_python_files'], 'source files,',
          inventory['module_docstrings'], 'module docstrings,', inventory['comment_tokens'], 'comment tokens')
    print('R7_DOC_GATE', result['status'], 'canonical_docs', len(result['checks']),
          'errors', len(result['errors']), 'evidence', output)
    for issue in result['errors']:
        print('R7_ISSUE', issue)
    return 0 if result['status'] == 'PASS' else 1


if __name__ == '__main__':
    raise SystemExit(main())
