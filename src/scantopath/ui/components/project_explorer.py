"""Panel điều hướng dữ liệu. GĐ1-06.4 không tự đọc SQLite hoặc tạo dữ liệu mẫu."""
from __future__ import annotations

from dataclasses import dataclass

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import QLabel, QTreeWidget, QTreeWidgetItem, QVBoxLayout, QWidget

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

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("projectExplorer")
        self.setAccessibleName("Cây dự án")
        layout = QVBoxLayout(self)
        layout.setContentsMargins(9, 10, 9, 10)
        self.empty_label = QLabel("Chưa tải dữ liệu dự án. Kết nối SQLite ở phiên 07.")
        self.empty_label.setObjectName("explorerEmptyLabel")
        self.empty_label.setWordWrap(True)
        layout.addWidget(self.empty_label)

        self.tree = QTreeWidget(self)
        self.tree.setObjectName("projectExplorerTree")
        self.tree.setHeaderLabels(["Đối tượng"])
        self.tree.setUniformRowHeights(True)
        self.tree.setVisible(False)
        self.tree.setEnabled(False)
        self.tree.currentItemChanged.connect(self._current_item_changed)
        layout.addWidget(self.tree, stretch=1)
        self._selection: SelectionRef | None = None

    @property
    def selection(self) -> SelectionRef | None:
        return self._selection

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
