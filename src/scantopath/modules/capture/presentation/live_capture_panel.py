"""GD2-09.07.2: a child panel inside the existing Capture Workspace.

Raw Replay panel remains completely separate and unaffected.
"""
from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QFrame, QHBoxLayout, QLabel, QPushButton, QSizePolicy, QSplitter, QVBoxLayout, QWidget,
)

from scantopath.modules.capture.domain.models import CameraState, DepthRoi, RoiSource
from .depth_roi_overlay import DepthRoiOverlay
from .live_3d_panel import Live3DPanel
from .preview_widget import owned_rgb_image
from .preview_widget import depth_display_u8
from scantopath.modules.geometry.application.live_visual_depth import StableDepthScale

from PySide6.QtGui import QPixmap


_FT056_DEFAULT_ROI = object()  # Backward-compatible optional display override.

class LiveCapturePanel(QFrame):
    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("captureLivePanel")
        self._manual: DepthRoi | None = None
        self._auto: DepthRoi | None = None
        self._rgb_original: QPixmap | None = None
        self._stable_depth_scale = StableDepthScale()
        self._live = False

        layout = QVBoxLayout(self)
        layout.setContentsMargins(12, 12, 12, 12)
        layout.setSpacing(9)
        bar = QHBoxLayout()
        title = QLabel("GEMINI 2 · LIVE RGB-D", self)
        title.setObjectName("captureLiveHeading")
        bar.addWidget(title)
        bar.addStretch(1)
        self.start_button = QPushButton("Kết nối", self)
        self.start_button.setObjectName("captureLiveStartButton")
        self.stop_button = QPushButton("Dừng", self)
        self.stop_button.setObjectName("captureLiveStopButton")
        self.retry_button = QPushButton("Thử lại", self)
        self.retry_button.setObjectName("captureLiveRetryButton")
        for button in (self.start_button, self.stop_button, self.retry_button):
            bar.addWidget(button)
        self.capture_button = QPushButton("Chụp và lưu", self)
        self.capture_button.setObjectName("captureLiveCommitButton")
        self.capture_button.setToolTip("Lưu keyframe vào phiên quét đang mở trong Cây dự án")
        self.capture_button.setEnabled(False)
        bar.addWidget(self.capture_button)
        self.auto_capture_button = QPushButton("Auto Keyframe: OFF", self)
        self.auto_capture_button.setObjectName("captureLiveAutoKeyframeButton")
        self.auto_capture_button.setCheckable(True)
        self.auto_capture_button.setEnabled(False)
        self.auto_capture_button.toggled.connect(
            lambda checked: self.auto_capture_button.setText(
                "Auto Keyframe: ON" if checked else "Auto Keyframe: OFF"
            )
        )
        bar.addWidget(self.auto_capture_button)
        layout.addLayout(bar)

        panes = QSplitter(Qt.Horizontal, self)
        self._camera_column = QWidget(panes)
        camera_layout = QVBoxLayout(self._camera_column)
        camera_layout.setContentsMargins(0, 0, 0, 0)
        camera_layout.setSpacing(3)
        self.camera_panes = QSplitter(Qt.Vertical, self._camera_column)
        self.camera_panes.setObjectName('captureLiveCameraSplitter')
        self.camera_panes.setChildrenCollapsible(False)
        camera_layout.addWidget(self.camera_panes, 1)
        left = QFrame(self._camera_column)
        left_layout = QVBoxLayout(left)
        left_layout.setContentsMargins(0, 0, 0, 0)
        left_layout.addWidget(QLabel("RGB live (không align)", left))
        self.rgb_image = QLabel("Chưa kết nối", left)
        self.rgb_image.setObjectName("captureLiveRgbImage")
        self.rgb_image.setAlignment(Qt.AlignCenter)
        self.rgb_image.setMinimumSize(135, 110)
        self.rgb_image.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        self.rgb_image.setStyleSheet("background:#171c24; color:#bec7d2;")
        left_layout.addWidget(self.rgb_image, 1)
        self.camera_panes.addWidget(left)

        right = QFrame(self._camera_column)
        right_layout = QVBoxLayout(right)
        right_layout.setContentsMargins(0, 0, 0, 0)
        right_layout.addWidget(QLabel("Depth live + ROI (tọa độ Depth)", right))
        self.depth_overlay = DepthRoiOverlay(right)
        self.depth_overlay.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        right_layout.addWidget(self.depth_overlay, 1)
        self.camera_panes.addWidget(right)
        self.camera_panes.setStretchFactor(0, 1)
        self.camera_panes.setStretchFactor(1, 1)
        self.camera_panes.setSizes([240, 240])
        panes.addWidget(self._camera_column)
        self.cloud_view = Live3DPanel(panes)
        panes.addWidget(self.cloud_view)
        panes.setObjectName('captureLiveMainSplitter')
        self.main_splitter = panes
        panes.setStretchFactor(0, 2)
        panes.setStretchFactor(1, 5)
        panes.setSizes([300, 700])
        panes.setChildrenCollapsible(False)
        layout.addWidget(panes, 1)

        tools = QHBoxLayout()
        self.manual_button = QPushButton("Chọn ROI thủ công", self)
        self.manual_button.setObjectName("captureLiveManualRoiButton")
        self.manual_button.setCheckable(True)
        self.auto_button = QPushButton("Dùng ROI tự động", self)
        self.auto_button.setObjectName("captureLiveAutoRoiButton")
        tools.addWidget(self.manual_button)
        tools.addWidget(self.auto_button)
        tools.addStretch(1)
        layout.addLayout(tools)
        self.roi_label = QLabel("ROI: chưa có", self)
        self.roi_label.setObjectName("captureLiveRoiStatus")
        self.roi_label.setWordWrap(True)
        self.state_label = QLabel("Camera: IDLE · Không mở thiết bị tự động", self)
        self.state_label.setObjectName("captureLiveState")
        layout.addWidget(self.roi_label)
        layout.addWidget(self.state_label)
        self.capture_context_label = QLabel("Chọn phiên quét đang mở để chụp và lưu.", self)
        self.capture_context_label.setObjectName("captureLiveContextLabel")
        self.capture_context_label.setWordWrap(True)
        layout.addWidget(self.capture_context_label)
        self.roi_safety_status = QLabel("ROI Safety: WAITING | chưa đánh giá Depth", self)
        self.roi_safety_status.setObjectName("captureLiveRoiSafetyStatus")
        self.roi_safety_status.setWordWrap(True)
        self.roi_safety_status.setToolTip(
            "Ngưỡng kiểm soát an toàn HS-01.4; không phải segmentation hay đo pose. "
            "Nếu ROI quá rộng, hãy chọn ROI thủ công theo ảnh Depth."
        )
        layout.addWidget(self.roi_safety_status)
        self.auto_capture_button.setToolTip(
            "Bật/tắt thu RAW tự động; tắt Auto không dừng camera. "
            "ROI không an toàn sẽ chặn yêu cầu tự động."
        )
        self.auto_capture_status = QLabel("Auto Keyframe: IDLE", self)
        self.auto_capture_status.setObjectName("captureLiveAutoKeyframeStatus")
        self.auto_capture_status.setWordWrap(True)
        layout.addWidget(self.auto_capture_status)
        # Keep essential ROI actions visible; collapse verbose diagnostics to
        # preserve usable RGB/Depth/3D area on 125%/150% DPI Windows screens.
        self.details_button = QPushButton('Thông tin chi tiết camera / ROI ▸', self)
        self.details_button.setObjectName('captureLiveDetailsToggle')
        self.details_button.setCheckable(True)
        layout.addWidget(self.details_button)
        self._detail_labels = (self.roi_label, self.state_label,
                               self.roi_safety_status, self.auto_capture_status)
        for label in self._detail_labels:
            label.setVisible(False)
        self.details_button.toggled.connect(self._toggle_details)
        self.manual_button.toggled.connect(self.depth_overlay.set_manual_enabled)
        self.depth_overlay.manual_roi_selected.connect(self._on_manual_selected)
        self.auto_button.clicked.connect(self.use_auto)
        self.set_state(CameraState.IDLE)

    def _toggle_details(self, visible: bool) -> None:
        for label in self._detail_labels:
            label.setVisible(visible)
        self.details_button.setText('Ẩn thông tin chi tiết ▾' if visible
                                    else 'Thông tin chi tiết camera / ROI ▸')

    @property
    def manual_roi(self) -> DepthRoi | None:
        return self._manual

    @property
    def displayed_roi(self) -> DepthRoi | None:
        return self.depth_overlay.roi

    def _on_manual_selected(self, roi: DepthRoi) -> None:
        self._manual = roi
        self._show_roi()

    def use_auto(self) -> None:
        self._manual = None
        self.manual_button.setChecked(False)
        self._show_roi()

    def set_auto_result(self, result, *, display_roi=_FT056_DEFAULT_ROI) -> None:
        # Display-only override; safety/Auto Capture receives original result.
        if display_roi is _FT056_DEFAULT_ROI:
            self._auto = result.roi if result is not None and result.usable else None
        elif display_roi is None or isinstance(display_roi, DepthRoi):
            self._auto = display_roi
        else:
            raise TypeError("DISPLAY_ROI_INVALID")
        reason = result.status.value if result is not None else "analysis_failed"
        confidence = f"{result.confidence:.2f}" if result is not None else "--"
        self._reason = f"{reason}; score={confidence} (chưa hiệu chuẩn)"
        self._show_roi()

    def _show_roi(self) -> None:
        roi = self._manual if self._manual is not None else self._auto
        if self.depth_overlay.image_size is not None:
            if roi is not None and (roi.frame_width, roi.frame_height) != self.depth_overlay.image_size:
                roi = None
            self.depth_overlay.set_roi(roi)
        if roi is None:
            self.roi_label.setText("ROI: chưa có · " + getattr(self, "_reason", "chưa phân tích"))
        else:
            source = "Manual" if roi.source is RoiSource.MANUAL else "Depth suggestion"
            self.roi_label.setText(
                f"{source}: ({roi.x}, {roi.y}, {roi.width}, {roi.height}) "
                f"/ {roi.frame_width}x{roi.frame_height} · "
                + getattr(self, "_reason", "")
            )

    def show_live_frame(self, frame) -> None:
        from scantopath.modules.capture.application.live_stream import LiveRgbdFrame
        if not isinstance(frame, LiveRgbdFrame):
            raise TypeError("expected owned LiveRgbdFrame")
        dimensions = (frame.source.depth_width, frame.source.depth_height)
        if self.depth_overlay.image_size not in (None, dimensions):
            # A new sensor grid invalidates any previously chosen manual ROI.
            self._manual = self._auto = None
            self.manual_button.setChecked(False)
        self._rgb_original = QPixmap.fromImage(owned_rgb_image(frame.color_rgb))
        self._fit_rgb()
        self.depth_overlay.set_depth_image(self._stable_depth_scale.update(frame.depth_u16))
        self._show_roi()

    def _fit_rgb(self) -> None:
        if self._rgb_original is not None and self.rgb_image.width() > 1 and self.rgb_image.height() > 1:
            self.rgb_image.setPixmap(self._rgb_original.scaled(
                self.rgb_image.size(), Qt.KeepAspectRatio, Qt.SmoothTransformation
            ))

    def resizeEvent(self, event) -> None:
        super().resizeEvent(event)
        if self._rgb_original is not None:
            from PySide6.QtCore import QTimer
            QTimer.singleShot(0, self._fit_rgb)

    def clear_live(self) -> None:
        self._stable_depth_scale.reset()
        self._rgb_original = None
        self.rgb_image.clear()
        self.rgb_image.setText("Chưa kết nối")
        self.depth_overlay.clear()
        self._manual = self._auto = None
        self._reason = "chưa phân tích"
        self.manual_button.setChecked(False)
        self._show_roi()

    def set_state(self, state: CameraState, error: str | None = None) -> None:
        self._live = state in (CameraState.STREAMING, CameraState.CAPTURING)
        self.start_button.setEnabled(state in (CameraState.IDLE, CameraState.CLOSED))
        self.stop_button.setEnabled(state in (CameraState.OPENING, CameraState.STREAMING, CameraState.CAPTURING))
        self.retry_button.setEnabled(state is CameraState.FAILED)
        self.manual_button.setEnabled(state is CameraState.STREAMING)
        self.auto_button.setEnabled(state is CameraState.STREAMING)
        self.state_label.setText(
            f"Camera: {state.value.upper()}" + (f" · Lỗi: {error}" if error else "")
        )
        if not self._live and self.manual_button.isChecked():
            self.manual_button.setChecked(False)
