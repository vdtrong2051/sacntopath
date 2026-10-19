"""Bảng tác vụ và thông báo UI: hiện dữ liệu được cấp, không thực thi job hay ghi SQLite."""
from __future__ import annotations

from PySide6.QtWidgets import (
    QHBoxLayout, QLabel, QListWidget, QPushButton, QTabWidget, QTreeWidget,
    QTreeWidgetItem, QVBoxLayout, QWidget,
)

from PySide6.QtCore import Qt, Signal

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
    demo_requested = Signal()
    cancel_requested = Signal(str)

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("taskAndEventPanel")
        self.setAccessibleName("Tác vụ và thông báo")
        layout = QVBoxLayout(self)
        layout.setContentsMargins(5, 4, 5, 4)
        self.tabs = QTabWidget(self)
        self.tabs.setObjectName("taskEventTabs")
        layout.addWidget(self.tabs)

        tasks_page = QWidget(self.tabs)
        task_layout = QVBoxLayout(tasks_page)
        task_layout.setContentsMargins(5, 5, 5, 4)
        self.task_hint = QLabel("Bước 06.5: Chưa có tác vụ đang hiển thị. Chỉ chạy tác vụ KIỂM THỬ, không ghi vào SQLite.")
        self.task_hint.setObjectName("taskEmptyLabel")
        self.task_hint.setWordWrap(True)
        task_layout.addWidget(self.task_hint)
        buttons = QHBoxLayout()
        buttons.setSpacing(6)
        self.demo_button = QPushButton("Chạy tác vụ KIỂM THỬ")
        self.demo_button.setObjectName("startFixtureTask")
        self.demo_button.clicked.connect(self.demo_requested.emit)
        buttons.addWidget(self.demo_button)
        self.cancel_button = QPushButton("Yêu cầu hủy tác vụ")
        self.cancel_button.setObjectName("cancelSelectedTask")
        self.cancel_button.setEnabled(False)
        self.cancel_button.clicked.connect(self._cancel_selected)
        buttons.addWidget(self.cancel_button)
        task_layout.addLayout(buttons)
        self._snapshots_by_id: dict[str, TaskSnapshot] = {}
        self.tasks = QTreeWidget(tasks_page)
        self.tasks.setObjectName("taskSnapshotTable")
        self.tasks.setHeaderLabels(["Tác vụ", "Trạng thái", "Tiến độ"])
        self.tasks.setRootIsDecorated(False)
        self.tasks.itemSelectionChanged.connect(self._update_cancel_button)
        self.tasks.setVisible(False)
        task_layout.addWidget(self.tasks, stretch=1)
        self.tabs.addTab(tasks_page, "Tác vụ")

        events_page = QWidget(self.tabs)
        events_layout = QVBoxLayout(events_page)
        events_layout.setContentsMargins(5, 5, 5, 4)
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
        selected = self.tasks.currentItem()
        selected_id = selected.data(0, Qt.UserRole) if selected is not None else None
        self._snapshots_by_id = {s.task_id: s for s in snapshots}
        self.tasks.clear()
        self.task_hint.setVisible(not snapshots)
        self.tasks.setVisible(bool(snapshots))
        for snapshot in snapshots:
            progress = "Không xác định" if snapshot.progress is None else f"{snapshot.progress:g}%"
            item = QTreeWidgetItem(self.tasks, [
                snapshot.title, _TASK_TITLES[snapshot.state], progress,
            ])
            item.setData(0, Qt.UserRole, snapshot.task_id)
            item.setToolTip(0, f"Mã tác vụ: {snapshot.task_id}")
            if snapshot.error is not None:
                item.setToolTip(1, snapshot.error)
            if snapshot.task_id == selected_id:
                self.tasks.setCurrentItem(item)
        self._update_cancel_button()

    def _update_cancel_button(self) -> None:
        item = self.tasks.currentItem()
        task_id = item.data(0, Qt.UserRole) if item is not None else None
        snapshot = self._snapshots_by_id.get(task_id)
        self.cancel_button.setEnabled(bool(snapshot and snapshot.can_cancel))

    def _cancel_selected(self) -> None:
        item = self.tasks.currentItem()
        task_id = item.data(0, Qt.UserRole) if item is not None else None
        if task_id is not None and self.cancel_button.isEnabled():
            self.cancel_requested.emit(task_id)

    def add_ui_event(self, message: str) -> None:
        """Chỉ lưu thao tác UI trong bộ nhớ của cửa sổ hiện tại."""
        if not isinstance(message, str) or not message.strip():
            raise ValueError("Thông báo UI phải là chuỗi không rỗng")
        self.events.addItem(message)
        while self.events.count() > self.MAX_UI_EVENTS:
            self.events.takeItem(0)
        self.events.scrollToBottom()
