"""FT-05 compact embedded live 3D Qt viewport. Never imports VTK or SDK."""
from __future__ import annotations

from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QImage, QPixmap
from PySide6.QtWidgets import QCheckBox, QComboBox, QFrame, QHBoxLayout, QLabel, QPushButton, QVBoxLayout


class _CloudImage(QLabel):
    intent = Signal(str, float, float)

    def __init__(self, parent=None):
        super().__init__('3D chưa kết nối', parent)
        self.setAlignment(Qt.AlignCenter)
        self.setMinimumSize(240, 180)
        self.setStyleSheet('background: #111923; color: #d3dfed;')
        self._original: QPixmap | None = None
        self._pos = None
        self.setMouseTracking(True)

    def set_render(self, rgb: bytes, width: int, height: int):
        if (type(rgb) is not bytes or type(width) is not int or type(height) is not int
                or width <= 0 or height <= 0 or len(rgb) != width * height * 3):
            raise ValueError('FT05_INVALID_RGB_FRAME')
        # Own a Qt-side copy before the worker replaces its latest RGB snapshot.
        image = QImage(rgb, width, height, width * 3, QImage.Format_RGB888).copy()
        # VTK's RGB24 rows are bottom-up; QImage expects top-down.
        self._original = QPixmap.fromImage(image.mirrored(False, True))
        self._fit()

    def clear(self, message: str = '3D chưa kết nối') -> None:
        self._original = None
        self._pos = None
        self.setPixmap(QPixmap())
        self.setText(message)

    def _fit(self) -> None:
        if self._original is not None and self.width() > 1 and self.height() > 1:
            self.setPixmap(self._original.scaled(self.size(), Qt.KeepAspectRatio,
                                                 Qt.SmoothTransformation))

    def resizeEvent(self, event) -> None:
        super().resizeEvent(event)
        self._fit()

    def mousePressEvent(self, event) -> None:
        if self._original is not None and event.button() in (Qt.LeftButton, Qt.MiddleButton):
            self._pos = event.position()
            event.accept()
        else:
            super().mousePressEvent(event)

    def mouseMoveEvent(self, event) -> None:
        if self._pos is None or self._original is None:
            return super().mouseMoveEvent(event)
        now = event.position()
        delta = now - self._pos
        self._pos = now
        if event.buttons() & Qt.MiddleButton or event.modifiers() & Qt.ShiftModifier:
            self.intent.emit('pan', float(delta.x()), float(delta.y()))
        else:
            self.intent.emit('orbit', float(delta.x()) * 0.35, float(delta.y()) * 0.35)
        event.accept()

    def mouseReleaseEvent(self, event) -> None:
        self._pos = None
        super().mouseReleaseEvent(event)

    def wheelEvent(self, event) -> None:
        if self._original is None:
            return super().wheelEvent(event)
        self.intent.emit('zoom', float(event.angleDelta().y()) / 120.0, 0.0)
        event.accept()


class Live3DPanel(QFrame):
    """One viewer alongside the existing RGB/Depth/ROI; no extra application window."""
    camera_intent = Signal(str, float, float)
    denoise_mode_changed = Signal(str)
    scope_mode_changed = Signal(str)
    reference_mode_changed = Signal(str)
    enhancement_mode_changed = Signal(str)
    freeze_requested = Signal()
    resume_requested = Signal()
    snapshot_requested = Signal()

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.setObjectName('captureLive3DPanel')
        self.setMinimumWidth(240)
        lay = QVBoxLayout(self)
        lay.setContentsMargins(4, 4, 4, 4)
        lay.setSpacing(6)
        header = QHBoxLayout()
        title = QLabel('LIVE 3D · XYZ đơn frame', self)
        title.setObjectName('captureLive3DHeading')
        header.addWidget(title)
        header.addStretch(1)
        self.scope_mode = QComboBox(self)
        self.scope_mode.setObjectName("captureLive3DScopeMode")
        self.scope_mode.addItem("Vật thể", "object")
        self.scope_mode.addItem("Toàn cảnh", "scene")
        self.scope_mode.setToolTip("Vật thể: tách khỏi mặt nền nếu đủ tin cậy; Toàn cảnh: giữ toàn bộ ROI")
        self.scope_mode.currentIndexChanged.connect(
            lambda _i: self.scope_mode_changed.emit(str(self.scope_mode.currentData())))
        header.addWidget(self.scope_mode)
        self.reference_mode = QComboBox(self)
        self.reference_mode.setObjectName("captureLive3DReferenceMode")
        self.reference_mode.addItem("ChArUco", "charuco")
        self.reference_mode.addItem("Hình học Depth", "depth")
        self.reference_mode.setToolTip("ChArUco: dùng bảng chuẩn; Hình học Depth: FT-05.7 độc lập")
        self.reference_mode.currentIndexChanged.connect(
            lambda _i: self.reference_mode_changed.emit(str(self.reference_mode.currentData())))
        self.scope_mode.currentIndexChanged.connect(
            lambda _i: self.reference_mode.setEnabled(self.scope_mode.currentData() == "object"))
        header.addWidget(self.reference_mode)
        self.denoise_toggle = QCheckBox("Lọc 3D", self)
        self.denoise_toggle.setObjectName("captureLive3DDenoise")
        self.denoise_toggle.setChecked(True)
        self.denoise_toggle.setToolTip("Chỉ lọc Live 3D; RAW gốc không đổi")
        self.denoise_toggle.toggled.connect(
            lambda checked: self.denoise_mode_changed.emit("standard" if checked else "off"))
        header.addWidget(self.denoise_toggle)
        self.reset_button = QPushButton('Góc mặc định', self)
        self.reset_button.setObjectName('captureLive3DResetButton')
        self.reset_button.clicked.connect(lambda: self.camera_intent.emit('reset', 0.0, 0.0))
        header.addWidget(self.reset_button)
        lay.addLayout(header)
        self.image = _CloudImage(self)
        self.image.setObjectName('captureLive3DImage')
        self.image.intent.connect(self.camera_intent.emit)
        lay.addWidget(self.image, 1)
        # Main workflow actions stay next to the viewer, visible without scrolling.
        actions = QHBoxLayout()
        self.freeze_button = QPushButton('Đóng băng', self)
        self.freeze_button.setObjectName('captureLiveFreezeButton')
        self.freeze_button.clicked.connect(self.freeze_requested.emit)
        self.resume_button = QPushButton('Tiếp tục Live', self)
        self.resume_button.setObjectName('captureLiveResumeButton')
        self.resume_button.clicked.connect(self.resume_requested.emit)
        self.snapshot_button = QPushButton('Lưu Snapshot (.ply)', self)
        self.snapshot_button.setObjectName('captureLiveSnapshotButton')
        self.snapshot_button.clicked.connect(self.snapshot_requested.emit)
        for widget in (self.freeze_button, self.resume_button, self.snapshot_button):
            actions.addWidget(widget)
        self.enhance_toggle = QCheckBox('Mượt + lấp lỗ', self)
        self.enhance_toggle.setObjectName('captureLiveVisualDepthEnhancement')
        self.enhance_toggle.setChecked(True)
        self.enhance_toggle.setToolTip('Chỉ Geometry hiển thị; điểm bổ sung được đánh dấu trong Snapshot; RAW không đổi')
        self.enhance_toggle.toggled.connect(
            lambda enabled: self.enhancement_mode_changed.emit('visual' if enabled else 'off'))
        actions.addWidget(self.enhance_toggle)
        actions.addStretch(1)
        lay.addLayout(actions)
        self.geometry_info = QLabel('Điểm: —  •  Kích thước XYZ: —  •  Chưa đóng băng', self)
        self.geometry_info.setObjectName('captureLiveGeometryInspection')
        self.geometry_info.setWordWrap(True)
        self.geometry_info.setToolTip('Kích thước bao của bề mặt thấy trong frame, không phải kích thước vật thể hoàn chỉnh')
        lay.addWidget(self.geometry_info)
        self.tracking_info = QLabel('Vật thể: chưa theo dõi', self)
        self.tracking_info.setObjectName('captureLiveObjectTrackingStatus')
        self.tracking_info.setToolTip('Khung xanh lam chỉ phục vụ quan sát; Auto Keyframe vẫn dùng ROI Safety cũ')
        self.tracking_info.setWordWrap(True)
        lay.addWidget(self.tracking_info)
        self.status = QLabel('Viewer: chưa kết nối', self)
        self.status.setObjectName('captureLive3DStatus')
        self.status.setWordWrap(True)
        lay.addWidget(self.status)
        self.scope = QLabel('Phạm vi: Toàn ảnh Depth', self)
        self.scope.setObjectName('captureLive3DScope')
        self.scope.setWordWrap(True)
        lay.addWidget(self.scope)
        self.help = QLabel('Kéo trái: xoay · Shift+kéo: dịch · Cuộn: phóng to', self)
        self.help.setObjectName('captureLive3DHelp')
        self.help.setWordWrap(True)
        lay.addWidget(self.help)
        self.set_ready(False)
        self.set_snapshot_state('idle')

    def set_ready(self, ready: bool) -> None:
        self.reset_button.setEnabled(ready)

    def set_snapshot_state(self, state: str) -> None:
        self.freeze_button.setEnabled(state == 'live')
        self.resume_button.setEnabled(state == 'frozen')
        self.snapshot_button.setEnabled(state == 'frozen')
        self.snapshot_button.setText('Lưu Snapshot (.ply)' if state != 'saving' else 'Đang lưu…')

    def clear(self, reason: str = 'Chưa kết nối') -> None:
        self.image.clear('Chưa có Live Point Cloud')
        self.status.setText('Viewer: ' + reason)
        self.set_ready(False)
        self.set_snapshot_state('idle')
        self.geometry_info.setText('Điểm: —  •  Kích thước XYZ: —  •  Chưa đóng băng')

    def show_frame(self, rgb: bytes, width: int, height: int, points: int | None = None) -> None:
        self.image.set_render(rgb, width, height)
        suffix = f' · {points:,} điểm' if points is not None else ''
        self.status.setText('Viewer: Đang hiển thị · depth_optical · mét' + suffix)
        self.set_ready(True)
