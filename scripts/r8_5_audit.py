"""R8.5: Kiểm toán kiểm thử tĩnh, phát hiện ứng viên dư thừa mà không tự xóa.

Không import các module ScanToPath/Qt/VTK; chỉ đọc Git và mã nguồn.
Tất cả bằng chứng được xuất bên ngoài repository. Không chứng nhận HMI/native thực.
"""
from __future__ import annotations

import argparse
import ast
from collections import Counter, defaultdict
import copy
import csv
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import subprocess
import sys

BASELINE = '4a2df5938d8e82a3c7790acb2a251003d9224511'
SCHEMA = 'scantopath-r8-5-audit-v1'
EXPECT_TEST_FILES = 80
EXPECT_SCRIPT_FILES = 27
NEW_AUDIT_TEST = 'tests/contracts/quality/test_gd1_r8_5_audit.py'
NEW_AUDIT_SCRIPT = 'scripts/r8_5_audit.py'
GROUPS = ('unit', 'integration', 'contracts', 'ui', 'native', 'performance')
ACTIVE_GATES = frozenset({
    'scripts/verify.ps1', 'scripts/r8_4_verify.py', 'scripts/r8_5_audit.py',
    'scripts/r8_3_contracts_gate.py', 'scripts/r8_2_structure_gate.py',
    'scripts/r8_1_test_inventory.py', 'scripts/check_qt_acceptance_xml.py',
    'scripts/check_07_12_quality.py', 'scripts/check_architecture_boundaries.py',
    'scripts/r7_docs_gate.py',
})


def git(root: Path, *args: str) -> str:
    p = subprocess.run(['git', *args], cwd=root, capture_output=True,
                       encoding='utf-8', errors='replace', text=True, timeout=40)
    if p.returncode:
        raise RuntimeError('GIT_FAILED:' + ' '.join(args) + ':' + p.stderr[-250:])
    return p.stdout.strip()


def tests_and_scripts(paths: list[str]) -> tuple[list[str], list[str]]:
    tests = sorted(p for p in paths if p.startswith('tests/')
                   and Path(p).name.startswith('test_') and p.endswith('.py'))
    scripts = sorted(p for p in paths if p.startswith('scripts/')
                     and (p.endswith('.py') or p.endswith('.ps1')))
    return tests, scripts


def functions(code: str) -> list[str]:
    tree = ast.parse(code)
    return sorted(n.name for n in ast.walk(tree)
                  if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef))
                  and n.name.startswith('test_'))


def ast_test_shape(node: ast.FunctionDef | ast.AsyncFunctionDef) -> str:
    """Phát hiện dấu hiệu trùng AST; KHÔNG chứng minh trùng hành vi."""
    item = copy.deepcopy(node)
    item.name = '_candidate'
    return hashlib.sha256(ast.dump(item, include_attributes=False).encode('utf-8')).hexdigest()


def duplicate_candidates(source_by_path: dict[str, str]) -> list[dict]:
    groups: dict[str, list[str]] = defaultdict(list)
    for path, source in source_by_path.items():
        for node in ast.walk(ast.parse(source)):
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and node.name.startswith('test_'):
                groups[ast_test_shape(node)].append(path + '::' + node.name)
    return [
        {'kind':'SIMILAR_AST_TEST', 'members':sorted(members),
         'decision':'REVIEW_ONLY_NOT_DELETE'}
        for members in groups.values() if len(members)>1
    ]


def script_category(path: str) -> str:
    if path in ACTIVE_GATES:
        return 'ACTIVE_UNIFIED_GATE'
    if path == 'scripts/verify_gd1_r3_5.ps1':
        return 'LEGACY_ACCEPTANCE_COMPATIBILITY'
    if path.startswith(('scripts/r4_', 'scripts/r5_')) or path.startswith('scripts/probe_gd1_'):
        return 'HISTORICAL_NATIVE_OR_PERFORMANCE_DIAGNOSTIC'
    if path in {'scripts/gd1_architecture_audit.py', 'scripts/r7c_comment_audit.py'}:
        return 'HISTORICAL_STATIC_DIAGNOSTIC'
    return 'REVIEW_USAGE'


def source_risk(source: str) -> list[str]:
    tree = ast.parse(source)
    tokens: set[str] = set()
    if any(isinstance(n, ast.Call) and isinstance(n.func, ast.Attribute)
           and n.func.attr in ('read_text', 'getsource') for n in ast.walk(tree)):
        tokens.add('READS_SOURCE_OR_RESOURCE')
    if any(isinstance(n, ast.Call) and isinstance(n.func, ast.Attribute)
           and n.func.attr == 'splitlines' for n in ast.walk(tree)):
        tokens.add('SPLITLINES_STATIC_CHECK')
    if any(isinstance(n, ast.ImportFrom) and n.module
           and (n.module.startswith('test_') or n.module.startswith('tests.')
                and '.test_' in n.module) for n in ast.walk(tree)):
        tokens.add('CROSS_TEST_IMPORT')
    if any(isinstance(n, ast.Import) and any(x.name.startswith('test_') for x in n.names)
           for n in ast.walk(tree)):
        tokens.add('CROSS_TEST_IMPORT')
    return sorted(tokens)


def audit(root: Path) -> dict:
    root = root.resolve(strict=True)
    if Path(git(root, 'rev-parse', '--show-toplevel')).resolve() != root:
        raise RuntimeError('PROJECT_ROOT_NOT_GIT_ROOT')
    # Mốc nguồn phải là tổ tiên của HEAD để bảo vệ tính truy vết lâu dài.
    parent = subprocess.run(['git', 'merge-base', '--is-ancestor', BASELINE, 'HEAD'],
                            cwd=root, capture_output=True, timeout=30)
    if parent.returncode:
        raise RuntimeError('R84_BASELINE_NOT_ANCESTOR')
    baseline_paths = git(root, 'ls-tree', '-r', '--name-only', BASELINE).splitlines()
    baseline_tests, baseline_scripts = tests_and_scripts(baseline_paths)
    current_paths = git(root, 'ls-files').splitlines()
    # Khi chưa stage, files mới vẫn được tính theo Path (R8.5 chạy trước commit).
    for new in (NEW_AUDIT_TEST, NEW_AUDIT_SCRIPT):
        if (root / new).is_file() and new not in current_paths:
            current_paths.append(new)
    tests, scripts = tests_and_scripts(current_paths)
    errors: list[str] = []
    candidates: list[dict] = []
    if len(baseline_tests) != EXPECT_TEST_FILES or len(baseline_scripts) != EXPECT_SCRIPT_FILES:
        errors.append('BASELINE_COUNTS_CHANGED')
    for p in sorted(set(baseline_tests + baseline_scripts) - set(tests + scripts)):
        errors.append('BASELINE_FILE_DELETED:' + p)
    for p in sorted(set(tests + scripts)):
        f = root / p
        if not f.is_file() or f.is_symlink():
            errors.append('MISSING_OR_SYMLINK:' + p)
    tests_data: list[dict] = []
    code_by_test: dict[str, str] = {}
    for path in tests:
        f = root / path
        if not f.is_file() or f.is_symlink():
            continue
        try:
            source = f.read_text('utf-8-sig')
            names = functions(source)
        except (SyntaxError, UnicodeError, OSError) as exc:
            errors.append('INVALID_TEST:' + path + ':' + repr(exc))
            continue
        if path in baseline_tests:
            try:
                before = functions(git(root, 'show', BASELINE + ':' + path))
            except (RuntimeError, SyntaxError) as exc:
                errors.append('BASELINE_TEST_UNREADABLE:' + path + ':' + repr(exc))
                continue
            if names != before:
                errors.append('BASELINE_TEST_CASES_CHANGED:' + path)
        try:
            risks = source_risk(source)
        except SyntaxError as exc:
            errors.append('RISK_PARSE:' + path + ':' + repr(exc))
            continue
        if 'CROSS_TEST_IMPORT' in risks:
            errors.append('TEST_IMPORT_TEST:' + path)
        code_by_test[path] = source
        tests_data.append({
            'path':path, 'group':path.split('/')[1], 'function_count_static':len(names),
            'test_names':names, 'sha256':hashlib.sha256(f.read_bytes()).hexdigest(),
            'flags':risks, 'decision':'KEEP',
        })
        if path.split('/')[1] not in GROUPS:
            errors.append('TEST_GROUP_UNKNOWN:' + path)
        if 'SPLITLINES_STATIC_CHECK' in risks:
            candidates.append({'kind':'SOURCE_COUPLED_TEST', 'path':path,
                               'reason':'splitlines static assertion; review if refactoring',
                               'decision':'REVIEW_ONLY_NOT_DELETE'})
    scripts_data: list[dict] = []
    # Lấy nơi gọi trong Python/PowerShell/docs của chính dự án; heuristic, không chứng minh dead-code.
    refs: list[tuple[str,str]] = []
    suffixes = ('.py', '.ps1', '.md', '.toml', '.json', '.yaml', '.yml', '.cmake', '.txt')
    for path in current_paths:
        f = root / path
        if not f.is_file() or f.is_symlink() or not path.endswith(suffixes) or f.stat().st_size > 1000000:
            continue
        try:
            refs.append((path, f.read_text('utf-8-sig')))
        except UnicodeError:
            pass
    for path in scripts:
        file = root / path
        if not file.is_file() or file.is_symlink():
            continue
        name = Path(path).name
        module = Path(path).stem
        hits = sorted(p for p,txt in refs if p != path and
                      (path in txt or name in txt or
                       (p.endswith('.py') and ('from ' + module + ' import ') in txt)))
        category = script_category(path)
        scripts_data.append({'path':path, 'category':category,
                             'sha256':hashlib.sha256(file.read_bytes()).hexdigest(),
                             'references_found':hits[:80], 'reference_count':len(hits),
                             'decision':'KEEP_OR_REVIEW'})
        if not hits and category != 'ACTIVE_UNIFIED_GATE':
            candidates.append({'kind':'SCRIPT_NO_STATIC_REFERENCES', 'path':path,
                               'reason':'Không phát hiện lời gọi tĩnh. Có thể được chạy từ _setup hoặc thủ công.',
                               'decision':'REVIEW_ONLY_NOT_DELETE'})
    collisions = defaultdict(list)
    for row in scripts_data + tests_data:
        collisions[row['sha256']].append(row['path'])
    for paths in collisions.values():
        if len(paths) > 1:
            candidates.append({'kind':'IDENTICAL_SHA256_FILES', 'members':sorted(paths),
                               'decision':'REVIEW_ONLY_NOT_DELETE'})
    candidates.extend(duplicate_candidates(code_by_test))
    # Bảo vệ 6 hạng mục nghiệm thu HMI/native của R6 chưa được giải quyết.
    original = (root/'docs/07-nghiem-thu/records/GD1_R6_ACCEPTANCE_STATUS.md').read_text('utf-8')
    for marker in ('R6_AUTOMATED_PASS / R6_OVERALL_PENDING', 'NOT_TESTED', 'PARTIAL_EVIDENCE'):
        if marker not in original:
            errors.append('R6_PENDING_ACCEPTANCE_MARKER_MISSING:' + marker)
    if len(tests) < EXPECT_TEST_FILES + 1 or len(scripts) < EXPECT_SCRIPT_FILES + 1:
        errors.append('R85_ADDITIONS_MISSING')
    if NEW_AUDIT_TEST not in tests or NEW_AUDIT_SCRIPT not in scripts:
        errors.append('R85_REQUIRED_FILE_MISSING')
    return {
        'schema':SCHEMA, 'baseline':BASELINE, 'head':git(root,'rev-parse','HEAD'),
        'observed_at_utc':datetime.now(timezone.utc).isoformat(),
        'status':'PASS' if not errors else 'FAIL',
        'baseline_test_files':len(baseline_tests), 'baseline_script_files':len(baseline_scripts),
        'test_files':len(tests_data), 'script_files':len(scripts_data),
        'test_static_functions':sum(x['function_count_static'] for x in tests_data),
        'groups':dict(sorted(Counter(x['group'] for x in tests_data).items())),
        'tests':tests_data, 'scripts':scripts_data,
        'candidates':candidates, 'errors':errors,
        'decision':{
            'r8_5_static_audit':'PASS' if not errors else 'FAIL',
            'r8_5_full_regression':'NOT_RUN_BY_THIS_AUDIT',
            'gd1_final_freeze':'PENDING_08_06_6',
            'r6_overall':'PENDING',
            'automatic_deletions':0,
            'explanation':'Static calls, SHA and AST do not prove redundant behavior. No historic script/test deleted.'
        },
        'limits':['Chỉ kiểm toán tĩnh; không chạy Qt/VTK hoặc CTest.',
                  'Ứng viên trùng nguồn/không có lời gọi tĩnh không phải bằng chứng an toàn để xóa.',
                  'Những nguồn gọi từ _setup hoặc terminal operator không thể kiểm kê từ Git.',
                  'Không chứng nhận HMI/DPI, native fault, GPU/VRAM hay FPS hiển thị thực.']
    }


def export(data: dict, directory: Path, root: Path) -> None:
    directory = directory.resolve()
    root = root.resolve()
    if directory == root or directory.is_relative_to(root):
        raise RuntimeError('EVIDENCE_MUST_BE_OUTSIDE_REPOSITORY')
    directory.mkdir(parents=True, exist_ok=True)
    (directory/'R85_AUDIT.json').write_text(json.dumps(data,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    for filename,rows,columns in (
        ('R85_TESTS.csv',data['tests'],('path','group','function_count_static','sha256','flags','decision')),
        ('R85_SCRIPTS.csv',data['scripts'],('path','category','reference_count','sha256','references_found','decision')),
        ('R85_CANDIDATES.csv',data['candidates'],('kind','path','members','reason','decision')),
    ):
        with (directory/filename).open('w',newline='',encoding='utf-8-sig') as f:
            writer=csv.DictWriter(f,fieldnames=columns);writer.writeheader()
            for row in rows:
                writer.writerow({key:'; '.join(row.get(key,[])) if isinstance(row.get(key),list)
                                 else row.get(key,'') for key in columns})
    lines=[
        '# R8.5 — Kết quả kiểm toán kiểm thử', '',
        f"- Mốc: `{data['baseline']}`", f"- Trạng thái: **{data['status']}**",
        f"- Test: **{data['baseline_test_files']} baseline → {data['test_files']} hiện tại**",
        f"- Script: **{data['baseline_script_files']} baseline → {data['script_files']} hiện tại**",
        f"- Ứng viên cần rà soát: **{len(data['candidates'])}**; **0 file tự xóa**.",
        '- Chưa xác nhận: HMI/native/DPI/GPU/present. GĐ1 vẫn **PENDING_08_06_6**.',
        '', '## Nhóm test', ''
    ]
    lines.extend(f'- {k}: {v}' for k,v in data['groups'].items())
    lines+=['','## Kiến nghị','',
            'Giữ lại script đối chứng R4/R5 và runner R3.5 nếu chưa có bằng chứng caller âm tính cả bên ngoài Git.',
            'Ứng viên trong CSV chỉ để review; không xóa hoặc tự sửa số ca để đạt PASS.',
            'Chạy Full regression để kết luận phần tự động, rồi làm 08.06.6 cho HMI/native thực.',
            '']
    if data['errors']:
        lines+=['## Lỗi'] + ['- '+x for x in data['errors']]
    (directory/'R85_BAO_CAO.md').write_text('\n'.join(lines)+'\n',encoding='utf-8')


def main() -> int:
    p=argparse.ArgumentParser()
    p.add_argument('--project-root',type=Path,required=True)
    p.add_argument('--out-dir',type=Path,required=True)
    args=p.parse_args()
    try:
        root=args.project_root.resolve(strict=True)
        report=audit(root)
        export(report,args.out_dir,root)
    except (OSError,ValueError,RuntimeError,SyntaxError) as exc:
        print('R85_AUDIT_FAILED:',repr(exc));return 2
    print('R8.5 AUDIT:',report['status'],'tests',report['test_files'],
          'scripts',report['script_files'],'candidates',len(report['candidates']),
          'deleted',report['decision']['automatic_deletions'])
    for issue in report['errors']:
        print('R8.5 ERROR:',issue)
    return 0 if report['status']=='PASS' else 1

if __name__=='__main__':
    sys.exit(main())
