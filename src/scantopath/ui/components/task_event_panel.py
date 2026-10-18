"""Bảng tác vụ và thông báo UI: hiện dữ liệu được cấp, không thực thi job hay ghi SQLite."""
from __future__ import annotations

from PySide6.QtWidgets import (
    QLabel, QListWidget, QTabWidget, QTreeWidget, QTreeWidgetItem, QVBoxLayout, QWidget,
)

from scantopath.application.contracts import TaskSnapshot, TaskState


_TASK_TITLES = {
    TaskState.QUEUED: "Đang chờ",
    TaskState.RUNNING: "Đang xử lý",
    TaskState.SUCCEEDED: "Hoàn thành",
    TaskState.FAILED: "Thất bại",
    TaskState.CANCELLED: "Đã hủy",
}


class TaskAndEventPanel(QWidget):
    """TaskSnapshot chỉ là trạng thái UI, không phải ProcessingRun trong SQLite."""

    MAX_UI_EVENTS = 200

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("taskAndEventPanel")
        self.setAccessibleName("Tác vụ và thông báo")
        layout = QVBoxLayout(self)
        layout.setContentsMargins(8, 7, 8, 7)
        self.tabs = QTabWidget(self)
        self.tabs.setObjectName("taskEventTabs")
        layout.addWidget(self.tabs)

        tasks_page = QWidget(self.tabs)
        task_layout = QVBoxLayout(tasks_page)
        task_layout.setContentsMargins(6, 8, 6, 6)
        self.task_hint = QLabel("Chưa có tác vụ. Trình chạy và hủy tác vụ sẽ có ở bước 06.5.")
        self.task_hint.setObjectName("taskEmptyLabel")
        self.task_hint.setWordWrap(True)
        task_layout.addWidget(self.task_hint)
        self.tasks = QTreeWidget(tasks_page)
        self.tasks.setObjectName("taskSnapshotTable")
        self.tasks.setHeaderLabels(["Tác vụ", "Trạng thái", "Tiến độ"])
        self.tasks.setRootIsDecorated(False)
        self.tasks.setVisible(False)
        task_layout.addWidget(self.tasks, stretch=1)
        self.tabs.addTab(tasks_page, "Tác vụ")

        events_page = QWidget(self.tabs)
        events_layout = QVBoxLayout(events_page)
        events_layout.setContentsMargins(6, 8, 6, 6)
        self.event_hint = QLabel("Thông báo ở đây chỉ là thao tác giao diện, không phải nhật ký kiểm toán SQLite.")
        self.event_hint.setObjectName("eventSourceNote")
        self.event_hint.setWordWrap(True)
        events_layout.addWidget(self.event_hint)
        self.events = QListWidget(events_page)
        self.events.setObjectName("uiEventList")
        self.events.setAccessibleName("Lịch sử thao tác giao diện trong phiên hiện tại")
        events_layout.addWidget(self.events, stretch=1)
        self.tabs.addTab(events_page, "Thông báo UI")

    def set_tasks(self, snapshots: tuple[TaskSnapshot, ...]) -> None:
        """Cập nhật trạng thái đã cấp; không tự tạo job, tiến độ hoặc kết quả."""
        if not isinstance(snapshots, tuple) or not all(
            isinstance(s, TaskSnapshot) for s in snapshots
        ):
            raise TypeError("snapshots phải là tuple[TaskSnapshot, ...]")
        self.tasks.clear()
        self.task_hint.setVisible(not snapshots)
        self.tasks.setVisible(bool(snapshots))
        for snapshot in snapshots:
            progress = "Không xác định" if snapshot.progress is None else f"{snapshot.progress:g}%"
            item = QTreeWidgetItem(self.tasks, [
                snapshot.title, _TASK_TITLES[snapshot.state], progress,
            ])
            item.setToolTip(0, f"Mã tác vụ: {snapshot.task_id}")
            if snapshot.error is not None:
                item.setToolTip(1, snapshot.error)

    def add_ui_event(self, message: str) -> None:
        """Chỉ lưu thao tác UI trong bộ nhớ của cửa sổ hiện tại."""
        if not isinstance(message, str) or not message.strip():
            raise ValueError("Thông báo UI phải là chuỗi không rỗng")
        self.events.addItem(message)
        while self.events.count() > self.MAX_UI_EVENTS:
            self.events.takeItem(0)
        self.events.scrollToBottom()
