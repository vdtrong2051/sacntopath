"""R2.2.1: real PySide6 task-dock header and SRP regression (not screenshot proof)."""
from __future__ import annotations
import os
from pathlib import Path
import pytest

os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
pytest.importorskip('PySide6')
from PySide6.QtWidgets import QApplication
from scantopath.application.contracts import TaskSnapshot, TaskState
from scantopath.ui.shell import ScanToPathMainWindow


@pytest.fixture(scope='module')
def app():
    yield QApplication.instance() or QApplication([])


@pytest.fixture
def window(app):
    win=ScanToPathMainWindow()
    win.show()
    app.processEvents()
    yield win
    win.close()
    app.processEvents()


def test_task_titlebar_owns_toggle_summary_and_native_reopen(window,app):
    chrome=window.task_dock_chrome
    panel=window.task_event_panel
    assert window.task_dock.titleBarWidget() is chrome
    assert panel.expand_button.parentWidget() is chrome
    assert chrome.summary.text()=='Không có tác vụ đang chạy'
    assert panel.compact_summary.isHidden()
    assert panel.expand_button.isVisible()
    assert not panel.expanded and panel.tabs.isHidden()
    assert chrome.close_button.isVisible()
    assert chrome.float_button.isVisible()
    assert window.task_dock.toggleViewAction() is not None


def test_task_titlebar_toggle_keeps_three_tabs_and_contents(window,app):
    p=window.task_event_panel
    p.expand_button.click();app.processEvents()
    assert p.expanded and p.tabs.isVisible()
    assert p.task_empty.isVisible()
    assert p.cancel_button.isHidden()
    assert p.demo_button.isHidden()
    assert p.tabs.count()==3
    p.tabs.setCurrentIndex(1)
    p.add_ui_event('R2.2.1 no lost events')
    p.expand_button.click();app.processEvents()
    assert not p.expanded and p.tabs.isHidden()
    p.expand_button.click();app.processEvents()
    assert p.tabs.currentIndex()==1
    assert any(p.events.item(i).text()=='R2.2.1 no lost events' for i in range(p.events.count()))


def test_running_task_is_visible_from_title_and_expanded_list(window,app):
    p=window.task_event_panel
    p.set_expanded(False)
    p.set_tasks((TaskSnapshot(task_id='running-a',title='Thao tác thật',state=TaskState.RUNNING,can_cancel=True),))
    app.processEvents()
    assert '1 tác vụ đang chờ/xử lý' in window.task_dock_chrome.summary.text()
    p.expand_button.click();app.processEvents()
    assert p.expanded and p.tasks.isVisible()
    assert p.tasks.topLevelItemCount()==1
    assert p.cancel_button.isVisible()
    p.tasks.setCurrentItem(p.tasks.topLevelItem(0))
    assert p.cancel_button.isEnabled()
    p.set_tasks(())
    app.processEvents()
    assert not p.cancel_button.isVisible()
    assert p.task_empty.isVisible()


def test_task_dock_can_be_hidden_and_reopened(window,app):
    window.task_dock_chrome.close_button.click();app.processEvents()
    assert not window.task_dock.isVisible()
    window.task_dock.toggleViewAction().trigger();app.processEvents()
    assert window.task_dock.isVisible()
    window.task_event_panel.set_expanded(False)
    window._open_audit_panel();app.processEvents()
    assert window.task_event_panel.expanded
    assert window.task_event_panel.tabs.currentIndex()==2


def test_shell_stays_below_original_500_line_architecture_budget():
    root=Path(__file__).resolve().parents[1]
    shell=(root/'src/scantopath/ui/shell/main_window.py').read_text(encoding='utf-8')
    assert len(shell.splitlines()) < 500
    assert 'TaskDockChrome' in shell
    assert 'task_dock_chrome.open_audit()' in shell
