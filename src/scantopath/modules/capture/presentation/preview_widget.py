
"""GD2-09.04: 2D RGB-D preview inside the existing Capture Workspace.

The widget receives decoded arrays only. It never opens SQLite, RAW or SDK.
"""
from __future__ import annotations

import numpy as np

from PySide6.QtCore import Qt, QTimer
from PySide6.QtGui import QImage, QPixmap
from PySide6.QtWidgets import (
    QFrame, QHBoxLayout, QLabel, QPushButton,
    QSizePolicy, QVBoxLayout, QWidget,
)

from scantopath.modules.capture.application.contracts import CaptureContext
from scantopath.modules.capture.application.decoding import DecodedRgbdFrame


def depth_display_u8(depth: np.ndarray) -> np.ndarray:
    """Diagnostic visualization; zero is invalid, NOT metric geometry."""
    if (
        not isinstance(depth, np.ndarray)
        or depth.ndim != 2
        or depth.dtype != np.uint16
    ):
        raise ValueError("Expected depth uint16 HxW")

    gray = np.zeros(depth.shape, dtype=np.uint8)
    valid = depth > 0

    if np.any(valid):
        values = depth[valid]
        lo, hi = np.percentile(values, (2.0, 98.0))

        if hi <= lo:
            gray[valid] = 180
        else:
            scaled = 255.0 * (
                1.0 - np.clip(
                    (values.astype(np.float32) - lo) / (hi - lo),
                    0.0,
                    1.0,
                )
            )
            gray[valid] = scaled.astype(np.uint8)

    gray.setflags(write=False)
    return gray


def owned_rgb_image(rgb: np.ndarray) -> QImage:
    """QImage owns its pixels after this function returns."""
    if (
        not isinstance(rgb, np.ndarray)
        or rgb.dtype != np.uint8
        or rgb.ndim != 3
        or rgb.shape[2] != 3
    ):
        raise ValueError("Expected RGB uint8 HxWx3")

    array = np.ascontiguousarray(rgb)
    h, w, _ = array.shape

    image = QImage(
        array.data,
        w,
        h,
        int(array.strides[0]),
        QImage.Format_RGB888,
    )
    return image.copy()


def owned_depth_image(gray: np.ndarray) -> QImage:
    if (
        not isinstance(gray, np.ndarray)
        or gray.dtype != np.uint8
        or gray.ndim != 2
    ):
        raise ValueError("Expected grayscale uint8 HxW")

    array = np.ascontiguousarray(gray)
    h, w = array.shape

    image = QImage(
        array.data,
        w,
        h,
        int(array.strides[0]),
        QImage.Format_Grayscale8,
    )
    return image.copy()


class CapturePreviewWidget(QFrame):
    """One child panel; the shell still owns the four existing workspaces."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("capturePreview")
        self.setAccessibleName("Phát lại RGB và độ sâu")

        self._context: CaptureContext | None = None
        self._busy = False
        self._rgb_pixmap: QPixmap | None = None
        self._depth_pixmap: QPixmap | None = None

        root = QVBoxLayout(self)
        root.setContentsMargins(12, 12, 12, 12)
        root.setSpacing(10)

        header = QHBoxLayout()
        header.setSpacing(8)

        title = QLabel("PHÁT LẠI RGB-D", self)
        title.setObjectName("capturePreviewHeading")
        header.addWidget(title)

        header.addStretch(1)

        self.replay_button = QPushButton("Phát lại RAW", self)
        self.replay_button.setObjectName("captureReplayButton")
        self.replay_button.setEnabled(False)
        header.addWidget(self.replay_button)

        root.addLayout(header)

        self.context_label = QLabel("Chưa chọn bản thu.", self)
        self.context_label.setObjectName("captureContextLabel")
        self.context_label.setWordWrap(True)
        root.addWidget(self.context_label)

        previews = QHBoxLayout()
        previews.setSpacing(10)

        def make_pane(title_text: str, object_name: str):
            pane = QFrame(self)
            pane.setFrameShape(QFrame.StyledPanel)
            pane.setSizePolicy(
                QSizePolicy.Expanding,
                QSizePolicy.Expanding,
            )
            layout = QVBoxLayout(pane)
            layout.setContentsMargins(8, 8, 8, 8)
            layout.setSpacing(7)

            caption = QLabel(title_text, pane)
            layout.addWidget(caption)

            image = QLabel("Chưa tải ảnh", pane)
            image.setObjectName(object_name)
            image.setAlignment(Qt.AlignCenter)
            image.setMinimumSize(150, 200)
            image.setSizePolicy(
                QSizePolicy.Expanding,
                QSizePolicy.Expanding,
            )
            image.setStyleSheet(
                "background-color: #171c24; color: #bec7d2;"
            )

            layout.addWidget(image, 1)
            return pane, image

        rgb_pane, self.rgb_image = make_pane(
            "Ảnh RGB — màu gốc",
            "captureRgbImage",
        )
        depth_pane, self.depth_image = make_pane(
            "Depth — thang xám chẩn đoán",
            "captureDepthImage",
        )

        previews.addWidget(rgb_pane, 1)
        previews.addWidget(depth_pane, 1)
        root.addLayout(previews, 1)

        self.metadata_label = QLabel(
            "RGB: —   |   Depth: —   |   Scale: —",
            self,
        )
        self.metadata_label.setObjectName("captureMetadataLabel")
        self.metadata_label.setWordWrap(True)
        root.addWidget(self.metadata_label)

        self.state_label = QLabel(
            "Chưa tải dữ liệu · Chưa khởi động camera",
            self,
        )
        self.state_label.setObjectName("capturePreviewState")
        self.state_label.setWordWrap(True)
        root.addWidget(self.state_label)

        self.setMinimumHeight(365)

    @property
    def context(self) -> CaptureContext | None:
        return self._context

    def _clear_images(self) -> None:
        self._rgb_pixmap = None
        self._depth_pixmap = None

        self.rgb_image.clear()
        self.depth_image.clear()

        self.rgb_image.setText("Chưa tải ảnh")
        self.depth_image.setText("Chưa tải ảnh")

        self.metadata_label.setText(
            "RGB: —   |   Depth: —   |   Scale: —"
        )

    def _refresh_button(self) -> None:
        self.replay_button.setEnabled(
            self._context is not None and not self._busy
        )

    def set_context(self, context: CaptureContext | None) -> None:
        self._context = context
        self._clear_images()

        if context is None:
            self.context_label.setText("Chưa chọn bản thu.")
            self.state_label.setText(
                "Chưa tải dữ liệu · Chưa khởi động camera"
            )
        else:
            self.context_label.setText(
                f"Project: {context.project_id}  |  "
                f"Session: {context.session_id}  |  "
                f"Capture: {context.capture_id}"
            )
            self.state_label.setText(
                "Đã chọn Capture. Nhấn Phát lại RAW để tải."
            )

        self._refresh_button()

    def set_busy(self, busy: bool) -> None:
        self._busy = bool(busy)
        self._refresh_button()

        if busy:
            self.state_label.setText(
                "Đang đọc và giải mã RAW trong luồng nền…"
            )

    def show_frame(
        self,
        frame: DecodedRgbdFrame,
        depth_gray: np.ndarray,
    ) -> None:
        if not isinstance(frame, DecodedRgbdFrame):
            raise TypeError("Expected DecodedRgbdFrame")

        if (
            not isinstance(depth_gray, np.ndarray)
            or depth_gray.dtype != np.uint8
            or depth_gray.shape != frame.depth_u16.shape
        ):
            raise ValueError("Invalid depth display image")

        self._rgb_pixmap = QPixmap.fromImage(
            owned_rgb_image(frame.color_rgb)
        )
        self._depth_pixmap = QPixmap.fromImage(
            owned_depth_image(depth_gray)
        )

        self._fit_images()

        meta = frame.metadata
        self.metadata_label.setText(
            f"RGB: {meta.color.width} × {meta.color.height}  |  "
            f"Depth: {meta.depth.width} × {meta.depth.height}  |  "
            f"Scale: {meta.depth_scale_m_per_unit:g} m/unit"
        )

        source = "Camera" if meta.measured else "Fixture tổng hợp"
        self.state_label.setText(
            f"Đã phát lại RAW v2 · Capture {meta.capture_id} · "
            f"Nguồn: {source} · Không căn chỉnh RGB/Depth"
        )

    def show_error(self, message: str) -> None:
        self._clear_images()
        self.state_label.setText(message)

    def _fit_images(self) -> None:
        for label, original in (
            (self.rgb_image, self._rgb_pixmap),
            (self.depth_image, self._depth_pixmap),
        ):
            if original is None:
                continue

            target = label.size()

            if target.width() < 2 or target.height() < 2:
                continue

            scaled = original.scaled(
                target,
                Qt.KeepAspectRatio,
                Qt.SmoothTransformation,
            )
            label.setPixmap(scaled)

    def resizeEvent(self, event) -> None:
        super().resizeEvent(event)
        QTimer.singleShot(0, self._fit_images)
