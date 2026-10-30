"""GD2-09.09.4 — GUI-only operational activity bridge.

Observes actual controller signals and forwards transitions to the existing
TaskAndEventPanel. Does not launch work, poll files, fabricate percentages,
query SQLite or control the Gemini 2 native process.
"""
from __future__ import annotations

from PySide6.QtCore import QObject

from scantopath.modules.capture.domain.models import CameraState


class OperationActivityBridge(QObject):
    """Record real operations without confusing them with TaskManager jobs."""

    def __init__(self, view) -> None:
        super().__init__(view)
        self._view = view
        self._panel = view.task_event_panel

        view.project_loader.busy_changed.connect(self._project_busy)
        view.project_loader.loaded.connect(self._project_loaded)
        view.project_loader.failed.connect(self._project_failed)
        view.project_writer.busy_changed.connect(self._writer_busy)
        view.project_writer.completed.connect(self._project_written)
        view.project_writer.failed.connect(self._project_failed)

        view.capture_live.camera.state_changed.connect(self._camera_state)
        view.capture_live.camera.failure.connect(self._camera_failed)
        view.capture_action.phase_changed.connect(self._capture_phase)
        view.capture_preview.activity_changed.connect(self._replay_phase)

        view.capture_checker.busy_changed.connect(self._raw_check_busy)
        view.capture_checker.checked.connect(self._raw_checked)
        view.capture_checker.failed.connect(self._raw_check_failed)

    def _record(self, source: str, state: str, detail: str) -> None:
        self._panel.record_operation(source, state, detail)

    def _project_busy(self, busy: bool) -> None:
        if busy:
            self._record("Project", "running", "Đang tải kho và cây dự án")

    def _project_loaded(self, bundle) -> None:
        self._record("Project", "succeeded", f"Đã tải {len(bundle.trees)} dự án từ SQLite")

    def _project_failed(self, reason: str) -> None:
        self._record("Project", "failed", reason)

    def _writer_busy(self, busy: bool) -> None:
        if busy:
            self._record("Project", "running", "Đang ghi metadata dự án")

    def _project_written(self, result) -> None:
        action = getattr(result, "action", "update")
        pending = bool(getattr(result, "numbering_pending", False))
        if pending:
            self._record("Project", "failed", "Đã ghi metadata nhưng cần khôi phục cấp mã")
        else:
            code = getattr(result, "public_code", None) or getattr(result, "entity_id", "")
            label = f" · {code}" if code else ""
            self._record("Project", "succeeded", f"Metadata: {action}{label}")

    def _camera_state(self, state: CameraState) -> None:
        if state in (CameraState.OPENING, CameraState.STREAMING,
                     CameraState.CAPTURING, CameraState.STOPPING):
            self._record("Camera", "running", f"Gemini 2: {state.value.upper()}")
        elif state is CameraState.FAILED:
            error = self._view.capture_live.camera.error_code or "CAMERA_FAILED"
            self._record("Camera", "failed", error)
        elif state in (CameraState.IDLE, CameraState.CLOSED):
            # IDLE is normally never emitted during widget construction.
            self._record("Camera", "idle", f"Gemini 2: {state.value.upper()}")

    def _camera_failed(self, code: str) -> None:
        self._record("Camera", "failed", code)

    def _capture_phase(self, state: str, detail: str) -> None:
        self._record("Capture", state, detail)

    def _replay_phase(self, state: str, detail: str) -> None:
        self._record("Replay", state, detail)

    def _raw_check_busy(self, busy: bool) -> None:
        if busy:
            self._record("RAW Check", "running", "Kiểm tra cấu trúc và checksum RAW")

    def _raw_checked(self, result) -> None:
        status = str(getattr(result, "status", "unknown"))
        state = "succeeded" if status == "verified" else "failed"
        self._record("RAW Check", state, f"Capture RAW: {status}")

    def _raw_check_failed(self, message: str) -> None:
        self._record("RAW Check", "failed", message)
