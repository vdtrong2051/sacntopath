"""08.02 PySide6 MVC integration; offscreen never claims real GPU rendering."""
from __future__ import annotations
import os
import subprocess
import sys
from pathlib import Path

import pytest
os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
pytest.importorskip('PySide6')
from PySide6.QtWidgets import QApplication

from scantopath.application.contracts import WorkspaceId
from scantopath.ui.shell import ScanToPathMainWindow
from scantopath.modules.viewer3d.presentation.controller import Viewer3DController


@pytest.fixture
def app():
    return QApplication.instance() or QApplication([])


def test_lazily_composed_viewer_and_stable_navigation(app):
    window = ScanToPathMainWindow()
    try:
        assert window.viewer3d is None
        assert window.page_for(WorkspaceId.INSPECT3D).findChild(
            type(window.status_message), 'workspaceState').text() == 'CHƯA TRIỂN KHAI'
        window.nav_buttons[WorkspaceId.INSPECT3D].click()
        assert isinstance(window.viewer3d, Viewer3DController)
        first = window.viewer3d
        assert window.page_for(WorkspaceId.INSPECT3D) is first.page
        assert first.page.objectName() == 'workspace_inspect3d'
        assert first.page.accessibleName() == 'Kiểm tra 3D'
        app.processEvents()
        assert 'FIXTURE 08.02' in first.page.state.text()
        assert not first.render_initialized  # offscreen is not Windows GPU proof
        assert 'Không có đơn vị đo xác nhận' in first.page.note.text()
        window.nav_buttons[WorkspaceId.PROJECTS].click()
        window.nav_buttons[WorkspaceId.INSPECT3D].click()
        assert window.viewer3d is first
        assert window.workspace_stack.count() == 4
    finally:
        window.close()
    assert first._disposed


def test_import_and_mainwindow_startup_do_not_import_vtk_or_open_hardware(tmp_path):
    base = Path(__file__).resolve().parents[1]
    script = (
        "import sys; from scantopath.ui.shell import ScanToPathMainWindow; "
        "from PySide6.QtWidgets import QApplication; "
        "app=QApplication([]); w=ScanToPathMainWindow(); "
        "assert not any(x.startswith('vtkmodules') for x in sys.modules); "
        "assert 'scantopath.metadata.store' not in sys.modules; "
        "assert 'scantopath.acquisition.native' not in sys.modules; "
        "assert w.viewer3d is None; w.close(); print('lazy-start-pass')"
    )
    env = {**os.environ, 'QT_QPA_PLATFORM': 'offscreen',
           'PYTHONPATH': str(base/'src') + os.pathsep + os.environ.get('PYTHONPATH', '')}
    proc = subprocess.run([sys.executable, '-c', script], cwd=tmp_path,
                          env=env, capture_output=True, text=True, timeout=25)
    assert proc.returncode == 0, proc.stderr
    assert 'lazy-start-pass' in proc.stdout
    assert not list(tmp_path.iterdir())


def test_viewer_controller_does_not_allocate_scene_in_offscreen(app):
    calls = []
    window = ScanToPathMainWindow()
    try:
        from scantopath.modules.viewer3d.presentation.controller import Viewer3DController
        c = Viewer3DController(window, scene_factory=lambda: calls.append(1))
        c.activate()
        app.processEvents()
        assert calls == []
        assert not c.render_initialized
        c.dispose()
        c.dispose()
    finally:
        window.close()
