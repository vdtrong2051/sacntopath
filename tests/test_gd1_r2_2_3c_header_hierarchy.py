"""R2.2.3C: verify real Qt header geometry + bounded dock + 3 native actions."""
from __future__ import annotations
import os
import pytest
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
pytest.importorskip("PySide6")
from PySide6.QtCore import QPoint
from PySide6.QtWidgets import QApplication
from scantopath.ui.shell import ScanToPathMainWindow

@pytest.fixture(scope="module")
def app():
    return QApplication.instance() or QApplication([])

@pytest.fixture
def window(app):
    w = ScanToPathMainWindow()
    w.resize(1366, 768)
    w.show()
    app.processEvents()
    yield w
    w.close()
    app.processEvents()

def test_title_is_44_pixels_with_visible_distinct_actions(window, app):
    chrome = window.task_dock_chrome
    panel = window.task_event_panel
    assert chrome.height() == 44
    assert chrome._header_separator.objectName() == "taskDockHeaderSeparator"
    assert chrome._header_separator.height() == 1
    assert window.task_dock.titleBarWidget() is chrome
    assert len({id(panel.expand_button), id(chrome.maximize_button), id(chrome.close_button)}) == 3
    assert panel.expand_button.isVisible() and chrome.maximize_button.isVisible() and chrome.close_button.isVisible()
    assert panel.expand_button.geometry().right() < chrome.maximize_button.geometry().left()
    assert chrome.maximize_button.geometry().right() < chrome.close_button.geometry().left()

def test_tab_band_and_content_have_independent_surfaces(window, app):
    panel = window.task_event_panel
    panel.set_expanded(True)
    window.task_dock_chrome.resize_to(window.height())
    app.processEvents()
    assert panel.tabs.isVisible()
    app.processEvents()
    header_bottom = window.task_dock_chrome.mapTo(
        window.task_dock, QPoint(0, window.task_dock_chrome.height())).y()
    tab_top = panel.tabs.tabBar().mapTo(window.task_dock, QPoint(0, 0)).y()
    assert tab_top >= header_bottom + 2, (header_bottom, tab_top)
    assert panel.tabs.tabBar().isVisible()
    assert 22 <= panel.tabs.tabBar().height() < 45
    assert window.task_dock.height() <= 195
    assert window.workspace_stack.height() >= window.height() * 0.38
    qss = window.styleSheet()
    assert '/* R2.2.3C:' in qss
    assert 'background-color: #EBF2FA;' in qss
    assert 'border-top: 1px solid #B9CCDF;' in qss

def test_collapsed_and_square_restore_obey_actual_dock_height(window, app):
    p, chrome = window.task_event_panel, window.task_dock_chrome
    p.set_expanded(False)
    chrome.resize_to(window.height())
    app.processEvents()
    assert window.task_dock.height() <= 54
    chrome.maximize_button.click()
    app.processEvents()
    assert chrome._maximized and p.expanded
    assert window.task_dock.height() <= 315
    chrome.maximize_button.click()
    app.processEvents()
    assert not chrome._maximized and not p.expanded
    assert window.task_dock.height() <= 54
