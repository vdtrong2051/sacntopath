"""GD2-09.09.3: presentation-only Capture layout regression (no camera/SQLite)."""
from __future__ import annotations
import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest
pytest.importorskip("PySide6")
from PySide6.QtCore import Qt
from PySide6.QtWidgets import QApplication, QTabWidget, QWidget, QPushButton

from scantopath.application.contracts import SelectionRef, WorkspaceId
from scantopath.ui.shell import ScanToPathMainWindow


@pytest.fixture(scope="module")
def qapp():
    return QApplication.instance() or QApplication([])


@pytest.fixture
def window(qapp):
    win = ScanToPathMainWindow()
    win.resize(1280, 800)
    win.show()
    qapp.processEvents()
    yield win
    win.close()
    qapp.processEvents()


def test_existing_four_workspaces_and_panes_preserved(window):
    assert window.workspace_stack.count() == 4
    assert window.page_for(WorkspaceId.CAPTURE).objectName() == "workspace_capture"
    tabs = window.capture_workspace_layout.tabs
    assert isinstance(tabs, QTabWidget)
    assert tabs.count() == 2
    assert tabs.widget(0) is window.capture_live.panel
    assert tabs.widget(1) is window.capture_preview.panel
    assert window.capture_live.panel.objectName() == "captureLivePanel"
    assert window.capture_preview.panel.objectName() == "capturePreview"


def test_default_is_live_and_camera_is_not_opened(window):
    assert window.capture_workspace_layout.tabs.currentWidget() is window.capture_live.panel
    assert window.capture_live.state.value == "idle"
    assert window.capture_preview.context is None
    assert not window.capture_preview.panel.replay_button.isEnabled()


def test_capture_and_session_selection_choose_right_tab(window, qapp):
    window._navigate(WorkspaceId.CAPTURE)
    qapp.processEvents()
    window.project_explorer.selection_changed.emit(SelectionRef("capture", "test-capture"))
    assert window.capture_workspace_layout.tabs.currentWidget() is window.capture_preview.panel
    window.project_explorer.selection_changed.emit(SelectionRef("scan_session", "test-session"))
    assert window.capture_workspace_layout.tabs.currentWidget() is window.capture_live.panel


def test_switch_tabs_without_disposing_controllers(window, qapp):
    tabs = window.capture_workspace_layout.tabs
    tabs.setCurrentIndex(1)
    tabs.setCurrentIndex(0)
    qapp.processEvents()
    assert window.capture_live.panel.findChild(QPushButton, "captureLiveStartButton") is not None
    assert window.capture_preview.panel.findChild(QPushButton, "captureReplayButton") is not None
    assert window.explorer_dock.isVisible()


def test_compact_layout_no_horizontal_scroll_or_duplicate_header(window, qapp):
    page = window.page_for(WorkspaceId.CAPTURE)
    scroll = page.findChild(QWidget, "workspaceScrollContent")
    assert scroll is not None
    assert window.capture_workspace_layout.workflow_bar.objectName() == "captureWorkflowBar"
    for name in ("workspaceHeading", "workspaceSubtitle"):
        from PySide6.QtWidgets import QLabel
        label = scroll.findChild(QLabel, name, Qt.FindDirectChildrenOnly)
        assert label is None or label.isHidden()
    for width, height in ((1200, 760), (940, 620), (1380, 860)):
        window.resize(width, height)
        qapp.processEvents()
        assert window.capture_workspace_layout.tabs.count() == 2
        assert window.capture_workspace_layout.tabs.indexOf(window.capture_live.panel) == 0
        assert window.capture_workspace_layout.tabs.indexOf(window.capture_preview.panel) == 1
