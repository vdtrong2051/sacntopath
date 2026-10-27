"""Icon-based, keyboard-accessible Qt 3D toolbar; no geometry or VTK imports."""
from __future__ import annotations

from pathlib import Path
from PySide6.QtCore import Qt, Signal, QSize
from PySide6.QtGui import QIcon
from PySide6.QtWidgets import QFrame, QToolButton, QVBoxLayout, QButtonGroup, QMenu

ICON_ROOT = Path(__file__).resolve().parent / 'icons'


class LiveViewerTools(QFrame):
    mode_changed = Signal(str)
    camera_action = Signal(str)
    layer_changed = Signal(bool)
    grid_changed = Signal(bool, str)

    def __init__(self, parent):
        super().__init__(parent)
        self.setObjectName('viewer3dLiveTools')
        self.setAccessibleName('Công cụ kiểm tra 3D')
        self.setStyleSheet('''
            QFrame#viewer3dLiveTools { background: rgba(21,33,47,235);
                border-radius: 10px; border: 1px solid #586b80; }
            QToolButton { background: transparent; border: none; border-radius: 7px;
                color: #eaf2fa; padding: 3px; }
            QToolButton:hover { background: #3b546f; }
            QToolButton:checked { background: #2478d1; }
            QToolButton:disabled { opacity: 0.45; }
        ''')
        layout = QVBoxLayout(self)
        layout.setContentsMargins(5, 6, 5, 6)
        layout.setSpacing(4)
        self.setFixedWidth(52)
        self._modes = QButtonGroup(self)
        self._modes.setExclusive(True)
        self.buttons: dict[str, QToolButton] = {}
        for name, icon, tip, mode in (
            ('viewer3dToolSelect','cursor','Chọn điểm hoặc mặt (S): nhấp chuột trái','select'),
            ('viewer3dToolOrbit','orbit','Xoay góc nhìn (R): kéo chuột trái','orbit'),
            ('viewer3dToolPan','pan','Di chuyển góc nhìn (P): kéo chuột trái','pan'),
        ):
            b = self._make(name,icon,tip)
            b.setCheckable(True)
            self._modes.addButton(b)
            b.clicked.connect(lambda _checked=False, m=mode: self.mode_changed.emit(m))
            layout.addWidget(b)
        self.buttons['viewer3dToolOrbit'].setChecked(True)
        self._divider(layout)
        for name, icon, tip, action in (
            ('viewer3dToolFit','fit','Vừa khung nhìn (F)','reset'),
            ('viewer3dToolAxes','axes','Bật hoặc tắt trục tọa độ tham khảo','axes'),
            ('viewer3dToolZoomIn','zoom_in','Phóng to góc nhìn','zoom_in'),
            ('viewer3dToolZoomOut','zoom_out','Thu nhỏ góc nhìn','zoom_out'),
        ):
            b = self._make(name,icon,tip)
            b.clicked.connect(lambda _checked=False, a=action: self.camera_action.emit(a))
            layout.addWidget(b)
        self._divider(layout)
        self.grid_button = self._make('viewer3dToolGrid','grid','Bật/tắt lưới tham chiếu Oxy (G)')
        self.grid_button.setCheckable(True)
        self.grid_button.setChecked(True)
        self.grid_button.toggled.connect(self._notify_grid)
        self.grid_mode = 'xy'
        self.grid_button.setContextMenuPolicy(Qt.CustomContextMenu)
        self.grid_button.customContextMenuRequested.connect(self._grid_menu)
        layout.addWidget(self.grid_button)
        self.layer_button = self._make('viewer3dToolLayer','layers','Hiện hoặc ẩn lớp hình học (L)')
        self.layer_button.setCheckable(True)
        self.layer_button.setChecked(True)
        self.layer_button.toggled.connect(self.layer_changed.emit)
        layout.addWidget(self.layer_button)
        self.adjustSize()

    def _make(self, name: str, icon: str, tooltip: str) -> QToolButton:
        b = QToolButton(self)
        b.setObjectName(name)
        icon_path = ICON_ROOT / (icon + '.svg')
        if not icon_path.is_file():
            raise FileNotFoundError('THIEU_BIEU_TUONG: ' + str(icon_path))
        b.setIcon(QIcon(str(icon_path)))
        b.setIconSize(QSize(23,23))
        b.setToolButtonStyle(Qt.ToolButtonIconOnly)
        b.setFixedSize(40,40)
        b.setToolTip(tooltip)
        b.setAccessibleName(tooltip.split(' (')[0])
        self.buttons[name] = b
        return b

    @staticmethod
    def _divider(layout):
        sep = QFrame()
        sep.setFrameShape(QFrame.HLine)
        sep.setStyleSheet('background:#586b80;max-height:1px;')
        layout.addWidget(sep)

    def _notify_grid(self, active: bool) -> None:
        self.grid_changed.emit(bool(active), self.grid_mode)

    def _grid_menu(self, point) -> None:
        menu = QMenu(self)
        xy = menu.addAction('Mặt phẳng Oxy (Z = 0)')
        base = menu.addAction('Theo đáy mô hình (chỉ tham chiếu)')
        chosen = menu.exec(self.grid_button.mapToGlobal(point))
        if chosen not in (xy, base):
            return
        self.grid_mode = 'xy' if chosen == xy else 'base'
        if not self.grid_button.isChecked():
            self.grid_button.setChecked(True)
        else:
            self._notify_grid(True)

    def set_mode(self, mode: str):
        names = {'select':'viewer3dToolSelect','orbit':'viewer3dToolOrbit',
                 'pan':'viewer3dToolPan'}
        if mode in names:
            self.buttons[names[mode]].setChecked(True)

    def set_layer(self, visible: bool) -> None:
        self.layer_button.blockSignals(True)
        self.layer_button.setChecked(bool(visible))
        self.layer_button.blockSignals(False)

    def set_grid(self, enabled: bool, mode: str = 'xy') -> None:
        self.grid_button.blockSignals(True)
        self.grid_mode = mode
        self.grid_button.setChecked(bool(enabled))
        self.grid_button.blockSignals(False)

    def reset_layer(self) -> None:
        self.set_layer(True)
        self.set_grid(True,'xy')
