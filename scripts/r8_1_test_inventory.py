"""R8.1 — Kiểm kê tĩnh test/script, không import mã dự án hoặc mở tài nguyên native.

Đọc Git-index, AST và CSV danh mục; chỉ ghi kết quả vào đường dẫn --out-dir
bên ngoài repository. Không chạy pytest, Qt, VTK, RAW hoặc SQLite.
"""
from __future__ import annotations

import argparse
import ast
import csv
from collections import Counter, defaultdict
from datetime import datetime, timezone
import hashlib
import io
import json
from pathlib import Path
import re
import subprocess
import sys

BASELINE = 'f59d3f8518c52879c9b5b7fe37539ffd9061827a'
CATALOG = 'docs/standardization/R8_1_MA_TRAN_97_TEP.csv'
HEADERS = ('duong_dan', 'loai', 'nhom_chuc_nang', 'nhom_kiem_thu_de_xuat',
           'hop_dong_duoc_bao_ve_hoac_muc_dich', 'quyet_dinh_so_bo',
           'ly_do_can_xem_xet', 'test_chuan_de_xuat', 'do_tin_cay')
VIET = {'KEEP': 'GIU', 'REVIEW': 'CAN_DOI_CHIEU'}


def git(root: Path, *args: str) -> str:
    result = subprocess.run(['git', *args], cwd=root, stdout=subprocess.PIPE,
                            stderr=subprocess.PIPE, check=False)
    if result.returncode:
        raise RuntimeError(f'GIT_FAILED:{" ".join(args)}:{result.stderr.decode(errors="replace")[:300]}')
    return result.stdout.decode('utf-8-sig', errors='replace').strip()


def tracked_baseline(root: Path) -> tuple[list[str], list[str]]:
    # HEAD is pinned, so newly created R8.1 test/inventory tools cannot change this list.
    paths = git(root, 'ls-tree', '-r', '--name-only', BASELINE).splitlines()
    tests = sorted(p for p in paths if p.startswith('tests/') and p.endswith('.py'))
    scripts = sorted(p for p in paths if p.startswith('scripts/') and p.endswith(('.py', '.ps1')))
    return tests, scripts


def load_catalog(root: Path) -> list[dict[str, str]]:
    with (root / CATALOG).open('r', encoding='utf-8-sig', newline='') as f:
        reader = csv.DictReader(f)
        if tuple(reader.fieldnames or ()) != HEADERS:
            raise ValueError('R8_1_CATALOG_BAD_COLUMNS')
        return list(reader)


def _source_imports(tree: ast.AST) -> tuple[list[str], list[str]]:
    modules: set[str] = set()
    test_helpers: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            names = [a.name for a in node.names]
        elif isinstance(node, ast.ImportFrom) and node.module:
            names = [node.module]
        else:
            continue
        for name in names:
            if name.startswith('scantopath'):
                modules.add(name)
            if name.startswith('test_'):
                test_helpers.add(name)
    return sorted(modules), sorted(test_helpers)


def _source_paths(root: Path, modules: list[str]) -> list[str]:
    result = set()
    for mod in modules:
        base = Path('src') / Path(mod.replace('.', '/'))
        for suffix in ('.py', '/__init__.py'):
            p = Path(str(base) + suffix)
            if (root / p).is_file():
                result.add(p.as_posix())
    return sorted(result)


def _source_risk(tree: ast.AST, data: str) -> list[str]:
    names: set[str] = set()
    # Candidates only, not a verdict that a test is invalid.
    if re.search(r'\b(?:read_text|read_bytes|getsource|ast\.parse)\s*\(', data):
        names.add('CO_DOC_SOURCE')
    if re.search(r'assert\s+.+\bin\s+(?:source|bootstrap|shell|main|script|p|content|s)\b', data):
        names.add('CO_KIEM_TRA_CHUOI')
    if re.search(r'len\(.+splitlines\(\)\)\s*[<>]', data):
        names.add('CO_GIOI_HAN_SO_DONG')
    if re.search(r'\b(?:subprocess\.|Popen\(|check_output\()', data):
        names.add('CO_SUBPROCESS')
    if re.search(r'\b(?:QApplication|QWidget|QTest|PySide6)\b', data):
        names.add('CO_QT')
    if 'pytest.importorskip' in data:
        names.add('PHU_THUOC_MOI_TRUONG')
    if '@pytest.mark.skip' in data or 'pytest.skip(' in data:
        names.add('CO_DIEU_KIEN_SKIP')
    if 'shared_memory' in data or 'vtkmodules' in data:
        names.add('CO_NATIVE_HOAC_SHARED_MEMORY')
    return sorted(names)


def _call_names(tree: ast.AST) -> list[str]:
    return sorted({n.name for n in ast.walk(tree)
                   if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef))
                   and n.name.startswith('test_')})


def scan(root: Path) -> dict:
    root = root.resolve(strict=True)
    if Path(git(root, 'rev-parse', '--show-toplevel')).resolve() != root:
        raise RuntimeError('ROOT_NOT_REPO_ROOT')
    head = git(root, 'rev-parse', 'HEAD')
    if git(root, 'rev-parse', BASELINE + '^{commit}') != BASELINE:
        raise RuntimeError('BASELINE_MISSING')
    if head != BASELINE:
        check = subprocess.run(['git', 'merge-base', '--is-ancestor', BASELINE, 'HEAD'], cwd=root, check=False)
        if check.returncode != 0:
            raise RuntimeError(f'BASELINE_NOT_ANCESTOR:baseline={BASELINE}:head={head}')
    tests, scripts = tracked_baseline(root)
    registered = load_catalog(root)
    registered_paths = [row['duong_dan'] for row in registered]
    errors: list[str] = []
    if len(tests) != 75 or len(scripts) != 22:
        errors.append(f'SOURCE_COUNTS_CHANGED:tests={len(tests)},scripts={len(scripts)}')
    if len(registered_paths) != len(set(registered_paths)):
        errors.append('DUPLICATE_CATALOG_PATHS')
    if set(registered_paths) != set(tests + scripts):
        errors.append(f'CATALOG_PATH_MISMATCH:missing={sorted(set(tests+scripts)-set(registered_paths))}:extra={sorted(set(registered_paths)-set(tests+scripts))}')
    relocation = {}
    mapping_file = root / 'docs/standardization/R8_2_BAN_DO_TEST.csv'
    if mapping_file.is_file():
        with mapping_file.open(encoding='utf-8-sig', newline='') as f:
            relocation = {r['duong_dan_cu']: r['duong_dan_moi'] for r in csv.DictReader(f)}
    results = []
    functions: dict[str, list[str]] = defaultdict(list)
    imported_test_file: dict[str, list[str]] = defaultdict(list)
    for row in registered:
        p = row['duong_dan']
        current_path = relocation.get(p, p)
        path = root / current_path
        if not path.is_file() or path.is_symlink():
            errors.append(f'FILE_MISSING_OR_SYMLINK:{p}')
            continue
        raw = path.read_bytes()
        try:
            content = raw.decode('utf-8-sig')
        except UnicodeDecodeError:
            errors.append(f'INVALID_UTF8:{p}')
            continue
        status = 'DA_QUET'
        funcs=[]; mods=[]; helper_imports=[]; src=[]; risks=[]
        if p.endswith('.py'):
            try:
                tree = ast.parse(content, filename=p)
            except SyntaxError as exc:
                errors.append(f'SYNTAX_ERROR:{p}:{exc.lineno}')
                continue
            funcs = _call_names(tree)
            mods, helper_imports = _source_imports(tree)
            src = _source_paths(root, mods)
            risks = _source_risk(tree, content)
        if helper_imports:
            for h in helper_imports:
                imported_test_file[h].append(p)
        if p.startswith('tests/'):
            for fn in funcs:
                functions[fn].append(p)
            if not funcs:
                risks.append('KHONG_CO_TEST_FUNCTION_TRUC_TIEP')
        results.append({
            **row,
            'duong_dan_hien_tai': current_path,
            'git_blob_baseline': git(root, 'rev-parse', f'{BASELINE}:{p}'),
            'sha256_worktree': hashlib.sha256(raw).hexdigest(),
            'bytes': len(raw), 'test_functions_static': len(funcs),
            'test_case_names': funcs,
            'imported_scantopath_modules': mods,
            'resolved_source_files': src,
            'imported_test_modules': helper_imports,
            'risk_flags': sorted(set(risks)), 'scan_status': status,
        })
    findings = []
    for fn, members in functions.items():
        if len(members) > 1:
            findings.append({'loai':'TEN_TEST_TRUNG','chi_tiet':fn,'tap_tin':sorted(members),
                             'ket_luan':'CHUA_CHUNG_MINH_TRUNG_HANH_VI'})
    for helper, members in imported_test_file.items():
        findings.append({'loai':'TEST_IMPORT_TEST','chi_tiet':helper,'tap_tin':sorted(members),
                         'ket_luan':'CAN_CHUYEN_FIXTURE_SANG_SUPPORT_R8_2'})
    for row in results:
        if any(n in row['risk_flags'] for n in ('CO_KIEM_TRA_CHUOI','CO_GIOI_HAN_SO_DONG')):
            findings.append({'loai':'KIEM_TRA_PHU_THUOC_SOURCE','chi_tiet':','.join(row['risk_flags']),
                             'tap_tin':[row['duong_dan']], 'ket_luan':'CAN_DOI_CHIEU_CONTRACT_R8_3'})
    group_counts = dict(sorted(Counter(r['nhom_chuc_nang'] for r in results).items()))
    levels = dict(sorted(Counter(r['nhom_kiem_thu_de_xuat'] for r in results).items()))
    return {'schema':'scantopath-r8-1-test-inventory-v1','baseline_sha':BASELINE,'current_sha':head,
            'scanned_utc':datetime.now(timezone.utc).isoformat(),
            'tong_tap':len(results),'so_test':len(tests),'so_script':len(scripts),
            'so_test_function_tinh':sum(r['test_functions_static'] for r in results),
            'note_test_cases':'Số hàm AST KHÔNG phải số test case pytest sau parametrization/fixtures.',
            'nhom':group_counts,'loai':levels,'chi_tiet':results,'phat_hien':findings,
            'errors':errors,'status':'PASS' if not errors and len(results)==97 else 'FAIL',
            'gioi_han':['Đây là kiểm kê tĩnh; không chạy Qt/native hoặc đo hiệu năng.',
                        'Phát hiện chồng lặp theo dấu hiệu, không kết luận test trùng toàn bộ.',
                        'Cần pytest --collect-only và review thủ công để xác nhận số nodeid/hợp đồng.']}


def export(report: dict, out_dir: Path, root: Path) -> None:
    out_dir = out_dir.resolve()
    if out_dir == root or out_dir.is_relative_to(root):
        raise ValueError('EVIDENCE_MUST_BE_OUTSIDE_REPOSITORY')
    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / 'R8_1_DU_LIEU_QUET.json').write_text(
        json.dumps(report, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    columns=['duong_dan','loai','nhom_chuc_nang','nhom_kiem_thu_de_xuat','quyet_dinh_so_bo',
             'test_functions_static','resolved_source_files','imported_test_modules','risk_flags',
             'git_blob_baseline','sha256_worktree','bytes']
    with (out_dir / 'R8_1_MA_TRAN_BO_SUNG.csv').open('w', encoding='utf-8-sig',newline='') as f:
        writer=csv.DictWriter(f,fieldnames=columns);writer.writeheader()
        for row in report['chi_tiet']:
            writer.writerow({k:'; '.join(row[k]) if isinstance(row[k],list) else row[k] for k in columns})
    s=['# R8.1 — Báo cáo kiểm kê kiểm thử trên repository cục bộ','',
       f"**Baseline:** `{report['baseline_sha']}`",f"**Trạng thái:** {report['status']}",
       f"**Số lượng:** {report['so_test']} tệp test; {report['so_script']} script; {report['tong_tap']} mục.",
       f"**Số hàm test tĩnh:** {report['so_test_function_tinh']} (không thay cho số nodeid pytest).",'',
       '## Phân loại', '']
    for name, count in report['nhom'].items(): s.append(f'- {name}: {count}')
    s+=['','## Vấn đề cần xem xét']
    for e in report['phat_hien']:
        s.append(f"- **{e['loai']}** — {', '.join(e['tap_tin'])}: {e['chi_tiet']}.")
    s+=['','## Giới hạn','']
    s.extend('- '+x for x in report['gioi_han'])
    if report['errors']:
        s+=['','## Lỗi']+['- '+x for x in report['errors']]
    (out_dir / 'R8_1_BAO_CAO_QUET.md').write_text('\n'.join(s)+'\n',encoding='utf-8')


def main(argv: list[str] | None=None) -> int:
    parser=argparse.ArgumentParser(description='R8.1: chỉ đọc/kiểm kê tests và scripts')
    parser.add_argument('--project-root',required=True,type=Path)
    parser.add_argument('--out-dir',required=True,type=Path)
    args=parser.parse_args(argv)
    try:
        root=args.project_root.resolve(strict=True)
        report=scan(root)
        export(report,args.out_dir,root)
    except (OSError,RuntimeError,ValueError) as exc:
        print('R8_1_SCAN_FAILED',str(exc));return 1
    print('R8_1_SCAN',report['status'],'tests',report['so_test'],
          'scripts',report['so_script'],'items',report['tong_tap'],
          'candidate_findings',len(report['phat_hien']), 'evidence',args.out_dir)
    for msg in report['errors']:print('R8_1_ERROR',msg)
    return 0 if report['status']=='PASS' else 1

if __name__=='__main__':
    raise SystemExit(main())
