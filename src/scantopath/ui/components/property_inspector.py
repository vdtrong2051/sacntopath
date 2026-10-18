"""Bảng thuộc tính chỉ hiển thị thông tin đối tượng được chọn, chưa truy vấn backend."""
from __future__ import annotations

from PySide6.QtWidgets import (
    QAbstractItemView, QLabel, QTreeWidget, QTreeWidgetItem, QVBoxLayout, QWidget,
)

from scantopath.application.contracts import SelectionRef


_ENTITY_TITLES = {
    "project": "Dự án",
    "specimen": "Vật mẫu",
    "scan_session": "Phiên quét",
    "capture": "Bản thu",
    "processing_run": "Lần xử lý",
}


class PropertyInspector(QWidget):
    """Không hiển thị thông số đo/pose khi chỉ có SelectionRef."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("propertyInspector")
        self.setAccessibleName("Thuộc tính đối tượng")
        layout = QVBoxLayout(self)
        layout.setContentsMargins(9, 10, 9, 10)
        self.empty_label = QLabel("Chưa chọn đối tượng.")
        self.empty_label.setObjectName("inspectorEmptyLabel")
        self.empty_label.setWordWrap(True)
        layout.addWidget(self.empty_label)
        self.details = QTreeWidget(self)
        self.details.setObjectName("inspectorProperties")
        self.details.setHeaderLabels(["Thuộc tính", "Giá trị"])
        self.details.setRootIsDecorated(False)
        self.details.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.details.setVisible(False)
        layout.addWidget(self.details, stretch=1)
        self.note = QLabel("Thông tin này chỉ là tham chiếu ID; chưa tải metadata hoặc số đo.")
        self.note.setObjectName("inspectorSourceNote")
        self.note.setWordWrap(True)
        self.note.setVisible(False)
        layout.addWidget(self.note)
        self._selection: SelectionRef | None = None

    @property
    def selection(self) -> SelectionRef | None:
        return self._selection

    def set_selection(self, selection: SelectionRef | None) -> None:
        if selection is not None and not isinstance(selection, SelectionRef):
            raise TypeError("selection phải là SelectionRef hoặc None")
        self._selection = selection
        self.details.clear()
        show = selection is not None
        self.empty_label.setVisible(not show)
        self.details.setVisible(show)
        self.note.setVisible(show)
        if selection is None:
            return
        rows = [
            ("Loại", _ENTITY_TITLES.get(selection.entity_type, selection.entity_type)),
            ("Mã định danh", selection.entity_id),
        ]
        if selection.source_id is not None:
            rows.append(("Mã nguồn", selection.source_id))
        for name, value in rows:
            QTreeWidgetItem(self.details, [name, value])
