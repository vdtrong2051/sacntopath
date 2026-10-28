"""08.02 VTK native-fault isolation invariants (safe without display server)."""
from __future__ import annotations
import ast
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
BASE = ROOT / 'src' / 'scantopath' / 'modules' / 'viewer3d'


def test_no_vtk_interactor_in_desktop_process():
    controller = (BASE / 'presentation' / 'controller.py').read_text(encoding='utf8')
    view = (BASE / 'presentation' / 'view.py').read_text(encoding='utf8')
    assert 'QVTKRenderWindowInteractor' not in view
    # The name in the controller is used exclusively in a negative explanatory docstring.
    assert 'QVTKRenderWindowInteractor(' not in controller
    for text in (controller, view):
        code = ast.parse(text)
        targets = [n.module for n in ast.walk(code) if isinstance(n, ast.ImportFrom) and n.module]
        targets += [alias.name for n in ast.walk(code) if isinstance(n, ast.Import) for alias in n.names]
        assert not any(x.startswith(('vtk', 'vtkmodules')) for x in targets)


def test_child_vtk_renderer_has_no_qt_or_persistence_imports():
    source = (BASE / 'infrastructure' / 'render_preview.py').read_text(encoding='utf8')
    tree = ast.parse(source)
    imports = [n.module for n in ast.walk(tree) if isinstance(n, ast.ImportFrom) and n.module]
    imports += [a.name for n in ast.walk(tree) if isinstance(n, ast.Import) for a in n.names]
    assert not any(x.startswith(('PySide6', 'scantopath.ui', 'sqlite3', 'scantopath.metadata')) for x in imports)
    assert 'window.SetOffScreenRendering(1)' in source
    assert 'SCANTOPATH_VTK_PREVIEW_OK' in source


def test_subprocess_has_timeout_and_cleanup():
    source = (BASE / 'presentation' / 'controller.py').read_text(encoding='utf8')
    for contract in ('QProcess(self)', 'process.finished.connect(self._finished)',
                     'process.errorOccurred.connect(self._process_error)',
                     'timer.setSingleShot(True)', 'self._process.kill()',
                     'self._temp.cleanup()', 'self.page.show_png(png)'):
        assert contract in source


def test_five_points_still_unchanged():
    from scantopath.modules.viewer3d.domain.fixture import FIVE_POINT_FIXTURE
    assert FIVE_POINT_FIXTURE.point_count == 5
    assert FIVE_POINT_FIXTURE.units is None
