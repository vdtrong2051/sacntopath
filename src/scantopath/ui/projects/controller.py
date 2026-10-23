"""07.4: explicit store-loading QThread; only queued signals reach GUI widgets.

Never allocate codes, migrate SQLite, read RAW payloads, or open hardware.
Worker threads only create short-lived application services and plain DTOs.
"""
from __future__ import annotations

from PySide6.QtCore import QObject, QThread, Signal, Slot

def _make_project_service(root: str):
    # Import the persistence layer only inside the explicitly started worker.
    # UI module imports must preserve GĐ1-06.3 import isolation.
    from scantopath.application.projects import ProjectWorkspaceService
    return ProjectWorkspaceService(root)


class _LoadThread(QThread):
    loaded = Signal(object)
    load_failed = Signal(str)

    def __init__(self, root: str, parent: QObject | None = None) -> None:
        super().__init__(parent)
        self._root = root

    def run(self) -> None:
        try:
            from .presentation import ProjectLoadBundle
            service = _make_project_service(self._root)
            projects = service.list_projects()
            trees = tuple(service.get_project_tree(p.project_id) for p in projects)
            self.loaded.emit(ProjectLoadBundle(service.info, trees))
        except Exception as exc:
            # Sanitize: never expose raw exception text (path, DB contents, etc.).
            name = type(exc).__name__
            if name == "StoreNotOpenError":
                message = "Không tìm thấy kho dữ liệu SQLite hợp lệ trong thư mục đã chọn."
            elif name in ("PermissionError", "OperationalError", "DatabaseError"):
                message = "Không thể đọc cơ sở dữ liệu. Kiểm tra quyền truy cập và tình trạng SQLite."
            elif name in ("RuntimeError", "ValueError"):
                message = "Phiên bản hoặc cấu trúc kho dữ liệu không được hỗ trợ."
            else:
                message = "Không tải được kho dữ liệu. Không có dữ liệu nào được thay đổi."
            self.load_failed.emit(message)


class ProjectLoadController(QObject):
    loaded = Signal(object)
    failed = Signal(str)
    busy_changed = Signal(bool)
    stopped = Signal()

    def __init__(self, parent: QObject | None = None) -> None:
        super().__init__(parent)
        self._thread: _LoadThread | None = None
        self._closing = False

    @property
    def busy(self) -> bool:
        return self._thread is not None

    def load(self, root: str) -> bool:
        if not isinstance(root, str) or not root.strip():
            raise ValueError("Choose a nonempty store path")
        if self._closing or self.busy:
            return False
        thread = _LoadThread(root, self)
        self._thread = thread
        thread.loaded.connect(self._on_loaded)
        thread.load_failed.connect(self._on_failed)
        thread.finished.connect(self._on_finished)
        thread.finished.connect(thread.deleteLater)
        self.busy_changed.emit(True)
        thread.start()
        return True

    @Slot(object)
    def _on_loaded(self, bundle: object) -> None:
        if not self._closing:
            self.loaded.emit(bundle)

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
        """Nonblocking: never destroy a running QThread or terminate it abruptly."""
        self._closing = True
        return not self.busy
