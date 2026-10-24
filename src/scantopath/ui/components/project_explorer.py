"""Panel điều hướng dữ liệu. GĐ1-06.4 không tự đọc SQLite hoặc tạo dữ liệu mẫu."""
from __future__ import annotations

from dataclasses import dataclass

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import QHBoxLayout, QLabel, QMenu, QPushButton, QTreeWidget, QTreeWidgetItem, QVBoxLayout, QWidget

from scantopath.application.contracts import SelectionRef


@dataclass(frozen=True, slots=True)
class ExplorerNode:
    """Đầu vào đã được xác thực từ tầng ứng dụng (phiên 07), không phải ORM."""

    label: str
    selection: SelectionRef
    children: tuple["ExplorerNode", ...] = ()

    def __post_init__(self) -> None:
        if not isinstance(self.label, str) or not self.label.strip():
            raise ValueError("Tên hiển thị phải là chuỗi không rỗng")
        if not isinstance(self.selection, SelectionRef):
            raise TypeError("selection phải là SelectionRef")
        if not isinstance(self.children, tuple) or not all(
            isinstance(child, ExplorerNode) for child in self.children
        ):
            raise TypeError("children phải là tuple[ExplorerNode, ...]")


class ProjectExplorer(QWidget):
    """Explorer chỉ nhận cây dữ liệu được truyền vào, không tự mở DB."""

    selection_changed = Signal(object)
    open_requested = Signal()
    refresh_requested = Signal()
    create_project_requested = Signal()
    create_specimen_requested = Signal()
    create_session_requested = Signal()

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("projectExplorer")
        self.setAccessibleName("Cây dự án")
        layout = QVBoxLayout(self)
        layout.setContentsMargins(10, 11, 10, 11)
        layout.setSpacing(7)
        controls = QHBoxLayout()
        controls.setSpacing(6)
        self.open_button = QPushButton("Mở kho…", self)
        self.open_button.setObjectName("openProjectStore")
        self.open_button.setToolTip("Chọn thư mục đã có metadata.sqlite3")
        self.open_button.clicked.connect(self.open_requested.emit)
        controls.addWidget(self.open_button)
        self.refresh_button = QPushButton("Tải lại", self)
        self.refresh_button.setObjectName("refreshProjectStore")
        self.refresh_button.setEnabled(False)
        self.refresh_button.clicked.connect(self.refresh_requested.emit)
        controls.addWidget(self.refresh_button)
        layout.addLayout(controls)
        self.add_menu = QMenu(self)
        self.create_project_action = self.add_menu.addAction("Tạo dự án")
        self.create_specimen_action = self.add_menu.addAction("Thêm vật mẫu")
        self.create_session_action = self.add_menu.addAction("Tạo phiên quét")
        self.create_project_action.triggered.connect(self.create_project_requested.emit)
        self.create_specimen_action.triggered.connect(self.create_specimen_requested.emit)
        self.create_session_action.triggered.connect(self.create_session_requested.emit)
        self.add_button = QPushButton("＋ Thêm…", self)
        self.add_button.setObjectName("addProjectEntity")
        self.add_button.setMenu(self.add_menu)
        self.add_button.setEnabled(False)
        self.add_button.setMaximumHeight(32)
        layout.addWidget(self.add_button)
        self.store_label = QLabel("Kho: Chưa chọn", self)
        self.store_label.setObjectName("projectStoreLabel")
        self.store_label.setWordWrap(True)
        layout.addWidget(self.store_label)
        self.empty_label = QLabel("Chưa tải dữ liệu dự án. Hãy chọn kho SQLite.")
        self.empty_label.setObjectName("explorerEmptyLabel")
        self.empty_label.setWordWrap(True)
        layout.addWidget(self.empty_label)

        self.tree = QTreeWidget(self)
        self.tree.setObjectName("projectExplorerTree")
        self.tree.setHeaderLabels(["Đối tượng"])
        self.tree.setUniformRowHeights(True)
        self.tree.setTextElideMode(Qt.ElideMiddle)
        self.tree.setHorizontalScrollBarPolicy(Qt.ScrollBarAsNeeded)
        self.tree.setVisible(False)
        self.tree.setEnabled(False)
        self.tree.currentItemChanged.connect(self._current_item_changed)
        layout.addWidget(self.tree, stretch=1)
        self._selection: SelectionRef | None = None
        self._store_root: str | None = None

    @property
    def selection(self) -> SelectionRef | None:
        return self._selection

    @property
    def store_root(self) -> str | None:
        return self._store_root

    def show_store(self, root: str | None, *, schema_version: int | None = None) -> None:
        self._store_root = root
        if root is None:
            self.store_label.setText("Kho: Chưa chọn")
            self.store_label.setToolTip("")
        else:
            from pathlib import Path
            self.store_label.setText(f"Kho: {Path(root).name} · SQLite v{schema_version}" if schema_version else f"Kho: {Path(root).name}")
            self.store_label.setToolTip(root)
        self.refresh_button.setEnabled(root is not None)

    def set_busy(self, busy: bool) -> None:
        self.open_button.setEnabled(not busy)
        self.refresh_button.setEnabled(not busy and self._store_root is not None)
        if busy:
            self.empty_label.setText("Đang tải dữ liệu dự án…")
            self.empty_label.setVisible(True)

    def set_write_capabilities(self, can_write: bool, kind: str | None) -> None:
        """Caller uses selected SQLite schema and selected node identity."""
        self.add_button.setEnabled(can_write)
        self.create_project_action.setEnabled(can_write)
        self.create_specimen_action.setEnabled(can_write and kind == "project")
        self.create_session_action.setEnabled(can_write and kind == "specimen")
        self.add_button.setToolTip(
            "Tạo metadata mới trong SQLite v2" if can_write
            else "Chỉ ghi khi đã chọn kho SQLite v2 và không có tác vụ đang chạy"
        )

    def show_message(self, message: str) -> None:
        self.empty_label.setText(message)
        self.empty_label.setVisible(True)

    def set_nodes(self, nodes: tuple[ExplorerNode, ...]) -> None:
        """Cập nhật cây sau khi đã có nguồn dữ liệu thực; không thêm fixture."""
        if not isinstance(nodes, tuple) or not all(isinstance(n, ExplorerNode) for n in nodes):
            raise TypeError("nodes phải là tuple[ExplorerNode, ...]")
        previous = self.tree.blockSignals(True)
        try:
            self.tree.clear()
            for node in nodes:
                self._add_node(None, node)
            self.tree.setEnabled(bool(nodes))
            self.tree.setVisible(bool(nodes))
            self.empty_label.setVisible(not nodes)
        finally:
            self.tree.blockSignals(previous)
        self._update_selection(None)

    def clear_selection(self) -> None:
        self.tree.clearSelection()
        self.tree.setCurrentItem(None)
        self._update_selection(None)

    def _add_node(self, parent: QTreeWidgetItem | None, node: ExplorerNode) -> None:
        item = QTreeWidgetItem([node.label])
        item.setData(0, Qt.UserRole, node.selection)
        item.setToolTip(0, node.label)  # Always expose full, unelided name.
        if parent is None:
            self.tree.addTopLevelItem(item)
        else:
            parent.addChild(item)
        for child in node.children:
            self._add_node(item, child)

    def _current_item_changed(self, item: QTreeWidgetItem | None, _previous: QTreeWidgetItem | None) -> None:
        selection = item.data(0, Qt.UserRole) if item is not None else None
        self._update_selection(selection)

    def _update_selection(self, selection: SelectionRef | None) -> None:
        if self._selection == selection:
            return
        self._selection = selection
        self.selection_changed.emit(selection)
