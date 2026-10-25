"""Viewer 08.02 Qt View: present VTK-produced pixels, never own native OpenGL."""
from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtGui import QPixmap
from PySide6.QtWidgets import QFrame, QLabel, QSizePolicy, QVBoxLayout, QWidget


class Viewer3DPage(QWidget):
    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName('workspace_inspect3d')
        self.setAccessibleName('Kiểm tra 3D')
        outer = QVBoxLayout(self)
        outer.setContentsMargins(15, 12, 15, 12)
        outer.setSpacing(10)
        heading = QLabel('Kiểm tra 3D — VTK', self)
        heading.setObjectName('viewer3dTitle')
        heading.setAlignment(Qt.AlignLeft | Qt.AlignVCenter)
        outer.addWidget(heading)
        self.state = QLabel('Đang chuẩn bị VTK fixture…', self)
        self.state.setObjectName('workspaceState')
        self.state.setWordWrap(True)
        outer.addWidget(self.state)
        self.surface = QFrame(self)
        self.surface.setObjectName('viewer3dSurface')
        self.surface_layout = QVBoxLayout(self.surface)
        self.surface_layout.setContentsMargins(0, 0, 0, 0)
        self.preview = QLabel('Chưa có hình render VTK', self.surface)
        self.preview.setObjectName('viewer3dPreview')
        self.preview.setAlignment(Qt.AlignCenter)
        self.preview.setSizePolicy(QSizePolicy.Ignored, QSizePolicy.Ignored)
        self.preview.setMinimumSize(220, 140)
        self.preview.setStyleSheet('background-color: #1c2633; color: #e0e9f5;')
        self.surface_layout.addWidget(self.preview)
        outer.addWidget(self.surface, stretch=1)
        self.note = QLabel(
            'FIXTURE · 5 điểm tổng hợp · Không có đơn vị đo xác nhận · '
            'Ảnh do VTK render ở tiến trình riêng · Chưa tương tác 3D / mở PLY', self)
        self.note.setObjectName('workspaceFootnote')
        self.note.setWordWrap(True)
        outer.addWidget(self.note)
        self._image = QPixmap()

    def show_png(self, png_bytes: bytes) -> bool:
        image = QPixmap()
        if not png_bytes.startswith(b'\x89PNG\r\n\x1a\n') or not image.loadFromData(png_bytes, 'PNG'):
            return False
        self._image = image
        self._fit_preview()
        return True

    def _fit_preview(self) -> None:
        if not self._image.isNull():
            self.preview.setPixmap(self._image.scaled(
                self.preview.size(), Qt.KeepAspectRatio, Qt.SmoothTransformation))

    def resizeEvent(self, event) -> None:
        super().resizeEvent(event)
        self._fit_preview()

    def set_status(self, message: str) -> None:
        self.state.setText(message)
        self.state.setToolTip(message)
