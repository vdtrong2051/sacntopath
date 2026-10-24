"""Bảng thuộc tính chỉ hiển thị thông tin đối tượng được chọn, chưa truy vấn backend."""
from __future__ import annotations

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QAbstractItemView, QHBoxLayout, QLabel, QPushButton, QTreeWidget,
    QTreeWidgetItem, QVBoxLayout, QWidget,
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

    edit_requested = Signal()
    close_session_requested = Signal()
    verify_capture_requested = Signal()

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("propertyInspector")
        self.setAccessibleName("Thuộc tính đối tượng")
        layout = QVBoxLayout(self)
        layout.setContentsMargins(11, 11, 11, 12)
        layout.setSpacing(8)
        self.empty_label = QLabel("Chưa chọn đối tượng.")
        self.empty_label.setObjectName("inspectorEmptyLabel")
        self.empty_label.setWordWrap(True)
        layout.addWidget(self.empty_label)
        actions = QHBoxLayout()
        actions.setSpacing(7)
        self.edit_button = QPushButton("Sửa…", self)
        self.edit_button.setObjectName("editProjectMetadata")
        self.edit_button.setEnabled(False)
        self.edit_button.clicked.connect(self.edit_requested.emit)
        actions.addWidget(self.edit_button)
        self.close_button = QPushButton("Đóng phiên", self)
        self.close_button.setObjectName("closeScanSession")
        self.close_button.setEnabled(False)
        self.close_button.clicked.connect(self.close_session_requested.emit)
        actions.addWidget(self.close_button)
        layout.addLayout(actions)
        self.verify_button = QPushButton("Kiểm tra RAW", self)
        self.verify_button.setObjectName("verifySelectedCaptureRaw")
        self.verify_button.setEnabled(False)
        self.verify_button.clicked.connect(self.verify_capture_requested.emit)
        layout.addWidget(self.verify_button)
        self.details = QTreeWidget(self)
        self.details.setObjectName("inspectorProperties")
        self.details.setHeaderLabels(["Thuộc tính", "Giá trị"])
        self.details.setRootIsDecorated(False)
        self.details.setTextElideMode(Qt.ElideMiddle)
        self.details.setHorizontalScrollBarPolicy(Qt.ScrollBarAsNeeded)
        self.details.setAlternatingRowColors(True)
        self.details.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.details.setVisible(False)
        self.details.setColumnWidth(0, 105)
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
        self.note.setText("Thông tin này chỉ là tham chiếu ID; chưa tải metadata hoặc số đo.")
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
            item = QTreeWidgetItem(self.details, [name, value])
            item.setToolTip(1, value)

    def set_actions(self, *, can_edit: bool, can_close_session: bool) -> None:
        self.edit_button.setEnabled(can_edit)
        self.close_button.setEnabled(can_close_session)

    def set_verify_capability(self, enabled: bool) -> None:
        self.verify_button.setEnabled(enabled)

    def set_capture_inspection(self, state: str, message: str) -> None:
        """Replace the displayed RAW status only; never update SQLite."""
        if self._selection is None or self._selection.entity_type != "capture":
            return
        label = {"verified": "Đã kiểm tra", "missing": "Thiếu RAW",
                 "corrupt": "RAW không hợp lệ", "inaccessible": "Không thể truy cập"}.get(state, "Chưa xác định")
        for i in range(self.details.topLevelItemCount()):
            item = self.details.topLevelItem(i)
            if item.text(0) == "RAW":
                item.setText(1, label)
                break
        else:
            QTreeWidgetItem(self.details, ["RAW", label])
        self.note.setText(message + " Đây không phải xác nhận độ chính xác hình học.")

    def set_store_fields(self, fields: tuple[tuple[str, str], ...]) -> None:
        """Append verified DTO metadata, not guessed geometry/pose/accuracy."""
        if self._selection is None:
            raise RuntimeError("Cần chọn đối tượng trước khi hiển thị thông tin")
        if not isinstance(fields, tuple) or any(
            not isinstance(field, tuple) or len(field) != 2 or
            any(not isinstance(value, str) for value in field)
            for field in fields
        ):
            raise TypeError("fields phải là tuple[(str, str), ...]")
        for name, value in fields:
            item = QTreeWidgetItem(self.details, [name, value])
            item.setToolTip(1, value)
        self.note.setText("Metadata từ SQLite. Trạng thái RAW không phải độ chính xác hình học.")
