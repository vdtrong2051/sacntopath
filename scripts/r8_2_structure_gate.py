"""R8.2 — kiểm tra di chuyển test theo chức năng và bất biến phạm vi. Chỉ đọc Git/AST."""
from __future__ import annotations

import argparse
import ast
import csv
import json
from pathlib import Path
import subprocess
import sys

BASE = '997536b8f14b95e64642be1028f8318c51efecc5'
MAP = 'docs/99-lich-su/STANDARDIZATION/R8_2_BAN_DO_TEST.csv'


def git(root:Path,*args:str)->str:
    p=subprocess.run(['git',*args],cwd=root,stdout=subprocess.PIPE,stderr=subprocess.PIPE)
    if p.returncode:raise RuntimeError('GIT_FAILED:'+' '.join(args)+':'+p.stderr.decode(errors='replace')[:250])
    return p.stdout.decode('utf-8-sig')


def test_names(code:str)->list[str]:
    tree=ast.parse(code)
    return sorted(n.name for n in ast.walk(tree) if isinstance(n,(ast.FunctionDef,ast.AsyncFunctionDef)) and n.name.startswith('test_'))


def by_name(code:str,name:str)->ast.FunctionDef:
    tree=ast.parse(code)
    return next(x for x in tree.body if isinstance(x,ast.FunctionDef) and x.name==name)


def verify(root:Path)->dict:
    root=root.resolve(strict=True)
    errors=[]
    with (root/MAP).open('r',encoding='utf-8-sig',newline='') as f:
        rows=list(csv.DictReader(f))
    if len(rows)!=76:errors.append('MAP_EXPECTS_76_TESTS')
    olds=[r['duong_dan_cu'] for r in rows];news=[r['duong_dan_moi'] for r in rows]
    if len(set(olds))!=76 or len(set(news))!=76:errors.append('DUPLICATE_TEST_PATH')
    if set(news)&set(olds):errors.append('TEST_NOT_MOVED')
    if set(olds)!=set(x for x in git(root,'ls-tree','-r','--name-only',BASE).splitlines()
                      if x.startswith('tests/') and x.endswith('.py')):
        errors.append('MAPPING_NOT_COMPLETE_AT_BASELINE')
    cross_imports=[];test_count=0;changed=[]
    for old,new in zip(olds,news):
        path=root/new
        if (root/old).exists():errors.append('OLD_PATH_STILL_EXISTS:'+old)
        if not path.is_file() or path.is_symlink():
            errors.append('MISSING_NEW_TEST:'+new);continue
        try:
            current=path.read_text(encoding='utf-8-sig')
            original=git(root,'show',f'{BASE}:{old}')
            a=test_names(original);b=test_names(current)
            if a!=b:errors.append('TEST_FUNCTION_NAMES_CHANGED:'+old)
            test_count+=len(b)
            for node in ast.walk(ast.parse(current)):
                if isinstance(node,ast.ImportFrom) and node.module and node.module.startswith('test_'):
                    cross_imports.append((new,node.module))
                if isinstance(node,ast.Import):
                    cross_imports.extend((new,x.name) for x in node.names if x.name.startswith('test_'))
            if 'Path(__file__).resolve().parents[1]' in current:
                errors.append('STALE_REPO_ROOT_REFERENCE:'+new)
        except (SyntaxError, UnicodeError,RuntimeError) as e:
            errors.append('INVALID_TEST:'+new+':'+repr(e))
    if cross_imports:errors.append('CROSS_TEST_IMPORTS:'+str(cross_imports))
    # Kiểm tra chuyển nguyên văn phần thân hai fixture đã được tách.
    references={
        'tests/test_gd1_07_2_numbered_storage.py':('raw','tests/support/raw_fixture.py'),
        'tests/test_gd1_07_8_integrated.py':('_seed_v1','tests/support/project_seed.py'),
        'tests/test_gd1_07_8_integrated.py#2':('_seed_numbered','tests/support/project_seed.py'),
    }
    for f,(name,now) in references.items():
        origin=f.split('#')[0]
        try:
            original=git(root,'show',f'{BASE}:{origin}')
            actual=(root/now).read_text(encoding='utf-8')
            if ast.dump(by_name(original,name),include_attributes=False)!=ast.dump(by_name(actual,name),include_attributes=False):
                errors.append('FIXTURE_LOGIC_CHANGED:'+name)
        except Exception as exc:errors.append('FIXTURE_CHECK_FAILED:'+name+':'+repr(exc))
    for pkg in ['tests','tests/support','tests/contracts/quality']:
        if not (root/pkg/'__init__.py').is_file():errors.append('NOT_A_PYTHON_PACKAGE:'+pkg)
    script=(root/'scripts/verify_gd1_r3_5.ps1').read_text('utf-8-sig')
    for old,new in zip(olds,news):
        if old in script:errors.append('R35_OLD_SCRIPT_PATH:'+old)
    # Tài liệu/test cũ không được thay đổi nghiệm thu R6 hoặc chính sách SKIP ở R8.2.
    for required in ['R6_AUTOMATED_PASS / R6_OVERALL_PENDING']:
        if required not in (root/'docs/07-nghiem-thu/records/GD1_R6_ACCEPTANCE_STATUS.md').read_text('utf-8'):
            errors.append('R6_ACCEPTANCE_CLAIM_CHANGED')
    return {'schema':'scantopath-r8-2-structure-gate-v1','status':'PASS' if not errors else 'FAIL',
            'baseline':BASE,'mapped_tests':len(rows),'test_functions_static':test_count,
            'cross_imports':cross_imports,'errors':errors,
            'limitations':'AST static check only; pytest/CTest/HMI still require separate acceptance.'}


def main()->int:
    ap=argparse.ArgumentParser()
    ap.add_argument('--project-root',type=Path,required=True)
    ap.add_argument('--out-dir',type=Path,required=True)
    a=ap.parse_args()
    root=a.project_root.resolve(strict=True)
    out=a.out_dir.resolve()
    if out==root or out.is_relative_to(root):raise RuntimeError('EVIDENCE_MUST_BE_OUTSIDE_REPO')
    r=verify(root)
    out.mkdir(parents=True,exist_ok=True)
    (out/'R82_STRUCTURE_GATE.json').write_text(json.dumps(r,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    print('R8.2 STRUCTURE',r['status'],'mapped',r['mapped_tests'],'errors',len(r['errors']))
    for error in r['errors']:print('R8.2 ERROR',error)
    return 0 if r['status']=='PASS' else 1

if __name__=='__main__':
    try:sys.exit(main())
    except (OSError,ValueError,RuntimeError,SyntaxError) as exc:
        print('R8.2 GATE FAILED:',repr(exc));sys.exit(1)
