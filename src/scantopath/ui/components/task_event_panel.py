"""Bảng tác vụ và thông báo UI: hiện dữ liệu được cấp, không thực thi job hay ghi SQLite."""
from __future__ import annotations

from PySide6.QtWidgets import (
    QBoxLayout, QHBoxLayout, QLabel, QListWidget, QPushButton, QTabWidget, QTreeWidget,
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
    expanded_changed = Signal(bool)
    summary_changed = Signal(str)

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("taskAndEventPanel")
        self.setAccessibleName("Tác vụ và thông báo")
        layout = QVBoxLayout(self)
        layout.setContentsMargins(8, 7, 8, 9)
        layout.setSpacing(4)
        # Compact summary stays visible while heavy task/audit pages are collapsed.
        # The legacy tabs and test worker remain constructed for Qt compatibility.
        self._expanded = True
        self._demo_tools_visible = True
        header = QHBoxLayout()
        header.setContentsMargins(1, 0, 1, 0)
        header.setSpacing(8)
        self.compact_summary = QLabel("Không có tác vụ đang chạy", self)
        self.compact_summary.setObjectName("taskCompactSummary")
        self.compact_summary.setToolTip("Trạng thái tác vụ trong phiên ứng dụng, không phải ProcessingRun SQLite")
        header.addWidget(self.compact_summary, stretch=1)
        self.expand_button = QPushButton("Thu gọn ▾", self)
        self.expand_button.setObjectName("taskPanelExpandToggle")
        self.expand_button.setAccessibleName("Thu gọn hoặc mở rộng bảng tác vụ")
        self.expand_button.clicked.connect(self._toggle_expanded)
        header.addWidget(self.expand_button)
        self.compact_header = header
        layout.addLayout(header)
        self.tabs = QTabWidget(self)
        self.tabs.setObjectName("taskEventTabs")
        layout.addWidget(self.tabs)

        tasks_page = QWidget(self.tabs)
        task_layout = QVBoxLayout(tasks_page)
        task_layout.setContentsMargins(8, 8, 8, 8)
        task_layout.setSpacing(8)
        self.task_hint = QLabel("Bước 06.5: Chưa có tác vụ đang hiển thị. Chỉ chạy tác vụ KIỂM THỬ, không ghi vào SQLite.")
        self.task_hint.setObjectName("taskEmptyLabel")
        self.task_hint.setWordWrap(True)
        task_layout.addWidget(self.task_hint)
        self.task_empty = QLabel("Chưa có tác vụ. Tiến trình sẽ xuất hiện tại đây khi có công việc.", tasks_page)
        self.task_empty.setObjectName("taskOperatorEmpty")
        self.task_empty.setWordWrap(False)
        self.task_empty.hide()
        task_layout.addWidget(self.task_empty)
        # Start with the compact layout BEFORE Qt computes minimumSizeHint().
        # Starting horizontal can force a wide minimum width (the two buttons
        # combined) and clamp an attempted resize(390, ...) above the 460 px
        # breakpoint. resizeEvent still switches to horizontal on wider docks.
        buttons = QBoxLayout(QBoxLayout.TopToBottom)
        buttons.setSpacing(9)
        self.action_buttons_layout = buttons
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
        events_layout.setContentsMargins(8, 8, 8, 8)
        self.event_hint = QLabel("Thông báo ở đây chỉ là thao tác giao diện, không phải nhật ký kiểm toán SQLite.")
        self.event_hint.setObjectName("eventSourceNote")
        self.event_hint.setWordWrap(True)
        events_layout.addWidget(self.event_hint)
        self.events = QListWidget(events_page)
        self.events.setObjectName("uiEventList")
        self.events.setAccessibleName("Lịch sử thao tác giao diện trong phiên hiện tại")
        events_layout.addWidget(self.events, stretch=1)
        self.tabs.addTab(events_page, "Thông báo UI")

        audit_page = QWidget(self.tabs)
        audit_layout = QVBoxLayout(audit_page)
        audit_layout.setContentsMargins(8, 8, 8, 8)
        self.audit_hint = QLabel("Chỉ đọc 100 sự kiện SQLite gần nhất của kho đã mở; không phải tác vụ UI.")
        self.audit_hint.setWordWrap(True)
        audit_layout.addWidget(self.audit_hint)
        self.audit_table = QTreeWidget(audit_page)
        self.audit_table.setObjectName("sqliteAuditTimeline")
        self.audit_table.setHeaderLabels(["Thời gian (UTC)", "Mức", "Sự kiện", "Đối tượng"])
        # Keep the full UTC header and common ISO-8601 timestamps readable.
        # QHeaderView remains interactive, so operators can still drag the column.
        self.audit_table.setColumnWidth(0, 240)
        self.audit_table.setRootIsDecorated(False)
        audit_layout.addWidget(self.audit_table, stretch=1)
        self.tabs.addTab(audit_page, "Nhật ký SQLite")

    @property
    def expanded(self) -> bool:
        return self._expanded

    def _toggle_expanded(self) -> None:
        self.set_expanded(not self._expanded)

    def set_expanded(self, expanded: bool) -> None:
        """Collapse presentation only. Keep tasks, events and audit data intact."""
        if not isinstance(expanded, bool):
            raise TypeError("expanded phải là bool")
        if self._expanded == expanded:
            return
        self._expanded = expanded
        self.tabs.setVisible(expanded)
        self.expand_button.setText("Thu gọn ▾" if expanded else "Mở rộng ▴")
        self.expanded_changed.emit(expanded)

    def set_demo_tools_visible(self, visible: bool) -> None:
        """Keep 06.5 test hooks but hide fixture controls in operator mode."""
        if not isinstance(visible, bool):
            raise TypeError("visible phải là bool")
        self._demo_tools_visible = visible
        self.demo_button.setVisible(visible)
        self.task_hint.setVisible(visible and not self._snapshots_by_id)
        self.task_empty.setVisible(not visible and not self._snapshots_by_id)
        self.cancel_button.setVisible(visible or bool(self._snapshots_by_id))
        self.cancel_button.setMaximumWidth(16777215 if visible else 190)

    def _update_compact_summary(self, snapshots: tuple[TaskSnapshot, ...]) -> None:
        active = sum(s.state in (TaskState.QUEUED, TaskState.RUNNING) for s in snapshots)
        failed = sum(s.state == TaskState.FAILED for s in snapshots)
        if active:
            message = f"{active} tác vụ đang chờ/xử lý"
        elif failed:
            message = f"{failed} tác vụ thất bại · Mở bảng để xem"
        elif snapshots:
            message = f"{len(snapshots)} tác vụ đã ghi nhận"
        else:
            message = "Không có tác vụ đang chạy"
        self.compact_summary.setText(message)
        self.summary_changed.emit(message)

    def resizeEvent(self, event) -> None:
        """Stack task buttons when the dock is floated or narrowed.

        This preserves their complete Vietnamese labels without introducing
        a minimum window width or a horizontal scrollbar for the entire dock.
        """
        direction = (QBoxLayout.TopToBottom if self.width() < 460
                     else QBoxLayout.LeftToRight)
        if self.action_buttons_layout.direction() != direction:
            self.action_buttons_layout.setDirection(direction)
        super().resizeEvent(event)

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
        self.task_hint.setVisible(self._demo_tools_visible and not snapshots)
        self.task_empty.setVisible(not self._demo_tools_visible and not snapshots)
        self.cancel_button.setVisible(self._demo_tools_visible or bool(snapshots))
        self._update_compact_summary(snapshots)
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

    def set_audit_events(self, events: tuple) -> None:
        """Read-only immutable AuditEventSummary records from application service."""
        from scantopath.application.projects.models import AuditEventSummary
        if not isinstance(events, tuple) or any(not isinstance(e, AuditEventSummary) for e in events):
            raise TypeError("Expected tuple[AuditEventSummary, ...]")
        self.audit_table.clear()
        for item in events:
            row = QTreeWidgetItem(self.audit_table, [
                item.occurred_at, item.level, item.action,
                f"{item.entity_type}: {item.entity_id}",
            ])
            row.setToolTip(2, item.details_json[:1000])
        self.audit_hint.setText(
            f"{len(events)} sự kiện SQLite gần nhất trong kho đã mở (tối đa 100). "
            "Nhấn Tải lại ở Cây dự án để cập nhật. Không bao gồm log UI."
        )
