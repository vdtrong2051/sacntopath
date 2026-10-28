"""R2.2.3B: real Qt dock height + workspace geometry after event processing."""
from __future__ import annotations
import os
import pytest
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
pytest.importorskip("PySide6")
from PySide6.QtWidgets import QApplication
from scantopath.ui.shell import ScanToPathMainWindow

@pytest.fixture(scope="module")
def app():
    return QApplication.instance() or QApplication([])

@pytest.fixture
def window(app):
    w = ScanToPathMainWindow()
    w.resize(1200, 800)
    w.show()
    app.processEvents()
    w._initialize_dock_layout()
    app.processEvents()
    yield w
    w.close()
    app.processEvents()

def _geometry(window, app):
    app.processEvents()
    return (window.height(), window.task_dock.height(),
            window.workspace_stack.height(), window.task_dock_chrome._maximized)

def test_normal_open_and_collapse_have_measured_height_limits(window, app):
    p = window.task_event_panel
    chrome = window.task_dock_chrome
    assert not chrome._maximized
    p.set_expanded(True)
    chrome.resize_to(window.height())
    height, dock, center, maximized = _geometry(window, app)
    assert not maximized
    assert dock <= 195, (height, dock, center)
    assert center >= height * 0.40, (height, dock, center)
    p.set_expanded(False)
    chrome.resize_to(window.height())
    height, dock, center, _ = _geometry(window, app)
    assert dock <= 54, (height, dock, center)

def test_square_restore_and_reopen_never_leave_unbounded_dock(window, app):
    p = window.task_event_panel
    chrome = window.task_dock_chrome
    chrome.maximize_button.click()
    height, dock, center, maximized = _geometry(window, app)
    assert maximized and p.expanded
    assert dock <= 315, (height, dock, center)
    assert center >= height * 0.33, (height, dock, center)
    chrome.maximize_button.click()
    height, dock, center, maximized = _geometry(window, app)
    assert not maximized and not p.expanded
    assert dock <= 54, (height, dock, center)
    chrome.close_button.click()
    app.processEvents()
    assert not window.task_dock.isVisible()
    window.task_dock.toggleViewAction().trigger()
    app.processEvents()
    assert window.task_dock.isVisible()
    chrome.resize_to(window.height())
    assert window.task_dock.height() <= 54

def test_source_no_legacy_unbounded_resize_and_no_visitor_state_loss(window, app):
    chrome = window.task_dock_chrome
    assert chrome._dock.maximumHeight() <= 315
    assert window.task_dock.titleBarWidget() is chrome
    assert len({id(window.task_event_panel.expand_button),
                id(chrome.maximize_button), id(chrome.close_button)}) == 3
