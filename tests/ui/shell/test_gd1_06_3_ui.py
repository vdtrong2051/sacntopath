"""06.3 GUI contract tests. Run with QT_QPA_PLATFORM=offscreen in CI.

PySide6 is optional (project optional dependency 'ui'); without it these
GUI-specific tests skip, while pure Python 06.2 / GĐ0 tests still run.
"""
from __future__ import annotations

import os
from pathlib import Path
import subprocess
import sys

import pytest

# Set only when no platform has been configured by the caller.
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
pytest.importorskip("PySide6")

from PySide6.QtWidgets import QApplication, QMainWindow, QStackedWidget

from scantopath.application.contracts import (
    CommandOutcome, CommandStatus, WorkspaceId,
)
from scantopath.ui.shell import ScanToPathMainWindow
from scantopath.ui.viewmodels.navigation import NavigationViewModel
from scantopath.ui.workspaces import WORKSPACE_PRESENTATION


@pytest.fixture(scope="module")
def qt_app():
    app = QApplication.instance()
    if app is None:
        app = QApplication([])
    yield app


@pytest.fixture
def window(qt_app):
    win = ScanToPathMainWindow()
    yield win
    win.close()
    qt_app.processEvents()


def test_mainwindow_is_single_window_and_four_pages(window):
    assert isinstance(window, QMainWindow)
    assert isinstance(window.workspace_stack, QStackedWidget)
    assert window.workspace_stack.count() == 4
    assert len(window.nav_buttons) == len(window.workspace_actions) == 4
    assert len(WORKSPACE_PRESENTATION) == 4


def test_vietnamese_workspace_titles_are_visible(window):
    assert window.windowTitle().startswith("ScanToPath —")
    expected = ("Dự án", "Thu nhận và phát lại", "Kiểm tra 3D", "Xử lý và kết quả")
    assert tuple(WORKSPACE_PRESENTATION[key].title for key in WorkspaceId) == expected
    for item in WorkspaceId:
        assert window.nav_buttons[item].toolTip() == WORKSPACE_PRESENTATION[item].title
        assert window.page_for(item).accessibleName() == WORKSPACE_PRESENTATION[item].title


def test_default_workspace_projects(window):
    assert window.active_workspace is WorkspaceId.PROJECTS
    assert window.workspace_stack.currentWidget() is window.page_for(WorkspaceId.PROJECTS)
    assert window.nav_buttons[WorkspaceId.PROJECTS].isChecked()
    assert window.workspace_actions[WorkspaceId.PROJECTS].isChecked()
    assert window.status_message.text() == "Không gian hiện tại: Dự án"


@pytest.mark.parametrize("target", list(WorkspaceId))
def test_buttons_navigate_through_viewmodel(window, target):
    window.nav_buttons[target].click()
    assert window.active_workspace is target
    assert window.navigation.last_outcome is not None
    assert window.navigation.last_outcome.status is CommandStatus.SUCCEEDED
    assert window.workspace_stack.currentWidget() is window.page_for(target)
    assert sum(button.isChecked() for button in window.nav_buttons.values()) == 1
    assert sum(action.isChecked() for action in window.workspace_actions.values()) == 1


@pytest.mark.parametrize("target", list(WorkspaceId))
def test_menu_action_uses_same_navigation_state(window, target):
    window.workspace_actions[target].trigger()
    assert window.active_workspace is target
    assert window.nav_buttons[target].isChecked()
    assert window.workspace_stack.currentWidget() is window.page_for(target)


def test_navigation_shortcuts_are_stable(window):
    assert tuple(window.workspace_actions[key].shortcut().toString() for key in WorkspaceId) == (
        "Ctrl+1", "Ctrl+2", "Ctrl+3", "Ctrl+4",
    )


def test_no_real_data_or_fake_measurement_visible(window):
    for key in WorkspaceId:
        page = window.page_for(key)
        state = page.findChild(type(window.status_message), "workspaceState")
        note = page.findChild(type(window.status_message), "workspaceFootnote")
        assert state.text() == ("CÓ THỂ SỬ DỤNG QUA PANEL" if key in (WorkspaceId.PROJECTS, WorkspaceId.PROCESSING) else "CHƯA TRIỂN KHAI")
        assert "Chưa chạy phép đo" in note.text()
        assert ("Mở kho theo yêu cầu" if key in (WorkspaceId.PROJECTS, WorkspaceId.PROCESSING)
                else "Chưa tải dữ liệu") in note.text()


def test_invalid_workspace_does_not_switch_or_crash(window):
    initial = window.active_workspace
    window._navigate("not_a_workspace")
    assert window.active_workspace is initial
    assert window.workspace_stack.currentWidget() is window.page_for(initial)
    assert "Không" in window.status_message.text()


def test_failed_outcome_does_not_update_page(qt_app):
    class RejectedNavigation:
        workspace = WorkspaceId.PROJECTS

        def select_workspace(self, _workspace):
            return CommandOutcome(request_id="failure-01", status=CommandStatus.FAILED,
                                  error_code="SIMULATED_ERROR", message="Lỗi điều hướng giả lập")

    win = ScanToPathMainWindow(navigation=RejectedNavigation())
    try:
        win._navigate(WorkspaceId.INSPECT3D)
        assert win.workspace_stack.currentWidget() is win.page_for(WorkspaceId.PROJECTS)
        assert win.status_message.text() == "Lỗi điều hướng giả lập"
    finally:
        win.close()


def test_viewmodel_dependency_injection(window):
    assert isinstance(window.navigation, NavigationViewModel)
    revision = window.navigation._commands.navigation.current().revision
    window.nav_buttons[WorkspaceId.PROCESSING].click()
    new_revision = window.navigation._commands.navigation.current().revision
    assert new_revision == revision + 1
    window.nav_buttons[WorkspaceId.PROCESSING].click()
    assert window.navigation._commands.navigation.current().revision == new_revision


def test_resizing_and_closing_window_safe(window, qt_app):
    window.show()
    window.resize(1024, 700)
    qt_app.processEvents()
    assert window.width() >= 860
    assert window.height() >= 590
    window.close()
    assert not window.isVisible()


def test_launch_without_real_data_creates_no_capture_or_database(window, tmp_path, monkeypatch, qt_app):
    monkeypatch.chdir(tmp_path)
    win = ScanToPathMainWindow()
    try:
        win.show()
        qt_app.processEvents()
    finally:
        win.close()
    assert not (tmp_path / "scantopath-data").exists()


def test_import_ui_does_not_open_camera_or_load_metadata():
    # Fresh interpreter: importing modules must not create storage or request hardware.
    root = Path(__file__).resolve().parents[3]
    src = root / "src"
    env = os.environ.copy()
    env["PYTHONPATH"] = str(src) + os.pathsep + env.get("PYTHONPATH", "")
    completed = subprocess.run(
        [sys.executable, "-c", "import sys; import scantopath.ui.main; "
         "assert 'scantopath.acquisition.native' not in sys.modules; "
         "assert 'scantopath.metadata.store' not in sys.modules; "
         "print('ui.import_isolation=true')"],
        cwd=root, env=env, capture_output=True, text=True, timeout=20,
        check=False,
    )
    assert completed.returncode == 0, completed.stderr
    assert "ui.import_isolation=true" in completed.stdout
