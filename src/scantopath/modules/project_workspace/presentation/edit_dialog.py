"""Compact Vietnamese edit dialog, metadata only. No persistence code in QWidget."""
from __future__ import annotations

from PySide6.QtWidgets import (
    QDialog, QDialogButtonBox, QFormLayout, QLabel, QLineEdit, QPlainTextEdit,
    QVBoxLayout,
)
from .forms_contract import validate_description, validate_label


class ProjectEditDialog(QDialog):
    def __init__(self, *, kind: str, create: bool, name: str = "",
                 description: str = "", parent=None) -> None:
        super().__init__(parent)
        if kind not in ("project", "specimen", "session"):
            raise ValueError("Unknown edit dialog type")
        self.kind = kind
        names = {"project": "dự án", "specimen": "vật mẫu", "session": "phiên quét"}
        self.setWindowTitle(("Tạo " if create else "Sửa ") + names[kind])
        self.setObjectName("projectEditDialog")
        self.setMinimumWidth(330)
        self.resize(400, 230 if kind != "session" else 160)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(14, 12, 14, 12)
        form = QFormLayout()
        form.setSpacing(8)
        self.name_edit = QLineEdit(self)
        self.name_edit.setObjectName("projectNameEdit")
        self.name_edit.setMaxLength(256)
        self.name_edit.setText(name)
        form.addRow("Tên hiển thị:", self.name_edit)
        self.description_edit = None
        if kind != "session":
            self.description_edit = QPlainTextEdit(self)
            self.description_edit.setObjectName("projectDescriptionEdit")
            self.description_edit.setMaximumHeight(92)
            self.description_edit.setPlainText(description)
            form.addRow("Mô tả:", self.description_edit)
        layout.addLayout(form)
        self.error_label = QLabel("", self)
        self.error_label.setObjectName("projectEditError")
        self.error_label.setWordWrap(True)
        layout.addWidget(self.error_label)
        self.buttons = QDialogButtonBox(QDialogButtonBox.Save | QDialogButtonBox.Cancel, parent=self)
        self.buttons.button(QDialogButtonBox.Save).setText("Lưu")
        self.buttons.button(QDialogButtonBox.Cancel).setText("Hủy")
        self.buttons.accepted.connect(self._validate_accept)
        self.buttons.rejected.connect(self.reject)
        layout.addWidget(self.buttons)

    def _validate_accept(self) -> None:
        try:
            validate_label(self.name_edit.text())
            if self.description_edit is not None:
                validate_description(self.description_edit.toPlainText())
        except ValueError as exc:
            self.error_label.setText(str(exc))
            return
        self.accept()

    def values(self) -> tuple[str, str]:
        return (validate_label(self.name_edit.text()),
                validate_description(self.description_edit.toPlainText())
                if self.description_edit is not None else "")
