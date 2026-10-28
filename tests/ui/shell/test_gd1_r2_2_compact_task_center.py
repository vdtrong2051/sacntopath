"""R2.2: actual Qt widget behavior; offscreen complements manual Windows HMI."""
from __future__ import annotations

import os
import pytest
os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
pytest.importorskip('PySide6')

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QApplication
from scantopath.application.contracts import TaskSnapshot, TaskState, WorkspaceId
from scantopath.ui.components.task_event_panel import TaskAndEventPanel
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


def test_task_center_default_collapsed_with_native_dock_visible(window,app):
    app.processEvents()
    assert window.task_dock.isVisible()
    assert window.task_dock.widget() is window.task_event_panel
    assert not window.task_event_panel.expanded
    assert window.task_event_panel.tabs.isHidden()
    assert window.task_event_panel.compact_summary.text() == 'Không có tác vụ đang chạy'
    assert window.task_event_panel.expand_button.isVisible()
    assert window.task_event_panel.demo_button.isHidden()
    assert window.task_event_panel.tabs.count() == 3
    assert window.task_event_panel.tasks.topLevelItemCount() == 0


def test_task_center_expand_collapse_preserves_tabs_and_data(window,app):
    panel=window.task_event_panel
    panel.expand_button.click(); app.processEvents()
    assert panel.expanded and panel.tabs.isVisible()
    panel.add_ui_event('R2.2 UI sự kiện')
    panel.tabs.setCurrentIndex(1)
    panel.expand_button.click(); app.processEvents()
    assert not panel.expanded and panel.tabs.isHidden()
    panel.expand_button.click(); app.processEvents()
    assert panel.tabs.currentIndex() == 1
    assert any(panel.events.item(i).text()=='R2.2 UI sự kiện' for i in range(panel.events.count()))


def test_processing_audit_reopens_collapsed_center(window,app):
    window.task_event_panel.set_expanded(False)
    window._open_audit_panel();app.processEvents()
    assert window.task_dock.isVisible()
    assert window.task_event_panel.expanded
    assert window.task_event_panel.tabs.isVisible()
    assert window.task_event_panel.tabs.currentIndex()==2


def test_help_developer_tools_explicit_opt_in(window,app):
    tools=window.findChild(type(window.workspace_actions[WorkspaceId.PROJECTS]),'actionTaskDemoTools')
    assert tools is not None and tools.isCheckable() and not tools.isChecked()
    assert window.task_event_panel.demo_button.isHidden()
    tools.trigger();app.processEvents()
    assert tools.isChecked()
    assert window.task_event_panel.expanded
    assert window.task_event_panel.demo_button.isVisible()
    tools.trigger();app.processEvents()
    assert not tools.isChecked()
    assert window.task_event_panel.demo_button.isHidden()


def test_task_center_summary_tracks_real_task_snapshots_without_processingrun(app):
    panel=TaskAndEventPanel()
    try:
        panel.set_expanded(False)
        panel.set_tasks((TaskSnapshot(task_id='t-1',title='Fixture',state=TaskState.RUNNING,progress=None),))
        assert '1 tác vụ đang chờ/xử lý' in panel.compact_summary.text()
        assert panel.tasks.topLevelItemCount()==1
        panel.set_tasks((TaskSnapshot(task_id='t-1',title='Fixture',state=TaskState.FAILED,progress=0),))
        assert '1 tác vụ thất bại' in panel.compact_summary.text()
        panel.set_tasks(())
        assert panel.compact_summary.text()=='Không có tác vụ đang chạy'
    finally:
        panel.close()


def test_native_dock_controls_and_workspace_shortcuts_preserved(window,app):
    menu=next(a.menu() for a in window.menuBar().actions() if a.text().replace('&','')=='Hiển thị')
    assert len(menu.actions())==3
    assert window.task_dock.toggleViewAction() in menu.actions()
    window.task_dock.hide();app.processEvents()
    assert not window.task_dock.isVisible()
    window.task_dock.toggleViewAction().trigger();app.processEvents()
    assert window.task_dock.isVisible()
    for i,workspace in enumerate(WorkspaceId,1):
        assert window.workspace_actions[workspace].shortcut().toString()==f'Ctrl+{i}'
        window.nav_buttons[workspace].click()
        assert window.active_workspace==workspace
