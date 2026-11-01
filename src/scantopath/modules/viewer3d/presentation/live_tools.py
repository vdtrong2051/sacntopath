"""Icon-based, keyboard-accessible Qt 3D toolbar; no geometry or VTK imports."""
from __future__ import annotations

from pathlib import Path
from PySide6.QtCore import Qt, Signal, QSize
from PySide6.QtGui import QIcon, QActionGroup
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
        # Primary: high-frequency inspection and camera reset, always visible.
        self._divider(layout)
        fit = self._make('viewer3dToolFit', 'fit', 'Vừa khung nhìn (F)')
        fit.clicked.connect(lambda _checked=False: self.camera_action.emit('reset'))
        layout.addWidget(fit)

        # Advanced actions live in one menu. Keep the ORIGINAL QToolButtons,
        # objectNames, signals and shortcuts so existing callers remain stable.
        # Their visual duplicates are not placed on the canvas.
        self._divider(layout)
        self.advanced_button = QToolButton(self)
        self.advanced_button.setObjectName('viewer3dToolAdvanced')
        self.advanced_button.setText('⋯')
        self.advanced_button.setToolTip('Công cụ nâng cao: Zoom, Trục, Lưới, Lớp')
        self.advanced_button.setAccessibleName('Công cụ nâng cao')
        self.advanced_button.setFixedSize(40, 40)
        self.advanced_button.setPopupMode(QToolButton.InstantPopup)
        self.advanced_menu = QMenu(self.advanced_button)
        self.advanced_menu.setObjectName('viewer3dAdvancedMenu')
        self.advanced_button.setMenu(self.advanced_menu)
        # UXH-01.7-B-POLISH-HOTFIX (UI only)
        # Hide the native popup chevron: it crowds the ellipsis on 40px buttons.
        self.advanced_button.setStyleSheet("""
            QToolButton#viewer3dToolAdvanced {
                background-color: #263b52;
                color: #eef6ff;
                border: 1px solid #58758f;
                border-radius: 9px;
                font: 700 19px "Segoe UI";
                padding: 0px 0px 5px 0px;
            }
            QToolButton#viewer3dToolAdvanced:hover {
                background-color: #345675;
                border-color: #80b6e6;
            }
            QToolButton#viewer3dToolAdvanced:pressed {
                background-color: #1d3249;
            }
            QToolButton#viewer3dToolAdvanced::menu-indicator {
                image: none;
                width: 0px;
                height: 0px;
            }
        """)
        self.advanced_menu.setMinimumWidth(245)
        self.advanced_menu.setStyleSheet("""
            QMenu#viewer3dAdvancedMenu, QMenu#viewer3dGridPlaneMenu {
                background-color: #192b3d;
                color: #eaf3ff;
                border: 1px solid #4b6580;
                border-radius: 10px;
                padding: 7px 5px;
                font: 12px "Segoe UI";
            }
            QMenu::item {
                padding: 9px 30px 9px 27px;
                margin: 2px 5px;
                border-radius: 6px;
                background: transparent;
            }
            QMenu::item:selected {
                background-color: #315475;
                color: #ffffff;
            }
            QMenu::item:disabled {
                color: #849bb0;
            }
            QMenu::separator {
                height: 1px;
                background-color: #425e79;
                margin: 6px 14px;
            }
        """)
        layout.addWidget(self.advanced_button)

        for name, icon, tip, action, label in (
            ('viewer3dToolAxes', 'axes',
             'Trục gốc O nét mảnh; gizmo góc hiển thị hướng XYZ (không xác nhận hệ world)',
             'axes', 'Hiện/ẩn trục XYZ'),
            ('viewer3dToolZoomIn', 'zoom_in', 'Phóng to góc nhìn', 'zoom_in', 'Phóng to'),
            ('viewer3dToolZoomOut', 'zoom_out', 'Thu nhỏ góc nhìn', 'zoom_out', 'Thu nhỏ'),
        ):
            button = self._make(name, icon, tip)
            button.clicked.connect(lambda _checked=False, a=action: self.camera_action.emit(a))
            button.hide()
            menu_action = self.advanced_menu.addAction(label)
            menu_action.setObjectName('viewer3dAction' + action.title().replace('_', ''))
            menu_action.triggered.connect(lambda _checked=False, b=button: b.click())

        self.advanced_menu.addSeparator()
        self.grid_button = self._make('viewer3dToolGrid', 'grid',
            'Lưới tham chiếu nét chính/phụ, không phải mặt sàn (G)')
        self.grid_button.setCheckable(True)
        self.grid_button.setChecked(True)
        self.grid_mode = 'xy'
        self.grid_button.toggled.connect(self._notify_grid)
        self.grid_button.setContextMenuPolicy(Qt.CustomContextMenu)
        self.grid_button.customContextMenuRequested.connect(self._grid_menu)
        self.grid_button.hide()

        self._advanced_grid_action = self.advanced_menu.addAction('Hiện lưới tham chiếu (G)')
        self._advanced_grid_action.setObjectName('viewer3dActionGrid')
        self._advanced_grid_action.setCheckable(True)
        self._advanced_grid_action.setChecked(True)
        self._advanced_grid_action.triggered.connect(
            lambda _checked=False: self.grid_button.setChecked(
                self._advanced_grid_action.isChecked()
            )
        )
        self.grid_button.toggled.connect(
            lambda _checked=False: self._advanced_grid_action.setChecked(
                self.grid_button.isChecked()
            )
        )

        plane_menu = self.advanced_menu.addMenu('Mặt phẳng lưới')
        plane_menu.setObjectName('viewer3dGridPlaneMenu')
        plane_menu.setStyleSheet(self.advanced_menu.styleSheet())
        plane_group = QActionGroup(self)
        plane_group.setExclusive(True)
        self._grid_plane_actions = {}
        for mode, title in (
            ('xy', 'XY — Z = 0'),
            ('xz', 'XZ — Y = 0'),
            ('yz', 'YZ — X = 0'),
            ('base', 'Base — Z nhỏ nhất của mô hình (không phải mặt đất)'),
        ):
            choice = plane_menu.addAction(title)
            choice.setObjectName('viewer3dGridPlane' + mode.upper())
            choice.setCheckable(True)
            plane_group.addAction(choice)
            choice.triggered.connect(lambda _checked=False, m=mode: self._select_grid_plane(m))
            self._grid_plane_actions[mode] = choice
        self._grid_plane_actions['xy'].setChecked(True)

        self.layer_button = self._make('viewer3dToolLayer', 'layers',
            'Hiện hoặc ẩn lớp hình học (L)')
        self.layer_button.setCheckable(True)
        self.layer_button.setChecked(True)
        self.layer_button.toggled.connect(self.layer_changed.emit)
        self.layer_button.hide()
        self._advanced_layer_action = self.advanced_menu.addAction('Hiện lớp hình học (L)')
        self._advanced_layer_action.setObjectName('viewer3dActionLayer')
        self._advanced_layer_action.setCheckable(True)
        self._advanced_layer_action.setChecked(True)
        self._advanced_layer_action.triggered.connect(
            lambda _checked=False: self.layer_button.setChecked(
                self._advanced_layer_action.isChecked()
            )
        )
        self.layer_button.toggled.connect(
            lambda _checked=False: self._advanced_layer_action.setChecked(
                self.layer_button.isChecked()
            )
        )
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
        actions = {
            menu.addAction('XY — Z = 0 (mặt phẳng tọa độ)'): 'xy',
            menu.addAction('XZ — Y = 0 (mặt phẳng tọa độ)'): 'xz',
            menu.addAction('YZ — X = 0 (mặt phẳng tọa độ)'): 'yz',
            menu.addAction('Base — Z nhỏ nhất của mô hình (không phải mặt đất)'): 'base',
        }
        chosen = menu.exec(self.grid_button.mapToGlobal(point))
        if chosen not in actions:
            return
        self._select_grid_plane(actions[chosen])

    def _select_grid_plane(self, mode: str) -> None:
        if mode not in self._grid_plane_actions:
            raise ValueError('INVALID_REFERENCE_GRID')
        self.grid_mode = mode
        self._grid_plane_actions[mode].setChecked(True)
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
        self._advanced_layer_action.setChecked(bool(visible))

    def set_grid(self, enabled: bool, mode: str = 'xy') -> None:
        if mode not in ('xy', 'xz', 'yz', 'base'):
            raise ValueError('INVALID_REFERENCE_GRID')
        self.grid_button.blockSignals(True)
        self.grid_mode = mode
        self.grid_button.setChecked(bool(enabled))
        self.grid_button.blockSignals(False)
        self._advanced_grid_action.setChecked(bool(enabled))
        self._grid_plane_actions[mode].setChecked(True)

    def reset_layer(self) -> None:
        self.set_layer(True)
        self.set_grid(True,'xy')
