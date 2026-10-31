
"""GD2-09.04: Capture Preview controller for the existing Qt shell.

No new workspace, dock, Project tree, SQLite client or camera lifecycle.
Application services are provided by the composition root.
"""
from __future__ import annotations

from PySide6.QtCore import QObject, QTimer, Slot, Signal
from PySide6.QtWidgets import QFrame, QWidget

from scantopath.application.contracts import WorkspaceId
from scantopath.modules.capture.application.contracts import CaptureContext

from .preview_widget import CapturePreviewWidget
from .replay_worker import ReplayServiceFactory, ReplayThread


_ERRORS = {
    "CAPTURE_ID_REQUIRED": "Chưa chọn bản thu để phát lại.",
    "CAPTURE_NOT_REGISTERED": "Capture chưa được đăng ký trong SQLite.",
    "CAPTURE_CONTEXT_MISMATCH": "Capture không thuộc Project hoặc Session đã chọn.",
    "UNSUPPORTED_RAW_SCHEMA": "Replay chỉ hỗ trợ RAW v2.",
    "RAW_MISSING": "Không tìm thấy dữ liệu RAW đã đăng ký.",
    "RAW_INTEGRITY_FAILED": "RAW không đạt kiểm tra checksum hoặc cấu trúc.",
    "RAW_PATH_UNSAFE": "Đường dẫn RAW không hợp lệ.",
    "STORAGE_MAPPING_MISSING": "Thiếu ánh xạ Numbered Storage.",
    "STORAGE_MAPPING_MISMATCH": "Ánh xạ Numbered Storage không khớp.",
    "STORE_NOT_OPEN": "Kho dữ liệu không hợp lệ hoặc không truy cập được.",
    "INVALID_MJPEG": "Ảnh JPEG bị hỏng hoặc không thể giải mã.",
    "JPEG_DIMENSION_MISMATCH": "Kích thước JPEG không khớp metadata.",
    "JPEG_LIMIT_EXCEEDED": "JPEG vượt giới hạn hỗ trợ.",
    "UNSUPPORTED_COLOR_ENCODING": "Định dạng màu không được hỗ trợ.",
    "UNSUPPORTED_JPEG_MODE": "Chế độ màu JPEG không được hỗ trợ.",
    "INVALID_RGB_ARRAY": "Dữ liệu RGB giải mã không hợp lệ.",
    "INVALID_Y16": "Dữ liệu Y16 không hợp lệ.",
    "JPEG_DECODER_MISSING": "Chưa cài thư viện giải mã JPEG.",
    "REPLAY_UNEXPECTED_ERROR": "Không thể phát lại RAW. Kiểm tra kho dữ liệu.",
}


class CapturePreviewController(QObject):
    """Controller for offline Capture replay inside the existing workspace."""
    activity_changed = Signal(str, str)  # state, safe context/message

    def __init__(
        self,
        view,
        *,
        service_factory: ReplayServiceFactory,
    ) -> None:
        super().__init__(view)

        if not callable(service_factory):
            raise TypeError("service_factory must be callable")

        self.view = view
        self._service_factory = service_factory

        host = view.page_for(WorkspaceId.CAPTURE).findChild(
            QWidget,
            "workspaceScrollContent",
        )

        if host is None or host.layout() is None:
            raise RuntimeError("Capture workspace host missing")

        legacy = host.findChild(QFrame, "workspacePanel")

        if legacy is None:
            raise RuntimeError("Capture workspacePanel contract missing")

        self.panel = CapturePreviewWidget(host)

        layout = host.layout()
        position = layout.indexOf(legacy)
        layout.insertWidget(position, self.panel)

        # Preserve the GĐ1 workspace identity and placeholder contract.
        legacy.hide()

        self._contexts: dict[str, CaptureContext] = {}
        self._context: CaptureContext | None = None

        self._thread: ReplayThread | None = None
        self._activity_completed = False
        self._request_id = 0
        self._closing = False
        self._handoff = False
        # Latest selection wins. Never queue frame payloads on the GUI thread.
        self._auto_replay_pending = False
        # A completed RAW frame is not the same as an ordinary tree selection.
        self._displayed_context: CaptureContext | None = None
        self._resume_after_reload: CaptureContext | None = None

        self.panel.replay_button.clicked.connect(self.replay)

        view.project_loader.loaded.connect(self._on_store_loaded)
        view.project_loader.failed.connect(self._on_store_failed)
        view.project_loader.busy_changed.connect(self._on_store_busy)

        view.project_writer.busy_changed.connect(self._on_write_busy)

        view.project_explorer.selection_changed.connect(
            self._on_selection
        )

    @property
    def busy(self) -> bool:
        return self._thread is not None

    @property
    def context(self) -> CaptureContext | None:
        return self._context

    def prepare_store_reload(self, requested_root: str) -> None:
        """Called before ProjectRead clears the tree; only replay displayed RAW.

        Reloading the same Store in Capture may restore its previously visible
        frame. Simply switching workspaces or selecting a node never resumes RAW.
        """
        shown = self._displayed_context
        self._resume_after_reload = (
            shown if (
                shown is not None
                and shown == self._context
                and shown.store_root == requested_root
                and self.view.active_workspace is WorkspaceId.CAPTURE
            ) else None
        )

    def begin_navigation_handoff(self) -> None:
        """Preserve explicit context while GĐ1 clears Explorer selection."""
        self._handoff = True

    def end_navigation_handoff(self) -> None:
        self._handoff = False

    def invalidate(self) -> None:
        """Discard stale context and reject previously started results."""
        self._auto_replay_pending = False
        self._displayed_context = None
        self._request_id += 1
        self._contexts.clear()
        self._context = None

        self.panel.set_context(None)
        self.panel.set_busy(self.busy)

    @Slot(bool)
    def _on_store_busy(self, busy: bool) -> None:
        if busy:
            self.invalidate()
        else:
            # Loaded/selection signals may precede QThread.finished.
            QTimer.singleShot(0, self._maybe_auto_replay)

    @Slot(bool)
    def _on_write_busy(self, busy: bool) -> None:
        if busy:
            self.invalidate()

    @Slot(str)
    def _on_store_failed(self, _message: str) -> None:
        self._resume_after_reload = None
        self.invalidate()

    @Slot(object)
    def _on_store_loaded(self, bundle: object) -> None:
        self.invalidate()

        root = bundle.info.root

        for tree in bundle.trees:
            project_id = tree.project.project_id

            for specimen_node in tree.specimens:
                specimen_id = specimen_node.specimen.specimen_id

                for session in specimen_node.sessions:
                    for capture in session.captures:
                        self._contexts[capture.capture_id] = CaptureContext(
                            store_root=root,
                            project_id=project_id,
                            specimen_id=specimen_id,
                            session_id=session.session_id,
                            capture_id=capture.capture_id,
                        )

        # The Project loader may have restored Explorer selection.
        self._on_selection(self.view.project_explorer.selection)
        # Restore the image only when THIS Capture already had a successful
        # display before a same-Store reload. Re-selecting a node does not replay.
        resume = self._resume_after_reload
        self._resume_after_reload = None
        self._auto_replay_pending = (
            resume is not None
            and self._context == resume
            and self.view.active_workspace is WorkspaceId.CAPTURE
        )
        if self._auto_replay_pending:
            QTimer.singleShot(0, self._maybe_auto_replay)

    @Slot(object)
    def _on_selection(self, selection: object) -> None:
        if self._closing:
            return

        if selection is None and self._handoff:
            return

        new_context = None

        if (
            selection is not None
            and getattr(selection, "entity_type", None) == "capture"
        ):
            new_context = self._contexts.get(selection.entity_id)

        if new_context == self._context:
            return

        self._request_id += 1
        self._context = new_context
        self._displayed_context = None

        self.panel.set_context(new_context)
        self.panel.set_busy(self.busy)

        # Preserve 09.04's explicit replay when navigating from Projects.
        # Only a NEW tree selection inside Capture workspace auto-replays.
        self._auto_replay_pending = (
            new_context is not None
            and self.view.active_workspace is WorkspaceId.CAPTURE
        )
        if self._auto_replay_pending:
            QTimer.singleShot(0, self._maybe_auto_replay)

    def request_explicit_replay(self) -> bool:
        """UXH-01.4-R02: explicit user click; coalesce while Replay is busy.

        Called after choosing the RAW tab and entering Capture workspace.
        It does not run for programmatic selection restoration.
        """
        context = self._context
        if (self._closing or context is None or
                self.view.active_workspace is not WorkspaceId.CAPTURE or
                self.view.project_explorer.store_root != context.store_root or
                self.view.project_explorer.selection is None or
                self.view.project_explorer.selection.entity_type != "capture" or
                self.view.project_explorer.selection.entity_id != context.capture_id or
                self.view.project_loader.busy or self.view.project_writer.busy or
                self.view.capture_checker.busy):
            return False
        workflow = getattr(self.view, "workflow_context", None)
        if workflow is not None and (
                workflow.current.actionable_capture_id != context.capture_id or
                workflow.current.store_root != context.store_root):
            return False
        if self._displayed_context == context and not self.busy:
            return True  # Keep the already displayed frame; no duplicate decode.
        self._auto_replay_pending = True
        QTimer.singleShot(0, self._maybe_auto_replay)
        return True

    def _maybe_auto_replay(self) -> None:
        """Queue no second ReplayThread; latest selected Capture wins."""
        if self._auto_replay_pending and self.view.active_workspace is not WorkspaceId.CAPTURE:
            self._auto_replay_pending = False  # Navigation must never replay later.
            return
        if (not self._auto_replay_pending or self._closing
                or self._context is None or self.busy
                or self.view.active_workspace is not WorkspaceId.CAPTURE
                or self.view.project_loader.busy
                or self.view.project_writer.busy
                or self.view.capture_checker.busy):
            return
        self.replay()

    def replay(self) -> bool:
        if (
            self._closing
            or self.busy
            or self._context is None
            or self.view.project_loader.busy
            or self.view.project_writer.busy
            or self.view.capture_checker.busy
        ):
            return False

        context = self._context

        if self.view.project_explorer.store_root != context.store_root:
            self.invalidate()
            return False

        self._auto_replay_pending = False
        self._displayed_context = None
        self._request_id += 1
        request_id = self._request_id

        thread = ReplayThread(
            context,
            request_id,
            service_factory=self._service_factory,
            parent=self,
        )
        self._thread = thread

        thread.loaded.connect(self._on_loaded)
        thread.failed.connect(self._on_failed)
        thread.finished.connect(self._on_finished)
        thread.finished.connect(thread.deleteLater)

        self.panel.set_busy(True)
        self._activity_completed = False
        self.activity_changed.emit("running", "Đang đọc RAW Capture " + context.capture_id)

        self.view.task_event_panel.add_ui_event(
            "Đang phát lại Capture đã chọn."
        )

        thread.start()
        return True

    @Slot(int, object, object)
    def _on_loaded(
        self,
        request_id: int,
        frame: object,
        gray: object,
    ) -> None:
        if self._closing or request_id != self._request_id:
            return

        if (
            self._context is None
            or frame.metadata.capture_id != self._context.capture_id
        ):
            return

        self.panel.show_frame(frame, gray)
        self._displayed_context = self._context
        self._activity_completed = True
        self.activity_changed.emit("succeeded", "Replay thành công: " + frame.metadata.capture_id)

        self.view.task_event_panel.add_ui_event(
            "RAW Replay và RGB-D Decode hoàn thành."
        )

    @Slot(int, str)
    def _on_failed(self, request_id: int, code: str) -> None:
        if self._closing or request_id != self._request_id:
            return

        message = _ERRORS.get(
            code,
            "Không thể phát lại RAW đã chọn.",
        )

        self.panel.show_error(message)
        self._displayed_context = None
        self._activity_completed = True
        self.activity_changed.emit("failed", message)
        self.view.task_event_panel.add_ui_event(message)

    @Slot()
    def _on_finished(self) -> None:
        self._thread = None
        self.panel.set_busy(False)
        if not self._activity_completed and not self._closing:
            self.activity_changed.emit("idle", "Replay cũ đã bị bỏ qua khi đổi lựa chọn")

        if not self._closing and self._auto_replay_pending:
            QTimer.singleShot(0, self._maybe_auto_replay)

        if self._closing:
            QTimer.singleShot(0, self.view.close)

    def begin_shutdown(self) -> bool:
        """Do not destroy or terminate an active Replay QThread."""
        self._closing = True
        self._auto_replay_pending = False
        self._request_id += 1
        return not self.busy
