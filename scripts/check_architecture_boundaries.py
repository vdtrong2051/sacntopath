"""07.10: fail fast on architectural import regressions, without loading app/hardware.

AST inspects even imports inside functions. This is a boundary gate, not a SOLID score.
"""
from __future__ import annotations

import argparse
import ast
from pathlib import Path
import sys


LAYERS = {'application', 'domain', 'metadata', 'storage', 'acquisition'}


def scan(project_root: Path) -> list[tuple[str, int, str]]:
    root = project_root / 'src' / 'scantopath'
    if not root.is_dir():
        raise ValueError('Expected src/scantopath')
    violations = []
    for path in sorted(root.rglob('*.py')):
        rel = path.relative_to(root)
        module = 'scantopath.'+'.'.join(rel.with_suffix('').parts)
        parts = rel.parts
        if not parts:
            continue
        layer = parts[0]
        core = layer in LAYERS or (len(parts) >= 3 and parts[:2] == ('modules','project_workspace') and parts[2] in ('application','domain'))
        presentation = (len(parts) >= 3 and parts[:2] == ('modules','project_workspace') and parts[2] == 'presentation')
        shell = parts[:2] == ('ui','shell')
        tree = ast.parse(path.read_text(encoding='utf-8'), filename=str(path))
        for node in ast.walk(tree):
            names = []
            if isinstance(node,ast.Import):
                names = [n.name for n in node.names]
            elif isinstance(node,ast.ImportFrom):
                # Absolute imported modules are enough for guard; relative in-module imports okay.
                if not node.level and node.module:
                    names=[node.module]
            for target in names:
                if core and (target == 'PySide6' or target.startswith('PySide6.') or target == 'scantopath.ui' or target.startswith('scantopath.ui.') or '.presentation' in target and target.startswith('scantopath.modules.')):
                    violations.append((rel.as_posix(),node.lineno,target))
                if presentation and (target == 'scantopath.metadata' or target.startswith('scantopath.metadata.') or target == 'scantopath.storage' or target.startswith('scantopath.storage.')):
                    violations.append((rel.as_posix(),node.lineno,target))
                if shell and (target == 'scantopath.metadata' or target.startswith('scantopath.metadata.') or target == 'scantopath.storage' or target.startswith('scantopath.storage.')):
                    violations.append((rel.as_posix(),node.lineno,target))
    return violations


def main() -> int:
    p=argparse.ArgumentParser()
    p.add_argument('--project-root',type=Path,default=Path(__file__).resolve().parents[1])
    args=p.parse_args()
    bad=scan(args.project_root)
    for filename,line,target in bad:
        print(f'ARCH VIOLATION {filename}:{line}: forbidden import {target}')
    print(f'07.10 architecture import boundary: {"FAILED" if bad else "PASS"} ({len(bad)} violations)')
    return 1 if bad else 0

if __name__=='__main__':
    sys.exit(main())
