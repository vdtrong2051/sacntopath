"""R3.3: contextual, read-only Project metadata inspector.

Qt widgets render immutable DTO fields supplied by the Project presenter.
No persistence, RAW I/O, geometry measurement or hardware access occurs here.
"""
from __future__ import annotations

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QAbstractItemView, QFrame, QHBoxLayout, QLabel, QPushButton,
    QTreeWidget, QTreeWidgetItem, QVBoxLayout, QWidget,
)

from scantopath.application.contracts import SelectionRef


_ENTITY_TITLES = {
    "project": "Dự án",
    "specimen": "Vật mẫu",
    "scan_session": "Phiên quét",
    "capture": "Bản thu",
    "processing_run": "Lần xử lý",
}
_TITLE_FIELDS = ("Tên dự án", "Tên vật mẫu", "Tên phiên quét", "Công đoạn", "Loại dữ liệu")


class PropertyInspector(QWidget):
    """One selection authority; never infer a RAW checksum or metric geometry."""

    edit_requested = Signal()
    close_session_requested = Signal()
    verify_capture_requested = Signal()

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("propertyInspector")
        self.setAccessibleName("Thuộc tính đối tượng")
        self._selection: SelectionRef | None = None
        self._can_edit = False
        self._can_close = False
        self._can_verify = False

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        # A real header band, not a border painted across content/labels.
        self.context_frame = QFrame(self)
        self.context_frame.setObjectName("inspectorContextFrame")
        heading_layout = QVBoxLayout(self.context_frame)
        heading_layout.setContentsMargins(12, 11, 12, 10)
        heading_layout.setSpacing(4)
        self.kind_label = QLabel("", self.context_frame)
        self.kind_label.setObjectName("inspectorEntityKind")
        heading_layout.addWidget(self.kind_label)
        self.title_label = QLabel("", self.context_frame)
        self.title_label.setObjectName("inspectorEntityTitle")
        self.title_label.setWordWrap(True)
        self.title_label.setMaximumHeight(56)
        self.title_label.setTextInteractionFlags(Qt.TextSelectableByMouse)
        heading_layout.addWidget(self.title_label)
        layout.addWidget(self.context_frame)

        self.context_separator = QFrame(self)
        self.context_separator.setObjectName("inspectorContextSeparator")
        self.context_separator.setFrameShape(QFrame.HLine)
        self.context_separator.setFixedHeight(1)
        layout.addWidget(self.context_separator)

        self.empty_label = QLabel("Chưa chọn đối tượng.", self)
        self.empty_label.setObjectName("inspectorEmptyLabel")
        self.empty_label.setWordWrap(True)
        self.empty_label.setContentsMargins(12, 13, 12, 6)
        layout.addWidget(self.empty_label)

        self.properties_frame = QWidget(self)
        self.properties_frame.setObjectName("inspectorPropertiesFrame")
        prop_layout = QVBoxLayout(self.properties_frame)
        prop_layout.setContentsMargins(9, 10, 9, 8)
        prop_layout.setSpacing(6)
        self.section_label = QLabel("THÔNG TIN ĐỐI TƯỢNG", self.properties_frame)
        self.section_label.setObjectName("inspectorSectionTitle")
        prop_layout.addWidget(self.section_label)
        self.details = QTreeWidget(self.properties_frame)
        self.details.setObjectName("inspectorProperties")
        self.details.setHeaderLabels(["Thuộc tính", "Giá trị"])
        self.details.setRootIsDecorated(False)
        self.details.setUniformRowHeights(True)
        self.details.setTextElideMode(Qt.ElideMiddle)
        self.details.setHorizontalScrollBarPolicy(Qt.ScrollBarAsNeeded)
        self.details.setAlternatingRowColors(True)
        self.details.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.details.setColumnWidth(0, 112)
        prop_layout.addWidget(self.details, stretch=1)
        self.note = QLabel("Nguồn: metadata SQLite · không xác nhận hình học.", self.properties_frame)
        self.note.setObjectName("inspectorSourceNote")
        self.note.setWordWrap(True)
        self.note.setMaximumHeight(70)
        prop_layout.addWidget(self.note)
        layout.addWidget(self.properties_frame, stretch=1)

        self.actions_frame = QFrame(self)
        self.actions_frame.setObjectName("inspectorActionsFrame")
        action_layout = QVBoxLayout(self.actions_frame)
        action_layout.setContentsMargins(9, 8, 9, 10)
        action_layout.setSpacing(7)
        self.action_separator = QFrame(self.actions_frame)
        self.action_separator.setObjectName("inspectorActionSeparator")
        self.action_separator.setFrameShape(QFrame.HLine)
        self.action_separator.setFixedHeight(1)
        action_layout.addWidget(self.action_separator)
        row = QHBoxLayout()
        row.setSpacing(7)
        self.edit_button = QPushButton("Sửa…", self.actions_frame)
        self.edit_button.setObjectName("editProjectMetadata")
        self.edit_button.clicked.connect(self.edit_requested.emit)
        row.addWidget(self.edit_button)
        self.close_button = QPushButton("Đóng phiên", self.actions_frame)
        self.close_button.setObjectName("closeScanSession")
        self.close_button.clicked.connect(self.close_session_requested.emit)
        row.addWidget(self.close_button)
        action_layout.addLayout(row)
        self.verify_button = QPushButton("Kiểm tra RAW", self.actions_frame)
        self.verify_button.setObjectName("verifySelectedCaptureRaw")
        self.verify_button.clicked.connect(self.verify_capture_requested.emit)
        action_layout.addWidget(self.verify_button)
        layout.addWidget(self.actions_frame)
        self._sync_actions()
        self._sync_context()

    @property
    def selection(self) -> SelectionRef | None:
        return self._selection

    def _sync_context(self) -> None:
        selected = self._selection is not None
        self.context_frame.setVisible(selected)
        self.context_separator.setVisible(selected)
        self.properties_frame.setVisible(selected)
        self.empty_label.setVisible(not selected)
        self.actions_frame.setVisible(selected and self._selection.entity_type in (
            "project", "specimen", "scan_session", "capture"
        ))

    def _sync_actions(self) -> None:
        kind = self._selection.entity_type if self._selection is not None else None
        self.edit_button.setVisible(kind in ("project", "specimen", "scan_session"))
        self.edit_button.setEnabled(self._can_edit and kind in ("project", "specimen", "scan_session"))
        self.close_button.setVisible(kind == "scan_session")
        self.close_button.setEnabled(self._can_close and kind == "scan_session")
        self.verify_button.setVisible(kind == "capture")
        self.verify_button.setEnabled(self._can_verify and kind == "capture")
        self._sync_context()

    def _add_field(self, name: str, value: str) -> None:
        item = QTreeWidgetItem(self.details, [name, value])
        item.setToolTip(0, name)
        item.setToolTip(1, value)

    def set_selection(self, selection: SelectionRef | None) -> None:
        if selection is not None and not isinstance(selection, SelectionRef):
            raise TypeError("selection phải là SelectionRef hoặc None")
        self._selection = selection
        self.details.clear()
        self._can_edit = self._can_close = self._can_verify = False
        self.note.setText("Chỉ có tham chiếu đối tượng; chưa tải metadata hoặc số đo.")
        self.section_label.setText("THÔNG TIN ĐỐI TƯỢNG")
        if selection is not None:
            self.kind_label.setText(_ENTITY_TITLES.get(selection.entity_type, selection.entity_type).upper())
            self.title_label.setText(selection.entity_id)
            self.title_label.setToolTip(selection.entity_id)
            self._add_field("Loại", _ENTITY_TITLES.get(selection.entity_type, selection.entity_type))
            self._add_field("Mã định danh", selection.entity_id)
            if selection.source_id is not None:
                self._add_field("Mã nguồn", selection.source_id)
        self._sync_actions()

    def set_store_fields(self, fields: tuple[tuple[str, str], ...]) -> None:
        """Append validated DTO metadata; never invent geometry or RAW verification."""
        if self._selection is None:
            raise RuntimeError("Cần chọn đối tượng trước khi hiển thị thông tin")
        if not isinstance(fields, tuple) or any(
            not isinstance(field, tuple) or len(field) != 2 or
            any(not isinstance(value, str) for value in field)
            for field in fields
        ):
            raise TypeError("fields phải là tuple[(str, str), ...]")
        public_code = next((value for name, value in fields if name == "Mã"), "")
        display_name = next((value for name, value in fields if name in _TITLE_FIELDS), "")
        title = " · ".join(value for value in (public_code, display_name) if value and value != "Chưa cấp mã")
        if title:
            self.title_label.setText(title)
            self.title_label.setToolTip(title)
        for name, value in fields:
            self._add_field(name, value)
        self.section_label.setText("METADATA TỪ SQLITE")
        self.note.setText("Nguồn: metadata SQLite · RAW chưa được kiểm tra theo thao tác này.")

    def set_actions(self, *, can_edit: bool, can_close_session: bool) -> None:
        self._can_edit = bool(can_edit)
        self._can_close = bool(can_close_session)
        self._sync_actions()

    def set_verify_capability(self, enabled: bool) -> None:
        self._can_verify = bool(enabled)
        self._sync_actions()

    def set_capture_inspection(self, state: str, message: str) -> None:
        """Update only the selected Capture's RAW integrity result; no DB write."""
        if self._selection is None or self._selection.entity_type != "capture":
            return
        label = {"verified": "Đã kiểm tra", "missing": "Thiếu RAW",
                 "corrupt": "RAW không hợp lệ", "inaccessible": "Không thể truy cập"}.get(
                     state, "Chưa xác định")
        for index in range(self.details.topLevelItemCount()):
            item = self.details.topLevelItem(index)
            if item.text(0) == "RAW":
                item.setText(1, label)
                item.setToolTip(1, label)
                break
        else:
            self._add_field("RAW", label)
        self.note.setText(message + " Đây không phải xác nhận độ chính xác hình học.")
