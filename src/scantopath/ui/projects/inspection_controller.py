"""07.6: explicit, read-only RAW verification in a QThread.

No SQLite import at UI module load; no QModel/QWidget touched by worker.
No camera, capture, migration, algorithms or write operations here.
"""
from __future__ import annotations

from PySide6.QtCore import QObject, QThread, Signal, Slot


class _InspectThread(QThread):
    checked = Signal(object)
    failed = Signal(str)

    def __init__(self, root: str, capture_id: str, parent: QObject | None = None):
        super().__init__(parent)
        self._root = root
        self._capture_id = capture_id

    def run(self) -> None:
        try:
            from scantopath.application.projects import ProjectWorkspaceService
            result = ProjectWorkspaceService(self._root).inspect_capture(self._capture_id)
            self.checked.emit(result)
        except Exception:
            self.failed.emit("Không kiểm tra được bản thu trong kho SQLite đã chọn. Hãy tải lại cây.")


class CaptureInspectionController(QObject):
    checked = Signal(object)
    failed = Signal(str)
    busy_changed = Signal(bool)
    stopped = Signal()

    def __init__(self, parent: QObject | None = None):
        super().__init__(parent)
        self._thread: _InspectThread | None = None
        self._closing = False

    @property
    def busy(self) -> bool:
        return self._thread is not None

    def inspect(self, root: str, capture_id: str) -> bool:
        if not isinstance(root, str) or not root.strip() or not isinstance(capture_id, str) or not capture_id:
            raise ValueError("Root and capture ID are required")
        if self._closing or self.busy:
            return False
        thread = _InspectThread(root, capture_id, self)
        self._thread = thread
        thread.checked.connect(self._on_checked)
        thread.failed.connect(self._on_failed)
        thread.finished.connect(self._on_finished)
        thread.finished.connect(thread.deleteLater)
        self.busy_changed.emit(True)
        thread.start()
        return True

    @Slot(object)
    def _on_checked(self, result) -> None:
        if not self._closing:
            self.checked.emit(result)

    @Slot(str)
    def _on_failed(self, message: str) -> None:
        if not self._closing:
            self.failed.emit(message)

    @Slot()
    def _on_finished(self) -> None:
        self._thread = None
        self.busy_changed.emit(False)
        if self._closing:
            self.stopped.emit()

    def begin_shutdown(self) -> bool:
        self._closing = True
        return not self.busy
