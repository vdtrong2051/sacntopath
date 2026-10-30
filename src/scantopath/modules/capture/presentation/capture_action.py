"""GD2-09.09.1: selected open Session -> live camera -> RAW v2 commit.

No SDK/SQLite imports in presentation. Preflight and persistence work in a
QThread; Qt GUI only owns selection, state, and camera worker requests.
"""
from __future__ import annotations

from collections.abc import Callable
from PySide6.QtCore import QObject, QThread, Signal, Slot

from scantopath.application.contracts import SelectionRef
from scantopath.modules.capture.application.contracts import CaptureContext
from scantopath.modules.capture.domain.models import CameraState
from scantopath.acquisition.raw_rgbd import RawRgbdCapture


class _StoreActionThread(QThread):
    succeeded = Signal(object)
    failed = Signal(str)

    def __init__(self, *, operation: str, context: CaptureContext,
                 store_factory: Callable, raw: RawRgbdCapture | None = None, parent=None):
        super().__init__(parent)
        self.operation = operation
        self.context = context
        self.store_factory = store_factory
        self.raw = raw

    def run(self) -> None:
        try:
            adapter = self.store_factory()
            if self.operation == "preflight":
                adapter.validate_context(self.context)
                self.succeeded.emit(None)
            else:
                from scantopath.modules.capture.application.capture_service import CaptureCommitService
                receipt_id = CaptureCommitService(adapter).commit(self.context, self.raw)
                self.succeeded.emit(receipt_id)
        except Exception as exc:
            code = getattr(exc, "code", "CAPTURE_STORE_FAILED")
            if not isinstance(code, str) or not code.isascii() or not code.replace("_", "").isalnum():
                code = "CAPTURE_STORE_FAILED"
            self.failed.emit(code)


class CaptureActionCoordinator(QObject):
    """MainWindow-owned feature controller. Never opens another camera source."""
    finished = Signal(str)
    failed = Signal(str)
    stopped = Signal()

    def __init__(self, view, *, store_factory: Callable) -> None:
        super().__init__(view)
        self.view = view
        self._factory = store_factory
        self._thread: _StoreActionThread | None = None
        self._phase = "idle"
        self._context: CaptureContext | None = None
        self._closing = False
        self._last_indices: tuple[int, int] | None = None
        self._seen_ids: set[str] = set()
        self._pending_raw: RawRgbdCapture | None = None
        self.panel = view.capture_live.panel
        self.camera = view.capture_live.camera
        self.panel.capture_button.clicked.connect(self.capture)
        self.camera.keyframe_ready.connect(self._on_keyframe)
        self.camera.keyframe_failed.connect(self._on_keyframe_failed)
        self.camera.state_changed.connect(self._on_camera_state)
        view.project_explorer.selection_changed.connect(self._refresh)
        view.project_loader.busy_changed.connect(self._refresh)
        view.project_writer.busy_changed.connect(self._refresh)
        self._refresh()

    @property
    def busy(self) -> bool:
        return self._phase != "idle" or self._thread is not None

    def _selected_context(self) -> CaptureContext | None:
        project = self.view.project_workspace
        selection = self.view.project_explorer.selection
        if selection is None or selection.entity_type != "scan_session":
            return None
        if project._project_root is None or project._project_schema != 2:
            return None
        entity = project._project_entities.get(selection)
        if entity is None or entity.state != "open":
            return None
        specimen_id = project._project_owners.get(selection)
        if not specimen_id:
            return None
        project_id = project._project_owners.get(SelectionRef("specimen", specimen_id))
        if not project_id:
            return None
        return CaptureContext(project._project_root, project_id, specimen_id, selection.entity_id)

    @Slot()
    def _refresh(self, *_args) -> None:
        selected = self._selected_context()
        project = self.view.project_workspace
        ready = (not self._closing and self._phase == "idle" and self._thread is None
                 and not project.project_loader.busy and not project.project_writer.busy
                 and self.camera.state is CameraState.STREAMING and selected is not None)
        self.panel.capture_button.setEnabled(ready)
        if self._phase == "idle":
            self.panel.capture_context_label.setText(
                "Phiên đang chọn: " + selected.session_id if selected is not None
                else "Chọn một phiên quét đang mở trong Cây dự án để chụp và lưu."
            )

    def _notice(self, text: str) -> None:
        self.view.task_event_panel.add_ui_event(text)
        self.view._set_status(text)

    @Slot()
    def capture(self) -> bool:
        if self.busy or self._closing or self.camera.state is not CameraState.STREAMING:
            return False
        context = self._selected_context()
        if context is None or self.view.project_writer.busy or self.view.project_loader.busy:
            self._notice("Không thể chụp: chọn kho SQLite v2 và phiên quét đang mở.")
            return False
        self._context = context
        self._phase = "preflight"
        self._notice("Đang kiểm tra Project/Session trước khi chụp…")
        self._refresh()
        self._start_storage("preflight", context)
        return True

    def _start_storage(self, operation: str, context: CaptureContext,
                       raw: RawRgbdCapture | None = None) -> None:
        if self._thread is not None:
            raise RuntimeError("CAPTURE_STORAGE_THREAD_BUSY")
        worker = _StoreActionThread(operation=operation, context=context,
                                    store_factory=self._factory, raw=raw, parent=self)
        self._thread = worker
        worker.succeeded.connect(self._on_storage_success)
        worker.failed.connect(self._on_storage_failure)
        worker.finished.connect(self._on_storage_finished)
        worker.finished.connect(worker.deleteLater)
        worker.start()

    @Slot(object)
    def _on_storage_success(self, result) -> None:
        if self._closing:
            return
        if self._phase == "preflight":
            ctx = self._context
            if ctx is None or self._selected_context() != ctx or self.camera.state is not CameraState.STREAMING:
                self._fail("CAPTURE_CONTEXT_CHANGED")
                return
            if not self.camera.capture_keyframe(session_id=ctx.session_id, specimen_id=ctx.specimen_id):
                self._fail("CAPTURE_REQUEST_REJECTED")
                return
            self._phase = "capture"
            self._notice("Gemini 2: đang chụp keyframe RGB-D…")
        elif self._phase == "commit":
            capture_id = result
            self._notice("RAW v2 đã lưu và xác minh: " + capture_id)
            self.finished.emit(capture_id)
            self._phase = "idle"
            self._context = None
            # Existing reader refresh will insert Capture in Explorer. Replay is 09.09.2.
            self.view.project_workspace._pending_selection = SelectionRef("capture", capture_id)
            self.view.project_workspace._reload_project_store()
        self._refresh()

    @Slot(str)
    def _on_storage_failure(self, code: str) -> None:
        if not self._closing:
            self._fail(code)

    @Slot()
    def _on_storage_finished(self) -> None:
        self._thread = None
        if self._closing:
            self._pending_raw = None
            self.stopped.emit()
            return
        if self._phase == "commit" and self._pending_raw is not None:
            raw = self._pending_raw
            self._pending_raw = None
            self._start_storage("commit", self._context, raw)
        self._refresh()

    @Slot(object)
    def _on_keyframe(self, raw: object) -> None:
        if self._closing or self._phase != "capture":
            return
        ctx = self._context
        if ctx is None or not isinstance(raw, RawRgbdCapture):
            self._fail("INVALID_KEYFRAME")
            return
        meta = raw.metadata
        indices = (meta.color.frame_index, meta.depth.frame_index)
        if (meta.session_id != ctx.session_id or meta.specimen_id != ctx.specimen_id
                or meta.camera_pose is not None or meta.alignment_mode != "disabled"
                or meta.capture_id in self._seen_ids or
                (self._last_indices is not None and
                 (indices[0] <= self._last_indices[0] or indices[1] <= self._last_indices[1]))):
            self._fail("STALE_OR_INVALID_KEYFRAME")
            return
        self._seen_ids.add(meta.capture_id)
        self._last_indices = indices
        self._phase = "commit"
        self._notice("Đang ghi RAW v2 / đăng ký SQLite / xác minh Replay…")
        if self._thread is None:
            self._start_storage("commit", ctx, raw)
        else:
            # Qt can deliver a keyframe before preflight QThread.finished.
            self._pending_raw = raw
        self._refresh()

    @Slot(str)
    def _on_keyframe_failed(self, code: str) -> None:
        if not self._closing and self._phase == "capture":
            self._fail(code)

    @Slot(object)
    def _on_camera_state(self, state) -> None:
        if state in (CameraState.CLOSED, CameraState.FAILED, CameraState.STOPPING):
            if self._phase == "capture":
                self._fail("CAMERA_STOPPED_DURING_CAPTURE")
            if state is CameraState.CLOSED:
                self._last_indices = None
                self._seen_ids.clear()
        self._refresh()

    def _fail(self, code: str) -> None:
        self._phase = "idle"
        self._context = None
        self._pending_raw = None
        self._notice("Chụp/lưu chưa hoàn tất: " + code)
        self.failed.emit(code)
        self._refresh()

    def begin_shutdown(self) -> bool:
        self._closing = True
        self._refresh()
        return self._thread is None
