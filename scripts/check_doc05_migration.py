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
    bom = b'\xef\xbb\xbf'
    original = data.decode('utf-8-sig')
    source_parent = (root / source).parent
    target_parent = (root / target).parent
    in_fence = False
    result = []
    for line in original.splitlines(keepends=True):
        stripped = line.lstrip()
        if stripped.startswith(('```', '~~~')):
            in_fence = not in_fence
        if in_fence:
            result.append(line)
            continue
        def rebase(match: re.Match[str]) -> str:
            ref = match.group(2)
            if (ref.startswith(('http:', 'https:', 'mailto:', '#', '/', '\\', '<')) or
                re.match(r'^[A-Za-z]:', ref)):
                return match.group(0)
            plain = ref.split(' "', 1)[0]
            head = plain.split('#', 1)[0].split('?', 1)[0]
            if not head or '\\' in head:
                return match.group(0)
            resolved = (source_parent / head).resolve(strict=False)
            if not resolved.is_relative_to(root.resolve()):
                return match.group(0)
            # Preserve anchor/query; point back to the source's original target.
            rebased = Path(os.path.relpath(resolved, target_parent)).as_posix()
            return match.group(1) + rebased + plain[len(head):] + ref[len(plain):] + match.group(3)
        result.append(LINK.sub(rebase, line))
    encoded = ''.join(result).encode('utf-8')
    return (bom if data.startswith(bom) else b'') + encoded


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
    if git(root,'rev-parse','HEAD') != BASELINE:
        errors.append('DOC05_BASELINE_HEAD_CHANGED')
    # Validate every migration against DOC-02, not just a self-authored plan.
    with (root/'docs/standardization/DOC02_BAN_DO_65.csv').open(
            encoding='utf-8-sig', newline='') as stream:
        source_map = {r['id']:r for r in csv.DictReader(stream)}
    ids={}
    for x in plan['mirrors']:
        defined=source_map.get(x['id'])
        if not defined or defined['old_path']!=x['source'] or defined['primary_target']!=x['target']:
            errors.append('DOC02_MAPPING_DIVERGENCE:'+x['id'])

        old=safe(root,x['source']); new=safe(root,x['target'])
        ids[x['id']]=x['target']
        if not old.is_file() or not new.is_file():
            errors.append('DOC05_MIRROR_MISSING:'+x['id'])
            continue
        blob=git(root,'rev-parse',BASELINE+':'+x['source'])
        if blob!=x['source_git_blob']:
            errors.append('DOC05_SOURCE_BLOB_CHANGED:'+x['id'])
        if new.read_bytes()!=transform(root,x['source'],x['target'],old.read_bytes()):
            errors.append('DOC05_MIRROR_CONTENT_CHANGED:'+x['id'])
    for label in ('DOC-025','DOC-045','DOC-053'):
        if label not in source_map:
            errors.append('DOC02_EXCEPTION_SOURCE_MISSING:'+label)
    if (source_map['DOC-025']['primary_target']!='docs/99-lich-su/README.md' or
        source_map['DOC-045']['primary_target']!='docs/99-lich-su/README.md' or
        source_map['DOC-053']['primary_target']!='docs/99-lich-su/ARCHIVE/ROADMAP_CU/ROADMAP_V1_ARCHIVED.md'):
        errors.append('DOC02_MERGE_ALIAS_EXCEPTION_CHANGED')
    for rel in ALIASES:
        if not safe(root,rel).is_file():
            errors.append('DOC05_LEGACY_ALIAS_MISSING:'+rel)
    for rel in V2:
        if not safe(root,rel).is_file():
            errors.append('DOC05_INDEX_MISSING:'+rel)
        else:
            errors.extend(link_errors(root,rel))
    portal=safe(root,'docs/README.md').read_text('utf-8')
    for mark in ('DOC-03B','DOC-03C','DOC-04','DOC-05',
                 '7a0df7c5b596ff8750bf91f47310067c53a8b204',
                 '99-lich-su/README.md'):
        if mark not in portal:
            errors.append('DOC05_PORTAL_REGRESSION:'+mark)
    # Preserve pending decisions. No HMI pass can be inferred from docs migration.
    status=safe(root,'docs/05-quan-ly/TRANG_THAI_DU_AN.md').read_text('utf-8')
    acceptance=safe(root,'docs/07-nghiem-thu/GD1_ACCEPTANCE.md').read_text('utf-8')
    if 'GD1_OVERALL_PENDING' not in status or 'NOT_TESTED' not in acceptance:
        errors.append('DOC05_HMI_STATUS_CHANGED')
    return {'schema':'scantopath-doc05-migration-v1', 'source_commit':BASELINE,
            'status':'PASS' if not errors else 'FAIL','mirrors_checked':len(plan['mirrors']),
            'aliases_preserved':len(ALIASES),'windows_full':'NOT_RUN_BY_GATE',
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
