"""07.11: AST import policy for an offline-first modular MVC monolith.

No imports or runtime resource loading. Checks absolute AND relative imports,
including imports nested in functions. The one compatibility bootstrap seam
is reviewed and must not expand to other application modules.
"""
from __future__ import annotations
import argparse
import ast
from pathlib import Path
import sys

CORE = {'application', 'domain', 'metadata', 'storage', 'acquisition'}
FEATURE = 'scantopath.modules.'
ALLOWED_BOOTSTRAP = ('modules/project_workspace/application/service.py',
                     'scantopath.modules.project_workspace.infrastructure.sqlite_backend')
# Only stable DTO/Protocol surfaces may be shared between feature modules.
CROSS_FEATURE_PUBLIC = ('application.ports', 'application.models',
                        'application.contracts', 'domain.models')


def _resolved_imports(node: ast.AST, module_parts: tuple[str, ...], is_package: bool):
    if isinstance(node, ast.Import):
        return [alias.name for alias in node.names]
    if not isinstance(node, ast.ImportFrom):
        return []
    if node.level == 0:
        return [node.module] if node.module else []
    package = module_parts if is_package else module_parts[:-1]
    trim = node.level - 1
    if trim > len(package):
        return []
    prefix = package[:len(package) - trim]
    target = '.'.join((*prefix, *(node.module.split('.') if node.module else ())))
    if node.module is None:
        return [target + '.' + alias.name for alias in node.names]
    return [target]


def _starts(target: str, prefix: str) -> bool:
    return target == prefix or target.startswith(prefix + '.')


def scan(project_root: Path) -> list[tuple[str, int, str]]:
    root = project_root / 'src' / 'scantopath'
    if not root.is_dir():
        raise ValueError('Expected src/scantopath')
    violations = []
    for path in sorted(root.rglob('*.py')):
        rel = path.relative_to(root)
        relative = rel.as_posix()
        module_parts = ('scantopath', *rel.with_suffix('').parts)
        kind = rel.parts[0]
        is_feature = len(rel.parts) >= 3 and rel.parts[0] == 'modules'
        area = rel.parts[2] if is_feature else None
        core = kind in CORE or area in ('application', 'domain', 'infrastructure')
        presentation = area == 'presentation'
        shell = rel.parts[:2] == ('ui','shell')
        tree = ast.parse(path.read_text(encoding='utf8'), filename=str(path))
        for node in ast.walk(tree):
            if not isinstance(node, (ast.Import, ast.ImportFrom)):
                continue
            for target in _resolved_imports(node, module_parts, path.name == '__init__.py'):
                forbidden = False
                if core:
                    forbidden |= _starts(target, 'PySide6') or _starts(target, 'scantopath.ui')
                    forbidden |= (target.startswith(FEATURE) and '.presentation' in target)
                if presentation or shell:
                    # UXH-01.1: UI/presentation cannot open SQLite directly.
                    forbidden |= (_starts(target, 'scantopath.metadata') or
                                  _starts(target, 'scantopath.storage') or
                                  _starts(target, 'sqlite3'))
                # 08.01: protect feature ownership as the second feature (Viewer) arrives.
                # Other modules may expose small typed contracts but not concrete
                # infrastructure, presentation, services or private implementations.
                if is_feature and target.startswith(FEATURE):
                    parts = target.split('.')
                    if len(parts) >= 3 and parts[2] != rel.parts[1]:
                        public = '.'.join(parts[3:])
                        if not any(_starts(public, api) for api in CROSS_FEATURE_PUBLIC):
                            forbidden = True
                    if area == 'presentation' and _starts(
                            target, f'{FEATURE}{rel.parts[1]}.infrastructure'):
                        forbidden = True
                # Rendering belongs to the Qt presentation/VTK adapter boundary;
                # do not let application/domain silently depend on the VTK runtime.
                if kind in ('application', 'domain') or area in ('application', 'domain'):
                    forbidden |= _starts(target, 'vtkmodules') or _starts(target, 'vtk')
                if area in ('application','domain'):
                    # The feature core must not depend on concrete providers. Only
                    # the legacy facade may import the specific feature bootstrap.
                    forbidden |= (_starts(target,'scantopath.metadata') or
                                  _starts(target,'scantopath.storage') or
                                  _starts(target,'sqlite3'))
                    if '.infrastructure' in target:
                        forbidden |= (relative,target) != ALLOWED_BOOTSTRAP
                if area == 'infrastructure' and (_starts(target,'scantopath.ui') or
                                                 target.startswith(FEATURE) and '.presentation' in target):
                    forbidden = True
                if forbidden:
                    violations.append((relative, node.lineno, target))
    return violations


def main() -> int:
    p=argparse.ArgumentParser()
    p.add_argument('--project-root',type=Path,default=Path(__file__).resolve().parents[1])
    a=p.parse_args()
    bad=scan(a.project_root)
    for file,line,target in bad:
        print(f'ARCH VIOLATION {file}:{line}: forbidden import {target}')
    print(f'07.11 architecture import boundary: {"FAILED" if bad else "PASS"} ({len(bad)} violations)')
    return 1 if bad else 0

if __name__ == '__main__':
    sys.exit(main())
