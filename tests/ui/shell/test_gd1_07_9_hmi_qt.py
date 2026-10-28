"""07.9 recovery visual UX tests; offscreen cannot replace real Windows UI review."""
import os
import pytest
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
pytest.importorskip("PySide6")
from PySide6.QtWidgets import QApplication, QToolBar, QPushButton
from scantopath.ui.shell import ScanToPathMainWindow
from scantopath.application.contracts import WorkspaceId
from scantopath.ui.workspaces import WORKSPACE_PRESENTATION

@pytest.fixture(scope="module")
def app():
    yield QApplication.instance() or QApplication([])

@pytest.fixture
def window(app):
    w=ScanToPathMainWindow()
    w.show(); app.processEvents()
    yield w
    w.close(); app.processEvents()

def test_single_horizontal_toolbar_and_no_navigation_rail(window, app):
    assert isinstance(window.workspace_toolbar, QToolBar)
    assert window.workspace_toolbar.isVisible()
    assert window.workspace_toolbar.isMovable() is False
    assert not hasattr(window, "navigation_sidebar")
    assert not hasattr(window, "nav_compact_button")
    assert window.workspace_toolbar.width() >= window.workspace_stack.width()

def test_visible_navigation_and_existing_shortcuts(window):
    for index, workspace in enumerate(WorkspaceId, start=1):
        button=window.nav_buttons[workspace]
        assert button.toolTip()==WORKSPACE_PRESENTATION[workspace].title
        assert button.text() not in ("DA", "RGB", "XL")
        assert window.workspace_actions[workspace].shortcut().toString()==f"Ctrl+{index}"
        button.click()
        assert window.active_workspace==workspace
        assert window.workspace_stack.currentWidget() is window.page_for(workspace)

def test_workspace_button_uses_existing_store_dialog(window, monkeypatch, app):
    import scantopath.ui.shell.main_window as shell
    roots=[]
    class FakeDialog:
        @staticmethod
        def getExistingDirectory(*a, **kw):
            roots.append("opened")
            return ""  # cancel: must not create SQLite
    monkeypatch.setattr(shell,"QFileDialog",FakeDialog)
    action=window.page_for(WorkspaceId.PROJECTS).findChild(QPushButton,"workspacePrimaryAction")
    assert action is not None
    action.click()
    assert roots == ["opened"]
    assert window.project_explorer.store_root is None

def test_processing_action_brings_sqlite_timeline_forward(window, app):
    action=window.page_for(WorkspaceId.PROCESSING).findChild(QPushButton,"workspacePrimaryAction")
    assert action is not None
    action.click();app.processEvents()
    assert window.task_dock.isVisible()
    assert window.task_event_panel.tabs.currentIndex()==2

def test_resize_retains_navigation_and_reopenable_docks(window, app):
    window.resize(900,535); app.processEvents()
    window._initialize_dock_layout(); app.processEvents()
    assert window.workspace_stack.width()>200
    for dock in (window.explorer_dock,window.inspector_dock,window.task_dock):
        assert dock.toggleViewAction() is not None
    assert all(b.isEnabled() for b in window.nav_buttons.values())

def test_07_workspace_states_and_no_implicit_db(window):
    for workspace in (WorkspaceId.PROJECTS,WorkspaceId.PROCESSING):
        page=window.page_for(workspace)
        label=page.findChild(type(window.status_message),"workspaceState")
        assert label.text()=="CÓ THỂ SỬ DỤNG QUA PANEL"
    assert window.project_explorer.store_root is None
    assert not window.project_loader.busy
    assert not window.capture_checker.busy
