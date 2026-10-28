"""06.6 Qt integration. Must run on Windows with real PySide6 and offscreen QPA.

The Windows verification script requires PySide6 before running. For optional
headless developer environments this test module may skip, not break imports.
"""
from __future__ import annotations

import os
import time

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
import pytest
pytest.importorskip("PySide6")
from PySide6.QtCore import Qt
from PySide6.QtWidgets import QApplication, QDockWidget, QScrollArea

from scantopath.application.contracts import SelectionRef, TaskState, WorkspaceId
from scantopath.ui.components import ExplorerNode
from scantopath.ui.shell import ScanToPathMainWindow
from scantopath.ui.theme import load_hmi_qss
from scantopath.ui.workspaces import WORKSPACE_PRESENTATION


@pytest.fixture(scope="module")
def app():
    existing = QApplication.instance()
    qapp = existing or QApplication([])
    yield qapp


def until(app, condition, timeout=4.0):
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        app.processEvents()
        if condition():
            return
        time.sleep(0.008)
    raise AssertionError("Qt event condition exceeded allowed timeout")


@pytest.fixture
def window(app):
    win = ScanToPathMainWindow()
    win.show()
    app.processEvents()
    yield win
    if win.isVisible():
        win.close()
    until(app, lambda: not win.task_controller.manager.worker_alive)
    if win.isVisible():
        win.close()
    app.processEvents()


def test_window_qss_and_vietnamese_menu(window):
    assert window.styleSheet() == load_hmi_qss()
    menu_names = {a.text().replace("&", "") for a in window.menuBar().actions()}
    assert {"Tệp", "Không gian làm việc", "Hiển thị", "Trợ giúp"} <= menu_names
    assert window.windowTitle().startswith("ScanToPath")


def test_four_workspaces_are_only_navigable_pages(window):
    assert window.workspace_stack.count() == 4
    assert len(window.nav_buttons) == len(window.workspace_actions) == 4
    assert window.active_workspace == WorkspaceId.PROJECTS
    for workspace in WorkspaceId:
        window.nav_buttons[workspace].click()
        assert window.active_workspace is workspace
        assert window.workspace_stack.currentWidget() is window.page_for(workspace)
        assert window.nav_buttons[workspace].toolTip() == WORKSPACE_PRESENTATION[workspace].title


def test_no_fake_geometry_or_results(window):
    for w in WorkspaceId:
        page = window.page_for(w)
        state = page.findChild(type(window.status_message), "workspaceState")
        assert state is not None
        assert state.text() == ("CÓ THỂ SỬ DỤNG QUA PANEL" if w in (WorkspaceId.PROJECTS, WorkspaceId.PROCESSING) else "CHƯA TRIỂN KHAI")
    assert window.project_explorer.tree.topLevelItemCount() == 0
    assert window.property_inspector.selection is None
    assert window.task_event_panel.tasks.topLevelItemCount() == 0


def test_data_selection_flows_explorer_to_viewmodel_to_inspector(window):
    selection = SelectionRef("specimen", "specimen-acceptance", "fixture-source")
    nodes = (ExplorerNode("Vật mẫu (KIỂM THỬ)", selection),)
    window.project_explorer.set_nodes(nodes)
    window.project_explorer.tree.setCurrentItem(window.project_explorer.tree.topLevelItem(0))
    assert window.navigation.selection == selection
    assert window.property_inspector.selection == selection
    window.nav_buttons[WorkspaceId.CAPTURE].click()
    assert window.navigation.selection is None
    assert window.property_inspector.selection is None
    assert window.project_explorer.tree.topLevelItemCount() == 1


def test_three_docks_remain_reopenable(window, app):
    for dock in (window.explorer_dock, window.inspector_dock, window.task_dock):
        assert isinstance(dock, QDockWidget)
        dock.show()
        app.processEvents()
        dock.toggleViewAction().trigger()
        app.processEvents()
        assert not dock.isVisible()
        dock.toggleViewAction().trigger()
        app.processEvents()
        assert dock.isVisible()


@pytest.mark.parametrize("logical_size", [(1366, 768), (1120, 630), (850, 520)])
def test_workspace_compact_sizes_scroll_and_no_zero_viewport(window, app, logical_size):
    # Qt offscreen uses synthetic screen. This tests responsive layout only,
    # NOT a physical 14-inch laptop or its Windows scaling settings.
    window.resize(*logical_size)
    app.processEvents()
    window._initialize_dock_layout()
    app.processEvents()
    for w in WorkspaceId:
        scroll = window.page_for(w).findChild(QScrollArea, f"workspaceScroll_{w.value}")
        assert scroll is not None
        assert scroll.widgetResizable()
        assert scroll.horizontalScrollBarPolicy() == Qt.ScrollBarAlwaysOff
        assert scroll.viewport().width() > 0
        assert scroll.viewport().height() > 0


def test_fixture_job_updates_ui_without_blocking_workspace(window, app):
    window.task_event_panel.demo_button.click()
    until(app, lambda: window.task_controller.manager.worker_alive)
    window.nav_buttons[WorkspaceId.INSPECT3D].click()
    assert window.active_workspace == WorkspaceId.INSPECT3D
    until(app, lambda: window.task_controller.manager.snapshots()[0].state is TaskState.SUCCEEDED)
    until(app, lambda: window.task_event_panel.tasks.topLevelItemCount() == 1 and
          window.task_event_panel.tasks.topLevelItem(0).text(1) == "Hoàn thành")
    assert window.task_event_panel.tasks.topLevelItem(0).text(2) == "100%"


def test_cancel_fixture_job_from_panel(window, app):
    window.task_event_panel.demo_button.click()
    until(app, lambda: window.task_event_panel.tasks.topLevelItemCount() == 1)
    window.task_event_panel.tasks.setCurrentItem(window.task_event_panel.tasks.topLevelItem(0))
    until(app, lambda: window.task_event_panel.cancel_button.isEnabled())
    window.task_event_panel.cancel_button.click()
    until(app, lambda: window.task_controller.manager.snapshots()[0].state is TaskState.CANCELLED)
    until(app, lambda: window.task_event_panel.tasks.topLevelItem(0).text(1) == "Đã hủy")


def test_close_while_job_active_is_nonblocking(window, app):
    window.task_event_panel.demo_button.click()
    until(app, lambda: window.task_controller.manager.worker_alive)
    start = time.monotonic()
    window.close()
    assert time.monotonic() - start < 0.5
    until(app, lambda: not window.task_controller.manager.worker_alive, timeout=4.0)
    until(app, lambda: not window.isVisible())


def test_hmi_launch_does_not_create_default_project_database(window, app, tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    win = ScanToPathMainWindow()
    try:
        win.show()
        app.processEvents()
        assert not (tmp_path / "scantopath-data").exists()
        assert not win.task_controller.manager.worker_alive
    finally:
        win.close()
        app.processEvents()
