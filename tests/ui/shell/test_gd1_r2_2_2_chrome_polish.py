"""R2.2.2: task dock chrome and SQLite UTC column, requires actual Qt."""
import os
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
import pytest
pytest.importorskip("PySide6")
from PySide6.QtWidgets import QApplication
from scantopath.ui.shell import ScanToPathMainWindow

@pytest.fixture(scope="module")
def app():
    return QApplication.instance() or QApplication([])

@pytest.fixture
def window(app):
    w = ScanToPathMainWindow()
    w.show()
    app.processEvents()
    yield w
    w.close()
    app.processEvents()

def test_title_icons_are_vectors_without_font_dependent_glyphs(window):
    chrome = window.task_dock_chrome
    buttons = (window.task_event_panel.expand_button,
               chrome.maximize_button, chrome.close_button)
    for button in buttons:
        assert button.text() == ""
        assert not button.icon().isNull()
        assert button.toolTip()
        assert button.accessibleName()
    assert window.task_dock.titleBarWidget() is chrome
    assert chrome.maximize_button.isVisible()  # R2.2.3A final: independent square button

def test_toggle_updates_icon_without_losing_dock_contents(window, app):
    panel = window.task_event_panel
    assert not panel.expanded
    panel.expand_button.click()
    app.processEvents()
    assert panel.expanded
    assert panel.expand_button.text() == ""
    assert not panel.expand_button.icon().isNull()
    assert panel.tabs.isVisible()
    panel.expand_button.click()
    app.processEvents()
    assert not panel.expanded and panel.tabs.isHidden()

def test_utc_column_has_readable_default_width(window):
    audit = window.task_event_panel.audit_table
    assert audit.headerItem().text(0) == "Thời gian (UTC)"
    assert audit.columnWidth(0) >= 235
    assert audit.columnCount() == 4
