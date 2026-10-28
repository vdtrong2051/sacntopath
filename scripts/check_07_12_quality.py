"""07.12 structural regression gate; evidence, not a proof of all SOLID properties."""
from __future__ import annotations
import argparse
import ast
import json
from pathlib import Path

GATE = {
    'metadata/store.py': ('MetadataStore', 170),
    'storage/numbered.py': ('NumberedStorageRegistry', 145),
    'modules/project_workspace/presentation/controller.py': ('ProjectWorkspaceController', 140),
}
REQUIRED = (
    'metadata/schema.py', 'metadata/repos/projects.py', 'metadata/repos/captures.py',
    'metadata/repos/processing.py', 'metadata/repos/audit.py',
    'storage/numbered_contracts.py','storage/numbered_ops/codes.py',
    'storage/numbered_ops/resolve.py','storage/numbered_ops/capture.py',
    'storage/numbered_ops/migration.py','storage/numbered_ops/catalog.py',
    'modules/project_workspace/presentation/workflows/reading.py',
    'modules/project_workspace/presentation/workflows/writing.py',
    'modules/project_workspace/presentation/workflows/capture.py',
)

def audit(root: Path) -> dict:
    source=root/'src'/'scantopath'
    errors=[]; classes={}
    for rel,(name,limit) in GATE.items():
        path=source/rel
        tree=ast.parse(path.read_text(encoding='utf-8'))
        matches=[n for n in tree.body if isinstance(n,ast.ClassDef) and n.name==name]
        if len(matches)!=1:
            errors.append(f'{rel}: expected one {name}')
            continue
        cls=matches[0]
        methods=[n for n in cls.body if isinstance(n,(ast.FunctionDef,ast.AsyncFunctionDef))]
        classes[name]={'lines':cls.end_lineno-cls.lineno+1,'methods':len(methods),'limit':limit}
        if classes[name]['lines']>limit:errors.append(f'{name} exceeds SRP façade budget {limit}')
    for rel in REQUIRED:
        if not (source/rel).is_file():errors.append(f'missing responsibility module {rel}')
    from check_architecture_boundaries import scan
    for filename,line,target in scan(root):
        errors.append(f'{filename}:{line}: forbidden dependency {target}')
    for rel in REQUIRED:
        path=source/rel
        if not path.is_file():continue
        tree=ast.parse(path.read_text(encoding='utf-8'))
        for node in ast.walk(tree):
            targets=[]
            if isinstance(node,ast.Import):targets=[n.name for n in node.names]
            if isinstance(node,ast.ImportFrom) and node.module and node.level==0:targets=[node.module]
            if any(target.startswith(('PySide6','scantopath.ui')) for target in targets) and ('metadata/' in rel or 'storage/' in rel):
                errors.append(f'{rel}:{node.lineno}: persistence imports UI')
            if any(target.startswith(('sqlite3','sqlalchemy','scantopath.metadata','scantopath.storage')) for target in targets) and '/presentation/workflows/' in '/'+rel:
                errors.append(f'{rel}:{node.lineno}: Qt workflow imports persistence')
    # Surface ownership: metadata/numbered façades must not embed each use-case SQL.
    facade=(source/'metadata/store.py').read_text()
    for sql in ('INSERT INTO captures','INSERT INTO projects','UPDATE scan_sessions'):
        if sql in facade:errors.append(f'MetadataStore contains inlined SQL: {sql}')
    registry=(source/'storage/numbered.py').read_text()
    for sql in ('BEGIN IMMEDIATE','INSERT INTO storage_captures','INSERT INTO storage_counters'):
        if sql in registry:errors.append(f'NumberedStorageRegistry owns storage transaction: {sql}')
    return {'version':'07.12','facades':classes,'required_files':list(REQUIRED),
            'errors':errors,'limitation':'Static code properties only; not formal SOLID proof or concurrency model checking.'}

def main():
    p=argparse.ArgumentParser();p.add_argument('--project-root',type=Path,required=True)
    p.add_argument('--out-dir',type=Path)
    a=p.parse_args();result=audit(a.project_root)
    if a.out_dir:
        a.out_dir.mkdir(parents=True,exist_ok=True)
        (a.out_dir/'07_12_QUALITY.json').write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    print('07.12 quality gate:', 'PASS' if not result['errors'] else 'FAIL',len(result['errors']),'errors',result['facades'])
    for error in result['errors']:print('QUALITY:',error)
    return bool(result['errors'])
if __name__=='__main__':raise SystemExit(main())
