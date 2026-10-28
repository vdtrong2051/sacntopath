"""Qt GUI-thread polling adapter for the headless TaskManager.

No worker emits Qt signals or touches widgets. QTimer and its signals live
only in the GUI thread, including during graceful shutdown.
"""
from __future__ import annotations

import time

from PySide6.QtCore import QObject, QTimer, Signal

from scantopath.application.tasks import TaskContext, TaskManager, TaskQueueFull, TaskManagerClosed


class QtTaskController(QObject):
    snapshots_changed = Signal(object)  # tuple[TaskSnapshot, ...] in GUI thread
    notice = Signal(str)
    stopped = Signal()

    def __init__(self, parent: QObject | None = None, *, manager: TaskManager | None = None) -> None:
        super().__init__(parent)
        self.manager = manager if manager is not None else TaskManager(max_pending=2)
        self.timer = QTimer(self)
        self.timer.setInterval(80)
        self.timer.timeout.connect(self.poll)
        self._last_revision = -1
        self._close_requested = False
        self._close_deadline = 0.0
        self.timer.start()
        self.poll()

    def start_fixture(self) -> str | None:
        """Explicitly labelled, cancellable test task; no stored ProcessingRun."""
        def fixture(context: TaskContext) -> None:
            for step in range(1, 31):
                context.check_cancelled()
                time.sleep(0.06)
                context.report_progress(step * 100.0 / 30)

        try:
            task_id = self.manager.submit("Tác vụ KIỂM THỬ (không lưu)", fixture)
        except (TaskQueueFull, TaskManagerClosed):
            self.notice.emit("Hàng đợi đã đầy hoặc đang đóng; không thể thêm tác vụ.")
            return None
        self.notice.emit("Đã thêm tác vụ KIỂM THỬ vào hàng đợi.")
        self.poll()
        return task_id

    def request_cancel(self, task_id: str) -> bool:
        accepted = self.manager.cancel(task_id)
        self.notice.emit("Đã gửi yêu cầu hủy; đang đợi tác vụ xác nhận." if accepted
                         else "Không thể hủy tác vụ đã kết thúc hoặc không tồn tại.")
        self.poll()
        return accepted

    def begin_shutdown(self, *, grace_seconds: float = 3.0) -> bool:
        """Nonblocking: may require further QTimer polls before close is accepted."""
        self._close_requested = True
        self._close_deadline = time.monotonic() + grace_seconds
        if self.manager.shutdown(timeout=0):
            self.timer.stop()
            return True
        self.notice.emit("Đang yêu cầu dừng tác vụ trước khi đóng ứng dụng…")
        return False

    def poll(self) -> None:
        revision = self.manager.revision
        if revision != self._last_revision:
            self._last_revision = revision
            self.snapshots_changed.emit(self.manager.snapshots())
        if self._close_requested:
            if self.manager.shutdown(timeout=0):
                self._close_requested = False
                self.timer.stop()
                self.stopped.emit()
            elif time.monotonic() >= self._close_deadline:
                self._close_requested = False
                self.notice.emit("Tác vụ chưa dừng. Ứng dụng vẫn mở để tránh mất dữ liệu; hãy thử đóng lại sau.")
