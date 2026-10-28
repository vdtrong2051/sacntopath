"""R2.2.3B: compact dock sizes and IDE-style scoped tabs, actual PySide6."""
from __future__ import annotations
import os
import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
pytest.importorskip("PySide6")

from PySide6.QtWidgets import QApplication, QToolButton
from scantopath.ui.shell import ScanToPathMainWindow


@pytest.fixture(scope="module")
def app():
    yield QApplication.instance() or QApplication([])


@pytest.fixture
def win(app):
    window = ScanToPathMainWindow()
    window.resize(1366, 768)
    window.show()
    app.processEvents()
    yield window
    window.close()
    app.processEvents()


def test_title_gutter_keeps_three_independent_controls(win):
    chrome = win.task_dock_chrome
    panel = win.task_event_panel
    assert chrome.height() == 44
    assert win.task_dock.titleBarWidget() is chrome
    assert not hasattr(chrome, "float_button")
    assert len(chrome.findChildren(QToolButton)) == 2
    controls = (panel.expand_button, chrome.maximize_button, chrome.close_button)
    assert len({id(c) for c in controls}) == 3
    assert all(not c.icon().isNull() and c.toolTip() for c in controls)


def test_normal_expansion_leaves_room_for_workspaces(win, app):
    panel, chrome = win.task_event_panel, win.task_dock_chrome
    assert not chrome._maximized
    panel.set_expanded(True)
    chrome.resize_to(win.height())
    app.processEvents()
    assert panel.tabs.isVisible()
    # Room is reserved for explorer + actual workspace, not a 60% task drawer.
    assert win.workspace_stack.isVisible()
    assert win.workspace_stack.height() > 160
    assert win.task_dock.height() < win.height() * 0.40
    panel.set_expanded(False)
    chrome.resize_to(win.height())
    app.processEvents()
    assert not panel.expanded and panel.tabs.isHidden()


def test_scoped_tabs_use_navigation_visual_language(win, app):
    panel = win.task_event_panel
    panel.set_expanded(True)
    app.processEvents()
    assert panel.tabs.count() == 3
    assert panel.tabs.tabText(2) == "Nhật ký SQLite"
    style = win.styleSheet()
    assert "/* R2.2.3A-FINAL:" in style
    assert "background-color: #E7F0FF;" in style
    assert "border-bottom: 1px solid #B8CAE0;" in style
    assert "min-height: 18px;" in style
    assert panel.tabs.tabBar().height() < 47
    assert win.task_event_panel.audit_table.columnWidth(0) >= 235
