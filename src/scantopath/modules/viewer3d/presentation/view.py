"""08.03 Qt presentation: controls and pixels only, no vtk, SQL or file parsing."""
from __future__ import annotations
from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QPixmap, QPainter, QPen, QColor
from PySide6.QtWidgets import QFrame, QLabel, QPushButton, QSizePolicy, QHBoxLayout, QVBoxLayout, QWidget

from ..application.ply_contracts import PlySummary
from ..application.picking import PickResult, image_click_uv


class NavigationPreview(QLabel):
    """Gesture-only Qt view of a PNG. Never imports or invokes native VTK."""
    gesture = Signal(str, float, float)
    point_clicked = Signal(float, float)

    def __init__(self, text: str, parent=None):
        super().__init__(text, parent)
        self.setMouseTracking(True)
        self._origin = None
        self._button = None
        self._point_marker = None
        self._pick_enabled = False
        self.setToolTip('Kéo chuột trái: xoay · Kéo chuột phải: tịnh tiến · Cuộn: phóng to/thu nhỏ')

    def mousePressEvent(self, event):
        if event.button() in (Qt.LeftButton, Qt.RightButton) and self.pixmap() is not None and not self.pixmap().isNull():
            self._origin = event.position().toPoint()
            self._button = event.button()
            event.accept()
            return
        super().mousePressEvent(event)

    def mouseReleaseEvent(self, event):
        if self._origin is not None and event.button() == self._button:
            delta = event.position().toPoint() - self._origin
            button = self._button
            self._origin = self._button = None
            if abs(delta.x()) + abs(delta.y()) < 3 and button == Qt.LeftButton and self._pick_enabled:
                pix = self.pixmap()
                if pix is not None and not pix.isNull():
                    try:
                        uv = image_click_uv(float(event.position().x()), float(event.position().y()),
                                            self.width(), self.height(), pix.width(), pix.height())
                    except ValueError:
                        uv = None
                    if uv is not None:
                        self.point_clicked.emit(*uv)
            elif abs(delta.x()) + abs(delta.y()) >= 3:
                if button == Qt.LeftButton:
                    self.gesture.emit('orbit', delta.x() * 0.45, delta.y() * 0.45)
                else:
                    self.gesture.emit('pan', float(delta.x()), float(delta.y()))
            event.accept()
            return
        super().mouseReleaseEvent(event)

    def wheelEvent(self, event):
        if self.pixmap() is not None and not self.pixmap().isNull():
            steps = event.angleDelta().y() / 120.0
            if steps:
                self.gesture.emit('zoom', float(steps), 0.0)
            event.accept()
            return
        super().wheelEvent(event)


    def set_pick_enabled(self, enabled: bool) -> None:
        self._pick_enabled = bool(enabled)

    def set_marker(self, uv: tuple[float, float] | None) -> None:
        self._point_marker = uv
        self.update()

    def paintEvent(self, event) -> None:
        super().paintEvent(event)
        pix = self.pixmap()
        if self._point_marker is None or pix is None or pix.isNull():
            return
        u, v = self._point_marker
        x = (self.width()-pix.width())/2.0 + u*(pix.width()-1)
        y = (self.height()-pix.height())/2.0 + (1-v)*(pix.height()-1)
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        painter.setPen(QPen(QColor('#ffcb52'), 2))
        painter.drawEllipse(int(x)-6, int(y)-6, 12, 12)
        painter.end()


class Viewer3DPage(QWidget):
    open_ply_requested = Signal()
    navigation_requested = Signal(str, float, float)
    point_requested = Signal(float, float)
    layer_visibility_changed = Signal(bool)

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
        nav_row = QHBoxLayout()
        nav_row.setSpacing(6)
        self.navigation_buttons = []
        for label, name, action, dx, dy in (
            ('↶ Xoay trái', 'viewer3dOrbitLeft', 'orbit', -20.0, 0.0),
            ('↷ Xoay phải', 'viewer3dOrbitRight', 'orbit', 20.0, 0.0),
            ('↑ Nâng góc', 'viewer3dOrbitUp', 'orbit', 0.0, -15.0),
            ('↓ Hạ góc', 'viewer3dOrbitDown', 'orbit', 0.0, 15.0),
            ('+', 'viewer3dZoomIn', 'zoom', 1.0, 0.0),
            ('−', 'viewer3dZoomOut', 'zoom', -1.0, 0.0),
            ('Đặt lại', 'viewer3dReset', 'reset', 0.0, 0.0),
        ):
            button = QPushButton(label, self)
            button.setObjectName(name)
            button.setToolTip('08.04 — Điều chỉnh góc nhìn, không thay đổi dữ liệu PLY')
            button.clicked.connect(lambda checked=False, a=action, x=dx, y=dy:
                                   self.navigation_requested.emit(a, x, y))
            button.setEnabled(False)
            nav_row.addWidget(button)
            self.navigation_buttons.append(button)
        self.axes_button = QPushButton('Trục XYZ', self)
        self.axes_button.setObjectName('viewer3dAxes')
        self.axes_button.setCheckable(True)
        self.axes_button.setEnabled(False)
        self.axes_button.setToolTip('Trục tham khảo trong khung PLY; không xác nhận world frame')
        self.axes_button.clicked.connect(lambda _checked=False:
                                          self.navigation_requested.emit('axes', 0.0, 0.0))
        nav_row.addWidget(self.axes_button)
        self.layer_button = QPushButton('Hiện lớp điểm', self)
        self.layer_button.setObjectName('viewer3dCloudLayer')
        self.layer_button.setToolTip('Ẩn/hiện duy nhất lớp point cloud đang xem; không ghi PLY')
        self.layer_button.setCheckable(True)
        self.layer_button.setChecked(True)
        self.layer_button.setEnabled(False)
        self.layer_button.toggled.connect(self._toggle_cloud_layer)
        nav_row.addWidget(self.layer_button)
        nav_row.addStretch(1)
        outer.addLayout(nav_row)
        self.state = QLabel('Đang chuẩn bị VTK fixture…', self)
        self.state.setObjectName('workspaceState')
        self.state.setWordWrap(True)
        self.state.setTextFormat(Qt.PlainText)
        outer.addWidget(self.state)
        self.surface = QFrame(self)
        self.surface.setObjectName('viewer3dSurface')
        self.surface_layout = QVBoxLayout(self.surface)
        self.surface_layout.setContentsMargins(0, 0, 0, 0)
        self.preview = NavigationPreview('Chưa có hình render VTK', self.surface)
        self.preview.gesture.connect(self.navigation_requested.emit)
        self.preview.point_clicked.connect(self.point_requested.emit)
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
        self.layer_label = QLabel('Lớp 1 · FIXTURE 08.02 · Chỉ một lớp dữ liệu', self)
        self.layer_label.setObjectName('viewer3dLayerInfo')
        outer.addWidget(self.layer_label)
        self.point_inspector = QFrame(self)
        self.point_inspector.setObjectName('viewer3dPointInspector')
        inspector_layout = QVBoxLayout(self.point_inspector)
        inspector_layout.setContentsMargins(9, 6, 9, 7)
        self.point_title = QLabel('Inspector điểm · Chưa chọn điểm', self.point_inspector)
        self.point_title.setObjectName('viewer3dPointTitle')
        inspector_layout.addWidget(self.point_title)
        self.point_info = QLabel('Nhấp chuột trái lên điểm · Kéo để xoay. Tọa độ chỉ là giá trị PLY/fixture.', self.point_inspector)
        self.point_info.setObjectName('viewer3dPointInfo')
        self.point_info.setTextFormat(Qt.PlainText)
        self.point_info.setWordWrap(True)
        inspector_layout.addWidget(self.point_info)
        outer.addWidget(self.point_inspector)
        self._image = QPixmap()

    def set_loading(self, active: bool) -> None:
        self.open_ply_button.setEnabled(not active)
        available = not active and not self._image.isNull()
        for button in self.navigation_buttons:
            button.setEnabled(available)
        self.axes_button.setEnabled(available)
        self.layer_button.setEnabled(available)
        self.preview.set_pick_enabled(available and self.layer_button.isChecked())

    def set_axes(self, visible: bool) -> None:
        self.axes_button.setChecked(bool(visible))

    def _toggle_cloud_layer(self, visible: bool) -> None:
        self.clear_point('Lớp điểm đang ẩn.' if not visible else 'Chưa chọn điểm.')
        self.preview.set_pick_enabled(visible and not self._image.isNull())
        if visible:
            self._fit_preview()
        else:
            self.preview.clear()
            self.preview.setText('Lớp điểm đã ẩn · bật Hiện lớp điểm để xem')
        self.layer_visibility_changed.emit(visible)

    def clear_point(self, text: str = 'Chưa chọn điểm.') -> None:
        self.preview.set_marker(None)
        self.point_title.setText('Inspector điểm · ' + text)
        self.point_info.setText('Không có tọa độ điểm được chọn. Đơn vị/hệ tọa độ chưa xác nhận.')

    def show_point(self, result: PickResult) -> None:
        if not result.hit:
            self.clear_point('Không tìm thấy điểm tại vị trí nhấn.')
            return
        self.point_title.setText(f'Inspector điểm · Point ID {result.point_id}')
        self.point_info.setText(
            f'X = {result.xyz[0]:.7g} · Y = {result.xyz[1]:.7g} · Z = {result.xyz[2]:.7g} · '
            + (f'RGB = {result.rgb}' if result.rgb is not None else 'RGB: không có')
            + ' · Đơn vị: chưa xác nhận · Hệ tọa độ: chưa xác nhận'
        )
        self.preview.set_marker(result.display_uv)

    def clear_preview(self, placeholder: str = 'Chưa có dữ liệu 3D',
                      note: str = 'Không có dữ liệu PLY đang hiển thị.') -> None:
        self._image = QPixmap()
        self.clear_point()
        self.layer_button.blockSignals(True)
        self.layer_button.setChecked(True)
        self.layer_button.blockSignals(False)
        self.set_loading(False)
        self.preview.clear()
        self.preview.setText(placeholder)
        self.note.setText(note)
        self.layer_label.setText('Lớp điểm: chưa có dữ liệu đang hiển thị')

    def show_failure(self, message: str) -> None:
        self.clear_preview('Không thể hiển thị PLY',
                           'Không có dữ liệu đang hiển thị · Tệp trước đó đã được bỏ khỏi Viewer.')
        self.set_status(message, is_error=True)

    def show_fixture(self) -> None:
        self.layer_label.setText('Lớp 1 · FIXTURE 08.02 · 5 điểm')
        self.note.setText('FIXTURE · 5 điểm tổng hợp · Không có đơn vị đo xác nhận · '
                          'Xoay: kéo trái · Pan: kéo phải · Zoom: cuộn chuột · '
                          'Ảnh VTK cập nhật theo từng thao tác')

    def show_ply(self, summary: PlySummary) -> None:
        self.layer_label.setText(f'Lớp 1 · {summary.name} · {summary.point_count:,} điểm')
        x0, x1, y0, y1, z0, z1 = summary.bounds
        self.note.setText(
            f'PLY: {summary.name} · {summary.point_count:,} điểm · '
            f'Bounds X[{x0:.4g}, {x1:.4g}] Y[{y0:.4g}, {y1:.4g}] Z[{z0:.4g}, {z1:.4g}] · '
            f'RGB: {"Có" if summary.has_rgb else "Không"} · '
            f'Đơn vị/hệ tọa độ: chưa xác nhận · Điều khiển góc nhìn 08.04 bằng thao tác rời rạc')

    def show_png(self, png_bytes: bytes) -> bool:
        image = QPixmap()
        if not png_bytes.startswith(b'\x89PNG\r\n\x1a\n') or not image.loadFromData(png_bytes, 'PNG'):
            return False
        self._image = image
        self._fit_preview()
        self.set_loading(False)
        return True

    def _fit_preview(self) -> None:
        if not self._image.isNull() and self.layer_button.isChecked():
            self.preview.setPixmap(self._image.scaled(
                self.preview.size(), Qt.KeepAspectRatio, Qt.SmoothTransformation))

    def resizeEvent(self, event) -> None:
        super().resizeEvent(event)
        self._fit_preview()

    def set_status(self, message: str, *, is_error: bool = False) -> None:
        self.state.setText(message)
        self.state.setToolTip(message)
        # The existing global QSS styles the ordinary workspaceState as success;
        # an invalid PLY must not appear as a green success banner.
        self.state.setStyleSheet(
            'QLabel#workspaceState { background: #fff0ee; color: #9f2630; '
            'border: 1px solid #e7b0b4; border-radius: 5px; padding: 7px 10px; }'
            if is_error else ''
        )
