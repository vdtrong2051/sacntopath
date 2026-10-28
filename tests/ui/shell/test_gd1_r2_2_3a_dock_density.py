"""R2.2.3A: operator task dock density and chrome; requires real PySide6."""
from __future__ import annotations
import os
import pytest
os.environ.setdefault('QT_QPA_PLATFORM','offscreen')
pytest.importorskip('PySide6')
from PySide6.QtWidgets import QApplication, QWidget
from scantopath.ui.shell import ScanToPathMainWindow

@pytest.fixture(scope='module')
def app():
    return QApplication.instance() or QApplication([])

@pytest.fixture
def window(app):
    win=ScanToPathMainWindow()
    win.show()
    app.processEvents()
    yield win
    win.close()
    app.processEvents()

def test_title_three_independent_actions_and_dock_reopen(window,app):
    chrome=window.task_dock_chrome
    panel=window.task_event_panel
    assert window.task_dock.titleBarWidget() is chrome
    assert chrome.height()==44
    assert panel.expand_button.isVisible()
    assert chrome.close_button.isVisible()
    assert chrome.maximize_button.isVisible()
    assert chrome.maximize_button.objectName() == 'taskDockMaximizeButton'
    assert not chrome.findChildren(QWidget, 'taskDockFloatButton')
    assert panel.expand_button.icon().isNull() is False
    assert chrome.close_button.icon().isNull() is False
    chrome.close_button.click()
    app.processEvents()
    assert not window.task_dock.isVisible()
    window.task_dock.toggleViewAction().trigger()
    app.processEvents()
    assert window.task_dock.isVisible()

def test_notification_tab_has_no_permanent_explanation(window,app):
    p=window.task_event_panel
    p.set_expanded(True)
    p.tabs.setCurrentIndex(1)
    app.processEvents()
    assert p.event_hint.isHidden()
    assert p.event_empty.isVisible()
    assert p.event_empty.text()=='Chưa có thông báo.'
    p.add_ui_event('Thông báo thật từ giao diện')
    app.processEvents()
    assert p.event_empty.isHidden()
    assert p.events.isVisible()
    assert p.events.item(p.events.count()-1).text()=='Thông báo thật từ giao diện'

def test_audit_table_uses_available_space_without_hint(window,app):
    p=window.task_event_panel
    p.set_expanded(True)
    p.tabs.setCurrentIndex(2)
    app.processEvents()
    assert p.audit_hint.isHidden()
    assert p.audit_table.isVisible()
    assert p.audit_table.columnWidth(0)>=235
    assert p.audit_table.columnWidth(1)>=85
    assert p.audit_table.header().stretchSectionCount()==1
    page=p.tabs.widget(2)
    assert page.layout().contentsMargins().top()==0
    assert page.layout().contentsMargins().bottom()==0
    assert page.layout().contentsMargins().left()==0
    assert page.layout().contentsMargins().right()==0

def test_tasks_and_audit_remain_distinct(window,app):
    p=window.task_event_panel
    p.set_expanded(True)
    p.tabs.setCurrentIndex(0)
    app.processEvents()
    assert p.task_empty.text()=='Chưa có tác vụ.'
    assert p.tabs.tabText(0)=='Tác vụ'
    assert p.tabs.tabText(1)=='Thông báo UI'
    assert p.tabs.tabText(2)=='Nhật ký SQLite'
    assert window.task_dock.toggleViewAction() is not None
