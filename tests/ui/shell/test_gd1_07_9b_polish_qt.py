"""07.9B native Qt behavior: no SQL/RAW/3D access, offscreen-only verification."""
import os
import pytest

os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
pytest.importorskip('PySide6')

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QApplication, QBoxLayout, QScrollArea
from scantopath.application.contracts import SelectionRef, WorkspaceId
from scantopath.ui.components import ExplorerNode, ProjectExplorer, PropertyInspector, TaskAndEventPanel
from scantopath.ui.shell import ScanToPathMainWindow


@pytest.fixture(scope='module')
def app():
    return QApplication.instance() or QApplication([])


def test_long_explorer_label_has_tooltip_and_elision(app):
    panel = ProjectExplorer()
    try:
        value = 'P0001 - ' + 'Chi tiết gia công nhiều bề mặt cong ' * 6
        node = ExplorerNode(value, SelectionRef('project', 'project-long-name'))
        panel.set_nodes((node,))
        item = panel.tree.topLevelItem(0)
        assert item.toolTip(0) == value
        assert panel.tree.textElideMode() == Qt.ElideMiddle
    finally:
        panel.close()


def test_inspector_values_remain_available_in_tooltips(app):
    panel = PropertyInspector()
    try:
        panel.set_selection(SelectionRef('project', 'sample'))
        long_value = 'Tên vật mẫu đặc biệt / ' * 12
        panel.set_store_fields((('Tên dự án', long_value),))
        assert panel.details.textElideMode() == Qt.ElideMiddle
        assert any(panel.details.topLevelItem(i).toolTip(1) == long_value
                   for i in range(panel.details.topLevelItemCount()))
    finally:
        panel.close()


def test_task_buttons_stack_only_when_dock_is_narrow(app):
    panel = TaskAndEventPanel()
    try:
        panel.resize(390, 230)
        panel.show()
        app.processEvents()
        assert panel.action_buttons_layout.direction() == QBoxLayout.TopToBottom
        panel.resize(680, 260)
        app.processEvents()
        assert panel.action_buttons_layout.direction() == QBoxLayout.LeftToRight
        assert panel.demo_button.text() == 'Chạy tác vụ KIỂM THỬ'
        assert panel.cancel_button.text() == 'Yêu cầu hủy tác vụ'
    finally:
        panel.close()


@pytest.mark.parametrize('logical_size', [(1366, 768), (1120, 630), (850, 520)])
def test_native_panel_borders_do_not_destroy_viewport(app, logical_size):
    win = ScanToPathMainWindow()
    try:
        win.show()
        win.resize(*logical_size)
        app.processEvents()
        win._initialize_dock_layout()
        app.processEvents()
        assert win.explorer_dock.minimumWidth() >= 205
        assert win.inspector_dock.minimumWidth() >= 215
        assert win.workspace_stack.width() > 200
        assert all(d.toggleViewAction() is not None for d in
                   (win.explorer_dock, win.inspector_dock, win.task_dock))
        for ws in WorkspaceId:
            scroll = win.page_for(ws).findChild(QScrollArea)
            assert scroll is not None
            assert scroll.viewport().width() > 0
            assert scroll.viewport().height() > 0
    finally:
        win.close()
        app.processEvents()
