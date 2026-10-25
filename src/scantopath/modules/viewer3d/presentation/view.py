"""Feature-local Qt View: owns only widgets and visible state, no VTK imports."""
from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QFrame, QLabel, QVBoxLayout, QWidget


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
        self.state = QLabel('Đang chuẩn bị viewer thử nghiệm…', self)
        self.state.setObjectName('workspaceState')
        self.state.setWordWrap(True)
        outer.addWidget(self.state)
        self.surface = QFrame(self)
        self.surface.setObjectName('viewer3dSurface')
        self.surface_layout = QVBoxLayout(self.surface)
        self.surface_layout.setContentsMargins(0, 0, 0, 0)
        outer.addWidget(self.surface, stretch=1)
        self.note = QLabel('FIXTURE · 5 điểm tổng hợp · Không có đơn vị đo xác nhận · Không mở PLY', self)
        self.note.setObjectName('workspaceFootnote')
        self.note.setWordWrap(True)
        outer.addWidget(self.note)
        self._host: QWidget | None = None

    def mount(self, host: QWidget) -> None:
        if self._host is not None:
            raise RuntimeError('Viewer render host already mounted')
        if not isinstance(host, QWidget):
            raise TypeError('Expected a Qt QWidget VTK host')
        self._host = host
        self.surface_layout.addWidget(host)

    def set_status(self, message: str) -> None:
        self.state.setText(message)

    def unmount(self) -> None:
        if self._host is not None:
            self.surface_layout.removeWidget(self._host)
            self._host.setParent(None)
            self._host = None
