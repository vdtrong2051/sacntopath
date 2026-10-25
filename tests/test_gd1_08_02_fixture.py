"""08.02 pure architecture/fixture/VTK object checks, no GUI or hardware."""
from __future__ import annotations
import ast
from pathlib import Path

from scantopath.modules.viewer3d.domain.fixture import FIVE_POINT_FIXTURE

ROOT = Path(__file__).resolve().parents[1]


def test_fixture_is_immutable_and_unmeasured():
    assert FIVE_POINT_FIXTURE.point_count == 5
    assert FIVE_POINT_FIXTURE.points[0] == (0., 0., 0.)
    assert FIVE_POINT_FIXTURE.points[-1] == (.25, .25, .25)
    assert FIVE_POINT_FIXTURE.source == 'synthetic_08_02'
    assert FIVE_POINT_FIXTURE.units is None
    assert FIVE_POINT_FIXTURE.coordinate_frame == 'fixture_local'


def test_viewer_application_domain_are_ui_and_vtk_free():
    base = ROOT / 'src/scantopath/modules/viewer3d'
    for layer in ('domain', 'application'):
        for f in (base/layer).rglob('*.py'):
            tree = ast.parse(f.read_text(encoding='utf-8'))
            imports = [n.module for n in ast.walk(tree) if isinstance(n, ast.ImportFrom)]
            imports += [a.name for n in ast.walk(tree) if isinstance(n, ast.Import) for a in n.names]
            assert not any(s and s.startswith(('PySide6', 'vtkmodules', 'vtk', 'scantopath.ui')) for s in imports), f


def test_vtk_scene_owns_exact_five_points():
    from scantopath.modules.viewer3d.infrastructure.fixture_scene import VtkFixtureScene
    scene = VtkFixtureScene()
    try:
        assert scene.point_count == 5
        assert scene.renderer.GetActors().GetNumberOfItems() == 1
        assert scene._polydata.GetPoint(4) == (.25, .25, .25)
    finally:
        scene.dispose()
        scene.dispose()
    assert scene.renderer.GetActors().GetNumberOfItems() == 0


def test_declarative_optional_viewer_dependency():
    import tomllib
    conf = tomllib.loads((ROOT / 'pyproject.toml').read_text(encoding='utf-8'))
    assert any(dep.startswith('vtk>=') for dep in conf['project']['optional-dependencies']['viewer'])
    assert not any(dep.startswith('vtk') for dep in conf['project']['dependencies'])
