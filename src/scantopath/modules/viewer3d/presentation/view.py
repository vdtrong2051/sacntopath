"""08.03 Qt presentation: controls and pixels only, no vtk, SQL or file parsing."""
from __future__ import annotations
from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QPixmap
from PySide6.QtWidgets import QFrame, QLabel, QPushButton, QSizePolicy, QHBoxLayout, QVBoxLayout, QWidget

from ..application.ply_contracts import PlySummary


class Viewer3DPage(QWidget):
    open_ply_requested = Signal()

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName('workspace_inspect3d')
        self.setAccessibleName('Kiểm tra 3D')
        outer = QVBoxLayout(self)
        outer.setContentsMargins(15, 12, 15, 12)
        outer.setSpacing(10)
        row = QHBoxLayout()
        heading = QLabel('Kiểm tra 3D — VTK', self)
        heading.setObjectName('viewer3dTitle')
        heading.setAlignment(Qt.AlignLeft | Qt.AlignVCenter)
        row.addWidget(heading)
        row.addStretch(1)
        self.open_ply_button = QPushButton('Mở PLY…', self)
        self.open_ply_button.setObjectName('viewer3dOpenPlyButton')
        self.open_ply_button.clicked.connect(self.open_ply_requested.emit)
        row.addWidget(self.open_ply_button)
        outer.addLayout(row)
        self.state = QLabel('Đang chuẩn bị VTK fixture…', self)
        self.state.setObjectName('workspaceState')
        self.state.setWordWrap(True)
        self.state.setTextFormat(Qt.PlainText)
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
            'Ảnh do VTK render ở tiến trình riêng · Nhấn Mở PLY để nhập dữ liệu', self)
        self.note.setObjectName('workspaceFootnote')
        self.note.setTextFormat(Qt.PlainText)
        self.note.setWordWrap(True)
        outer.addWidget(self.note)
        self._image = QPixmap()

    def set_loading(self, active: bool) -> None:
        self.open_ply_button.setEnabled(not active)

    def show_fixture(self) -> None:
        self.note.setText('FIXTURE · 5 điểm tổng hợp · Không có đơn vị đo xác nhận · '
                          'Ảnh do VTK render ở tiến trình riêng · Nhấn Mở PLY để nhập dữ liệu')

    def show_ply(self, summary: PlySummary) -> None:
        x0, x1, y0, y1, z0, z1 = summary.bounds
        self.note.setText(
            f'PLY: {summary.name} · {summary.point_count:,} điểm · '
            f'Bounds X[{x0:.4g}, {x1:.4g}] Y[{y0:.4g}, {y1:.4g}] Z[{z0:.4g}, {z1:.4g}] · '
            f'RGB: {"Có" if summary.has_rgb else "Không"} · '
            f'Đơn vị/hệ tọa độ: chưa xác nhận · Chỉ xem ảnh VTK, chưa tương tác 3D')

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
