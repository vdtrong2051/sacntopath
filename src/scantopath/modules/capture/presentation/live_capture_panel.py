"""GD2-09.07.2: a child panel inside the existing Capture Workspace.

Raw Replay panel remains completely separate and unaffected.
"""
from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QFrame, QHBoxLayout, QLabel, QPushButton, QSizePolicy, QVBoxLayout, QWidget,
)

from scantopath.modules.capture.domain.models import CameraState, DepthRoi, RoiSource
from .depth_roi_overlay import DepthRoiOverlay
from .preview_widget import owned_rgb_image
from .preview_widget import depth_display_u8

from PySide6.QtGui import QPixmap


class LiveCapturePanel(QFrame):
    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("captureLivePanel")
        self._manual: DepthRoi | None = None
        self._auto: DepthRoi | None = None
        self._rgb_original: QPixmap | None = None
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
        layout.addLayout(bar)

        panes = QHBoxLayout()
        left = QFrame(self)
        left_layout = QVBoxLayout(left)
        left_layout.setContentsMargins(0, 0, 0, 0)
        left_layout.addWidget(QLabel("RGB live (không align)", left))
        self.rgb_image = QLabel("Chưa kết nối", left)
        self.rgb_image.setObjectName("captureLiveRgbImage")
        self.rgb_image.setAlignment(Qt.AlignCenter)
        self.rgb_image.setMinimumSize(150, 200)
        self.rgb_image.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        self.rgb_image.setStyleSheet("background:#171c24; color:#bec7d2;")
        left_layout.addWidget(self.rgb_image, 1)
        panes.addWidget(left, 1)

        right = QFrame(self)
        right_layout = QVBoxLayout(right)
        right_layout.setContentsMargins(0, 0, 0, 0)
        right_layout.addWidget(QLabel("Depth live + ROI (tọa độ Depth)", right))
        self.depth_overlay = DepthRoiOverlay(right)
        self.depth_overlay.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        right_layout.addWidget(self.depth_overlay, 1)
        panes.addWidget(right, 1)
        layout.addLayout(panes, 1)

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
        self.manual_button.toggled.connect(self.depth_overlay.set_manual_enabled)
        self.depth_overlay.manual_roi_selected.connect(self._on_manual_selected)
        self.auto_button.clicked.connect(self.use_auto)
        self.set_state(CameraState.IDLE)

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

    def set_auto_result(self, result) -> None:
        # No stale box for ambiguous, acquiring, missing or failed tracking.
        self._auto = result.roi if result is not None and result.usable else None
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
        self.depth_overlay.set_depth_image(depth_display_u8(frame.depth_u16))
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
