"""DOC-05 non-destructive documentation migration gate.

Pure filesystem/Git checks; no ScanToPath imports, Qt, SDK or data access.
Legacy sources are kept. Historical mirrors rebase only relative Markdown links
while the old source bytes remain available and Git blob identity is checked.
"""
from __future__ import annotations
import argparse
import csv
import hashlib
import json
import os
from pathlib import Path, PurePosixPath
import re
import subprocess
import sys

BASELINE = '8bf5e1e1603a0acf735ffc55f0b3d11ef9d96286'
PLAN = 'docs/standardization/DOC05_MIGRATION_PLAN.json'
ALIASES = (
    'docs/INDEX.md', 'docs/architecture/CURRENT_GD1_ARCHITECTURE.md',
    'docs/development/ENGINEERING_STANDARDS.md',
    'docs/development/R7_DOCUMENTATION_POLICY.md',
    'docs/modules/PROJECT_WORKSPACE.md', 'docs/modules/VIEWER3D.md',
    'docs/roadmap/ROADMAP_V1_ARCHIVED.md',
)
V2 = (
    'docs/99-lich-su/README.md',
    'docs/99-lich-su/STANDARDIZATION/README.md',
    'docs/standardization/DOC05_TRUY_VET_VA_BAN_GIAO.md',
    'docs/README.md',
)
# Only inline Markdown links; code fences are never rewritten. Original source
# bytes and SHA are retained in the legacy location and the migration plan.
LINK = re.compile(r'(!?\[[^\]\n]+\]\()([^\)\n]+)(\))')


def git(root: Path, *args: str) -> str:
    p = subprocess.run(['git', *args], cwd=root, capture_output=True,
                       text=True, encoding='utf-8', errors='replace', timeout=20)
    if p.returncode:
        raise RuntimeError('GIT_FAILED:' + ' '.join(args) + ':' + p.stderr[:200])
    return p.stdout.strip()


def safe(root: Path, rel: str) -> Path:
    if (not rel.startswith('docs/') or '\\' in rel or
        any(x in ('', '.', '..') for x in PurePosixPath(rel).parts) or
        not re.fullmatch(r'[A-Za-z0-9_./-]+', rel)):
        raise ValueError('UNSAFE_DOC_PATH:' + rel)
    path = root / rel
    resolved = path.resolve(strict=False)
    if not resolved.is_relative_to(root.resolve(strict=True)):
        raise ValueError('PATH_ESCAPE:' + rel)
    # Reject symlink/junction ancestors for both source and destination.
    step = root
    for part in PurePosixPath(rel).parts:
        step = step / part
        if step.is_symlink():
            raise ValueError('SYMLINK_REJECTED:' + rel)
    return path


def transform(root: Path, source: str, target: str, data: bytes) -> bytes:
    if not source.endswith('.md'):
        return data
    map_path=root/'docs/standardization/DOC02_BAN_DO_65.csv'
    redirect={}
    if map_path.is_file():
        with map_path.open(encoding='utf-8-sig',newline='') as stream:
            redirect={row['old_path']:row['primary_target'] for row in csv.DictReader(stream)
                      if row['old_path'].startswith('docs/') and row['old_path'] != row['primary_target']}
    bom=b'\xef\xbb\xbf'
    body=data.decode('utf-8-sig')
    result=[]
    fence=False
    for line in body.splitlines(keepends=True):
        if line.lstrip().startswith(('```','~~~')):
            fence=not fence
            result.append(line)
            continue
        if fence:
            result.append(line)
            continue
        def change(match):
            raw=match.group(2)
            if (raw.startswith(('http:','https:','mailto:','#','/','\\','<')) or
                    re.match(r'^[A-Za-z]:',raw)):
                return match.group(0)
            head=raw.split(' "',1)[0].split('#',1)[0].split('?',1)[0]
            if not head or '\\' in head:
                return match.group(0)
            parts=source.split('/')[:-1]
            for part in head.split('/'):
                if part in ('','.'):continue
                if part=='..':
                    if not parts:return match.group(0)
                    parts.pop()
                else:parts.append(part)
            relative='/'.join(parts)
            new_target=redirect.get(relative,relative)
            new_path=Path(os.path.relpath(new_target,Path(target).parent)).as_posix()
            if new_path=='.':new_path=Path(new_target).name
            return match.group(1)+new_path+raw[len(head):]+match.group(3)
        result.append(LINK.sub(change,line))
    return (bom if data.startswith(bom) else b'')+''.join(result).encode('utf-8')


def load_plan(root: Path) -> dict:
    plan = json.loads(safe(root, PLAN).read_text('utf-8'))
    assert plan['base_commit'] == BASELINE
    mirrors = plan['mirrors']
    if len(mirrors) != 28 or len({x['id'] for x in mirrors}) != 28:
        raise ValueError('DOC05_MIRROR_COUNT_OR_ID')
    if len({x['source'] for x in mirrors}) != 28 or len({x['target'] for x in mirrors}) != 28:
        raise ValueError('DOC05_SOURCE_OR_TARGET_COLLISION')
    for item in mirrors:
        if not re.fullmatch(r'DOC-\d{3}', item['id']):
            raise ValueError('DOC05_BAD_MAP_ID')
        safe(root, item['source']); safe(root, item['target'])
    return plan


def link_errors(root: Path, rel: str) -> list[str]:
    errors=[]
    doc=safe(root,rel)
    for match in LINK.finditer(doc.read_text('utf-8-sig')):
        target=match.group(2).split(' "',1)[0].split('#',1)[0].split('?',1)[0]
        if not target or target.startswith(('http:', 'https:', 'mailto:', '/')):
            continue
        if not (doc.parent/target).resolve().is_file():
            errors.append('BROKEN_NEW_INDEX_LINK:'+rel+':'+target)
    return errors


def verify(root: Path) -> dict:
    root=root.resolve(strict=True)
    errors=[]
    plan=load_plan(root)
    parent=subprocess.run(['git','merge-base','--is-ancestor',BASELINE,'HEAD'],
                          cwd=root,capture_output=True,timeout=30)
    if parent.returncode:errors.append('DOC05_SOURCE_BASELINE_NOT_ANCESTOR')
    with (root/'docs/standardization/DOC02_BAN_DO_65.csv').open(
            encoding='utf-8-sig', newline='') as stream:
        source_map={r['id']:r for r in csv.DictReader(stream)}
    for x in plan['mirrors']:
        mapped=source_map.get(x['id'])
        if not mapped or mapped['old_path']!=x['source'] or mapped['primary_target']!=x['target']:
            errors.append('DOC05_MAP_MISMATCH:'+x['id'])
        old=safe(root,x['source']);new=safe(root,x['target'])
        if old.exists():errors.append('DOC05_DUPLICATE_SOURCE_STILL_PRESENT:'+x['id'])
        if not new.is_file():
            errors.append('DOC05_MIRROR_MISSING:'+x['id']);continue
        blob=git(root,'rev-parse',BASELINE+':'+x['source'])
        if blob!=x['source_git_blob']:
            errors.append('DOC05_SOURCE_BLOB_CHANGED:'+x['id']);continue
        historical=subprocess.run(['git','show',BASELINE+':'+x['source']],cwd=root,
                                  capture_output=True,timeout=30)
        if historical.returncode:
            errors.append('DOC05_SOURCE_NOT_RETRIEVABLE:'+x['id']);continue
        expected=transform(root,x['source'],x['target'],historical.stdout)
        check=subprocess.run(['git','hash-object','--path='+x['target'],'--stdin'],
                             input=expected,cwd=root,capture_output=True,timeout=30)
        clean=subprocess.run(['git','hash-object','--path='+x['target'],'--',x['target']],
                             cwd=root,capture_output=True,timeout=30)
        if check.returncode or clean.returncode or check.stdout!=clean.stdout:
            errors.append('DOC05_MIRROR_CONTENT_CHANGED:'+x['id'])
    for rel in ALIASES:
        if safe(root,rel).exists():errors.append('DOC05_DUPLICATE_ALIAS_STILL_PRESENT:'+rel)
    for rel in V2:
        if not safe(root,rel).is_file():errors.append('DOC05_INDEX_MISSING:'+rel)
        else:errors.extend(link_errors(root,rel))
    portal=safe(root,'docs/README.md').read_text('utf-8')
    for mark in ('DOC-03B','DOC-03C','DOC-04','DOC-05',
                 '7a0df7c5b596ff8750bf91f47310067c53a8b204','99-lich-su/README.md'):
        if mark not in portal:errors.append('DOC05_PORTAL_REGRESSION:'+mark)
    state=safe(root,'docs/05-quan-ly/TRANG_THAI_DU_AN.md').read_text('utf-8')
    accept=safe(root,'docs/07-nghiem-thu/GD1_ACCEPTANCE.md').read_text('utf-8')
    if 'GD1_OVERALL_PENDING' not in state or 'NOT_TESTED' not in accept:
        errors.append('DOC05_HMI_STATUS_CHANGED')
    return {'schema':'scantopath-doc05-migration-v2', 'source_commit':BASELINE,
            'status':'PASS' if not errors else 'FAIL','mirrors_checked':len(plan['mirrors']),
            'aliases_preserved':0,'aliases_retired':len(ALIASES),'windows_full':'NOT_RUN_BY_GATE',
            'hmi_08_06_6':'PENDING_MANUAL','errors':errors}


def main() -> int:
    p=argparse.ArgumentParser();p.add_argument('--project-root',type=Path,required=True)
    p.add_argument('--out-dir',type=Path,required=True); a=p.parse_args()
    try:
        root=a.project_root.resolve(strict=True)
        out=a.out_dir.resolve()
        if out==root or out.is_relative_to(root):
            raise ValueError('EVIDENCE_MUST_BE_OUTSIDE_REPO')
        result=verify(root)
        out.mkdir(parents=True,exist_ok=True)
        (out/'DOC05_MIGRATION_GATE.json').write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
        print('DOC05 MIGRATION',result['status'],'mirrors',result['mirrors_checked'],
              'aliases',result['aliases_preserved'],'errors',len(result['errors']))
        for error in result['errors']: print('DOC05 ERROR:',error)
        return 0 if not result['errors'] else 1
    except Exception as exc:
        print('DOC05 GATE FAILED:',repr(exc),file=sys.stderr)
        return 2

if __name__=='__main__': raise SystemExit(main())
