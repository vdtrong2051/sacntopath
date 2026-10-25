"""08.01: feature boundaries and a no-runtime-import Viewer architecture baseline."""
from __future__ import annotations
import ast
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]


def _scan_fixture(tmp_path, files: dict[str, str]):
    sys.path.insert(0, str(ROOT / 'scripts'))
    try:
        from check_architecture_boundaries import scan
        base = tmp_path / 'src' / 'scantopath'
        for rel, content in files.items():
            path = base / rel
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(content, encoding='utf-8')
        return scan(tmp_path)
    finally:
        sys.path.remove(str(ROOT / 'scripts'))


def test_cross_feature_infrastructure_import_rejected(tmp_path):
    path = 'modules/alpha/presentation/view.py'
    bad = _scan_fixture(tmp_path, {path: 'from scantopath.modules.beta.infrastructure.ply import Reader\n'})
    assert (path, 1, 'scantopath.modules.beta.infrastructure.ply') in bad


def test_cross_feature_implementation_and_presentation_rejected(tmp_path):
    path = 'modules/alpha/application/use_case.py'
    bad = _scan_fixture(tmp_path, {path: (
        'from scantopath.modules.beta.application.service import Service\n'
        'from scantopath.modules.beta.presentation.controller import Controller\n'
    )})
    assert (path, 1, 'scantopath.modules.beta.application.service') in bad
    assert (path, 2, 'scantopath.modules.beta.presentation.controller') in bad


def test_cross_feature_nested_relative_import_rejected(tmp_path):
    path = 'modules/alpha/presentation/view.py'
    bad = _scan_fixture(tmp_path, {path: (
        'def hidden():\n'
        '    from ...beta.infrastructure import reader\n'
    )})
    assert (path, 2, 'scantopath.modules.beta.infrastructure') in bad


def test_cross_feature_public_contracts_allowed(tmp_path):
    path = 'modules/alpha/application/service.py'
    assert _scan_fixture(tmp_path, {path: (
        'from scantopath.modules.beta.application.ports import ReaderPort\n'
        'from scantopath.modules.beta.application.models import CloudInfo\n'
        'from scantopath.modules.beta.domain.models import XYZ\n'
    )}) == []


def test_presentation_cannot_import_own_concrete_adapter(tmp_path):
    path = 'modules/alpha/presentation/view.py'
    bad = _scan_fixture(tmp_path, {path: (
        'from scantopath.modules.alpha.infrastructure.vtk_renderer import Renderer\n'
    )})
    assert (path, 1, 'scantopath.modules.alpha.infrastructure.vtk_renderer') in bad


def test_application_domain_cannot_import_vtk(tmp_path):
    files = {
        'modules/alpha/application/service.py': 'from vtkmodules.vtkRenderingCore import vtkRenderer\n',
        'modules/alpha/domain/models.py': 'import vtk\n',
    }
    bad = _scan_fixture(tmp_path, files)
    assert len(bad) == 2


def test_compatibility_bootstrap_exception_is_not_expanded(tmp_path):
    path = 'modules/alpha/application/service.py'
    bad = _scan_fixture(tmp_path, {path: (
        'from scantopath.modules.alpha.infrastructure.sqlite_backend import default_factories\n'
    )})
    assert (path, 1, 'scantopath.modules.alpha.infrastructure.sqlite_backend') in bad


def test_repository_import_boundaries_are_clean():
    sys.path.insert(0, str(ROOT / 'scripts'))
    try:
        from check_architecture_boundaries import scan
        assert scan(ROOT) == []
    finally:
        sys.path.remove(str(ROOT / 'scripts'))


def test_probe_does_not_import_project_hardware_or_persistence():
    # This test remains valid after 08.2 introduces the actual Viewer module.
    tree = ast.parse((ROOT / 'scripts' / 'probe_gd1_08_01_vtk_qt.py').read_text(encoding='utf-8'))
    targets = [node.module for node in ast.walk(tree)
               if isinstance(node, ast.ImportFrom) and node.module]
    targets += [item.name for node in ast.walk(tree) if isinstance(node, ast.Import)
                for item in node.names]
    assert not any(target.startswith('scantopath.') for target in targets)
