"""GD2-09.09.4 operational dock regression. Qt only; no camera, SQLite or RAW.

The test exercises real signals/controller adapters without opening the native
SDK or writing to operator's scantopath-data directory.
"""
from __future__ import annotations

import os
from types import SimpleNamespace

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest
pytest.importorskip("PySide6")

from PySide6.QtWidgets import QApplication

from scantopath.application.contracts import WorkspaceId
from scantopath.modules.capture.domain.models import CameraState
from scantopath.ui.shell import ScanToPathMainWindow


@pytest.fixture(scope="module")
def qapp():
    return QApplication.instance() or QApplication([])


@pytest.fixture
def window(qapp):
    win = ScanToPathMainWindow()
    win.resize(1200, 780)
    win.show()
    qapp.processEvents()
    yield win
    win.close()
    qapp.processEvents()


def _latest(panel):
    return panel.operation_table.topLevelItem(panel.operation_table.topLevelItemCount() - 1)


def test_01_dock_starts_compact_and_does_not_create_fake_tasks(window):
    panel = window.task_event_panel
    assert window.workspace_stack.count() == 4
    assert panel.expanded is False
    assert panel.operation_table.objectName() == "operationActivityTable"
    assert panel.operation_table.topLevelItemCount() == 0
    assert panel.tasks.topLevelItemCount() == 0
    assert panel.compact_summary.text() == "Không có tác vụ đang chạy"


def test_02_capture_phase_signals_update_running_state_and_result(window, qapp):
    panel = window.task_event_panel
    window.capture_action.phase_changed.emit("running", "Kiểm tra Project và Session")
    qapp.processEvents()
    assert "Capture: đang xử lý" in panel.compact_summary.text()
    assert _latest(panel).text(1) == "Capture"
    assert _latest(panel).text(2) == "Đang chạy"

    window.capture_action.phase_changed.emit("running", "Ghi RAW / đăng ký SQLite")
    window.capture_action.phase_changed.emit("succeeded", "RAW v2 và SQLite: capture-01")
    qapp.processEvents()
    assert _latest(panel).text(2) == "Hoàn thành"
    assert "capture-01" in _latest(panel).text(3)
    assert panel.tasks.topLevelItemCount() == 0


def test_03_replay_signals_preserve_sqlite_audit_distinction(window, qapp):
    panel = window.task_event_panel
    previous_audit_count = panel.audit_table.topLevelItemCount()
    window.capture_preview.activity_changed.emit("running", "Đang đọc RAW Capture c1")
    window.capture_preview.activity_changed.emit("succeeded", "Replay thành công: c1")
    qapp.processEvents()
    assert _latest(panel).text(1) == "Replay"
    assert _latest(panel).text(2) == "Hoàn thành"
    assert panel.audit_table.topLevelItemCount() == previous_audit_count
    assert panel.tabs.count() == 3  # Existing Task/UI/SQLite tabs unchanged


def test_04_camera_state_is_actual_state_not_fake_progress(window):
    panel = window.task_event_panel
    bridge = window.operation_activity
    bridge._camera_state(CameraState.STREAMING)
    assert "Camera đang truyền RGB-D" in panel.compact_summary.text()
    assert "STREAMING" in _latest(panel).text(3)
    assert "%" not in _latest(panel).text(3)
    bridge._camera_failed("OPEN_FAILED")
    assert "Camera: có lỗi" in panel.compact_summary.text()
    assert _latest(panel).text(2) == "Thất bại"
    bridge._camera_state(CameraState.CLOSED)
    assert _latest(panel).text(2) == "Đã dừng"


def test_05_project_and_integrity_events_have_truthful_status(window):
    panel = window.task_event_panel
    bridge = window.operation_activity
    bridge._project_busy(True)
    bridge._project_loaded(SimpleNamespace(trees=(object(), object())))
    assert _latest(panel).text(1) == "Project"
    assert "2 dự án" in _latest(panel).text(3)

    bridge._raw_check_busy(True)
    bridge._raw_checked(SimpleNamespace(status="verified"))
    assert _latest(panel).text(1) == "RAW Check"
    assert _latest(panel).text(2) == "Hoàn thành"
    bridge._raw_checked(SimpleNamespace(status="corrupt"))
    assert _latest(panel).text(2) == "Thất bại"


def test_06_history_is_bounded_deduplicated_and_does_not_expand(window):
    panel = window.task_event_panel
    assert not panel.expanded
    for i in range(150):
        panel.record_operation("Capture", "running", f"Bước kiểm thử {i}")
    assert panel.operation_table.topLevelItemCount() == panel.MAX_OPERATION_EVENTS
    panel.record_operation("Capture", "running", "Bước kiểm thử 149")
    assert panel.operation_table.topLevelItemCount() == panel.MAX_OPERATION_EVENTS
    assert not panel.expanded
    assert _latest(panel).text(3) == "Bước kiểm thử 149"


def test_07_existing_task_manager_rendering_remains_separate(window):
    panel = window.task_event_panel
    panel.record_operation("Replay", "succeeded", "RAW Replay hoàn tất")
    panel.set_tasks(())
    assert panel.operation_table.topLevelItemCount() == 1
    assert panel.tasks.topLevelItemCount() == 0
    assert panel.operation_table.isHidden() is False


def test_08_expand_collapse_does_not_discard_activity(window, qapp):
    panel = window.task_event_panel
    panel.record_operation("Capture", "failed", "CAPTURE_STORE_FAILED")
    before = panel.operation_table.topLevelItemCount()
    panel.set_expanded(True)
    qapp.processEvents()
    assert panel.expanded
    assert panel.tabs.isVisible()
    assert panel.operation_table.topLevelItemCount() == before
    panel.set_expanded(False)
    assert panel.operation_table.topLevelItemCount() == before
    assert window.capture_workspace_layout.tabs.count() == 2
    assert window.page_for(WorkspaceId.CAPTURE).objectName() == "workspace_capture"


def test_09_invalid_activity_event_is_rejected_without_side_effect(window):
    panel = window.task_event_panel
    with pytest.raises(ValueError):
        panel.record_operation("Capture", "succeeded", "")
    with pytest.raises(ValueError):
        panel.record_operation("NotAController", "running", "hello")
    assert panel.operation_table.topLevelItemCount() == 0
