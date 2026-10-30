"""Explicit, nonblocking bootstrap of scantopath-data through the Project UI."""
from __future__ import annotations

from pathlib import Path
from PySide6.QtCore import QObject, QThread, Signal, Slot


def default_dev_store() -> Path:
    # src/scantopath/ui/projects/init_controller.py -> repository root
    return Path(__file__).resolve().parents[4] / "scantopath-data"


class _InitThread(QThread):
    completed = Signal(str)
    failed = Signal(str)

    def __init__(self, target: Path, parent=None):
        super().__init__(parent)
        self._target = target

    def run(self) -> None:
        try:
            from scantopath.modules.project_workspace.infrastructure.store_bootstrap import (
                initialize_empty_data_workspace,
            )
            root = initialize_empty_data_workspace(self._target)
            self.completed.emit(str(root))
        except Exception as exc:
            # Do not display absolute paths, SQL or source details to operators.
            message = {
                "STORE_DIRECTORY_NOT_EMPTY": "Thư mục có dữ liệu nhưng chưa có SQLite: từ chối ghi đè.",
                "ONLY_SCANTOPATH_DATA_ALLOWED": "Chỉ khởi tạo kho scantopath-data.",
            }.get(str(exc), "Không thể khởi tạo kho. Kiểm tra quyền ghi và trạng thái SQLite v2.")
            self.failed.emit(message)


class StoreInitController(QObject):
    completed = Signal(str)
    failed = Signal(str)
    busy_changed = Signal(bool)
    stopped = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self._thread: _InitThread | None = None
        self._closing = False

    @property
    def busy(self) -> bool:
        return self._thread is not None

    def initialize_default(self) -> bool:
        if self._closing or self.busy:
            return False
        thread = _InitThread(default_dev_store(), self)
        self._thread = thread
        thread.completed.connect(self._complete)
        thread.failed.connect(self._failed)
        thread.finished.connect(self._finished)
        thread.finished.connect(thread.deleteLater)
        self.busy_changed.emit(True)
        thread.start()
        return True

    @Slot(str)
    def _complete(self, root):
        if not self._closing:
            self.completed.emit(root)

    @Slot(str)
    def _failed(self, message):
        if not self._closing:
            self.failed.emit(message)

    @Slot()
    def _finished(self):
        self._thread = None
        self.busy_changed.emit(False)
        if self._closing:
            self.stopped.emit()

    def begin_shutdown(self) -> bool:
        self._closing = True
        return not self.busy
