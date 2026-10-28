"""Screen/DPI-aware HMI layout tests: require PySide6 and Qt offscreen.

These tests do NOT replace the manual Windows 14-inch DPI scaling test.
"""
from __future__ import annotations

import os
import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
pytest.importorskip("PySide6")

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QApplication, QScrollArea, QLabel, QDockWidget

from scantopath.application.contracts import WorkspaceId
from scantopath.ui.shell import ScanToPathMainWindow
from scantopath.ui.theme import load_hmi_qss


@pytest.fixture(scope="module")
def app():
    app = QApplication.instance()
    if app is None:
        app = QApplication([])
    yield app


@pytest.fixture
def window(app):
    win = ScanToPathMainWindow()
    win.show()
    app.processEvents()
    yield win
    win.close()
    app.processEvents()


def test_qss_is_external_and_loaded(window):
    assert window.styleSheet() == load_hmi_qss()
    assert window.workspace_toolbar.isVisible()
    assert window.workspace_toolbar.width() > 0


def test_initial_window_bounded_by_available_logical_area(app):
    win = ScanToPathMainWindow()
    try:
        avail = app.primaryScreen().availableGeometry()
        assert win.width() <= avail.width()
        assert win.height() <= avail.height()
        assert win.minimumWidth() <= avail.width()
        assert win.minimumHeight() <= avail.height()
    finally:
        win.close()


@pytest.mark.parametrize("workspace", list(WorkspaceId))
def test_each_workspace_supports_vertical_scrolling(window, workspace):
    page = window.page_for(workspace)
    scroll = page.findChild(QScrollArea, f"workspaceScroll_{workspace.value}")
    assert scroll is not None
    assert scroll.widgetResizable()
    assert scroll.horizontalScrollBarPolicy() == Qt.ScrollBarAlwaysOff
    assert scroll.verticalScrollBarPolicy() == Qt.ScrollBarAsNeeded
    assert page.findChild(QLabel, "workspaceState").text() == ("CÓ THỂ SỬ DỤNG QUA PANEL" if workspace in (WorkspaceId.PROJECTS, WorkspaceId.PROCESSING) else "CHƯA TRIỂN KHAI")


def test_panels_still_accessible_after_compact_resize(window, app):
    window.resize(900, 535)
    app.processEvents()
    window._initialize_dock_layout()
    assert window.workspace_toolbar.isVisible()
    assert window.workspace_toolbar.width() > 0
    assert all(isinstance(d, QDockWidget) for d in
               (window.explorer_dock, window.inspector_dock, window.task_dock))
    assert all(d.toggleViewAction() for d in
               (window.explorer_dock, window.inspector_dock, window.task_dock))
    window.inspector_dock.hide()
    app.processEvents()
    window.inspector_dock.toggleViewAction().trigger()
    app.processEvents()
    assert window.inspector_dock.isVisible()


def test_existing_commands_and_task_demo_still_connected(window, app):
    # No new camera, database, VTK or extra worker needed by QSS.
    window.nav_buttons[WorkspaceId.INSPECT3D].click()
    assert window.active_workspace == WorkspaceId.INSPECT3D
    assert window.task_event_panel.demo_button.text() == "Chạy tác vụ KIỂM THỬ"
    assert window.task_event_panel.cancel_button.text() == "Yêu cầu hủy tác vụ"
    assert not window.task_controller.manager.worker_alive


def test_narrow_page_layout_still_has_content_and_scrollbar(window, app):
    window.resize(820, 500)
    app.processEvents()
    scroll = window.page_for(WorkspaceId.PROJECTS).findChild(QScrollArea)
    assert scroll is not None
    assert scroll.viewport().width() > 0
    assert scroll.widget().layout().count() >= 5
