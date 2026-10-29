"""GD2-09.07.2: depth-pixel ROI overlay and mouse editor; display-only.

Depth and RGB are NOT registered. This widget uses only original depth-grid
coordinates, and QPixmap is an owned Qt copy of the diagnostic depth image.
"""
from __future__ import annotations

from math import ceil, floor

import numpy as np
from PySide6.QtCore import QPointF, QRect, QRectF, Qt, Signal
from PySide6.QtGui import QColor, QImage, QMouseEvent, QPainter, QPen, QPixmap
from PySide6.QtWidgets import QWidget

from scantopath.modules.capture.domain.models import DepthRoi, RoiSource
from .preview_widget import owned_depth_image


class DepthRoiOverlay(QWidget):
    manual_roi_selected = Signal(object)  # DepthRoi in unaligned DEPTH pixels

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("captureLiveDepthOverlay")
        self.setMinimumSize(150, 200)
        self.setMouseTracking(True)
        self.setCursor(Qt.CrossCursor)
        self._pixmap: QPixmap | None = None
        self._size: tuple[int, int] | None = None
        self._roi: DepthRoi | None = None
        self._manual_enabled = False
        self._drag_start: QPointF | None = None
        self._drag_current: QPointF | None = None

    @property
    def roi(self) -> DepthRoi | None:
        return self._roi

    @property
    def image_size(self) -> tuple[int, int] | None:
        return self._size

    def image_rect(self) -> QRectF:
        """Drawing rectangle including letterbox margins (KeepAspectRatio)."""
        if self._size is None:
            return QRectF()
        width, height = self._size
        if self.width() < 1 or self.height() < 1:
            return QRectF()
        ratio = min(self.width() / width, self.height() / height)
        dw, dh = width * ratio, height * ratio
        return QRectF((self.width() - dw) / 2, (self.height() - dh) / 2, dw, dh)

    def image_to_widget(self, x: float, y: float) -> QPointF:
        if self._size is None:
            raise RuntimeError("depth image not loaded")
        rect = self.image_rect()
        w, h = self._size
        return QPointF(rect.left() + x * rect.width() / w,
                       rect.top() + y * rect.height() / h)

    def _to_image(self, position: QPointF, *, clamp: bool) -> QPointF | None:
        if self._size is None:
            return None
        rect = self.image_rect()
        if rect.isEmpty():
            return None
        if not clamp and not rect.contains(position):
            return None
        x = (position.x() - rect.left()) / rect.width() * self._size[0]
        y = (position.y() - rect.top()) / rect.height() * self._size[1]
        return QPointF(max(0.0, min(self._size[0], x)),
                       max(0.0, min(self._size[1], y)))

    def set_depth_image(self, gray: np.ndarray) -> None:
        if not isinstance(gray, np.ndarray) or gray.ndim != 2 or gray.dtype != np.uint8:
            raise ValueError("depth visualization must be uint8 HxW")
        height, width = gray.shape
        if not height or not width:
            raise ValueError("empty depth visualization")
        dimensions = (width, height)
        if self._size is not None and self._size != dimensions:
            self._roi = None
            self._drag_start = self._drag_current = None
        self._size = dimensions
        # The QImage function returns an owning copy; QPixmap owns its pixels.
        self._pixmap = QPixmap.fromImage(owned_depth_image(gray))
        self.update()

    def set_roi(self, roi: DepthRoi | None) -> None:
        if roi is not None and not isinstance(roi, DepthRoi):
            raise TypeError("ROI must be a DepthRoi")
        if roi is not None and (self._size is None or
                                (roi.frame_width, roi.frame_height) != self._size):
            raise ValueError("ROI does not match depth image grid")
        self._roi = roi
        self.update()

    def set_manual_enabled(self, enabled: bool) -> None:
        self._manual_enabled = bool(enabled)
        if not enabled:
            self._drag_start = self._drag_current = None
        self.update()

    def clear(self) -> None:
        self._pixmap = None
        self._size = None
        self._roi = None
        self._drag_start = self._drag_current = None
        self._manual_enabled = False
        self.update()

    def _finish_drag(self) -> None:
        if self._size is None or self._drag_start is None or self._drag_current is None:
            return
        p0 = self._to_image(self._drag_start, clamp=True)
        p1 = self._to_image(self._drag_current, clamp=True)
        if p0 is None or p1 is None:
            return
        width, height = self._size
        x0, y0 = floor(min(p0.x(), p1.x())), floor(min(p0.y(), p1.y()))
        x1, y1 = ceil(max(p0.x(), p1.x())), ceil(max(p0.y(), p1.y()))
        x0, y0 = max(0, x0), max(0, y0)
        x1, y1 = min(width, x1), min(height, y1)
        if x1 - x0 < 2 or y1 - y0 < 2:
            return
        roi = DepthRoi(x0, y0, x1 - x0, y1 - y0, width, height, RoiSource.MANUAL)
        self._roi = roi
        self.manual_roi_selected.emit(roi)

    def mousePressEvent(self, event: QMouseEvent) -> None:
        if (self._manual_enabled and event.button() == Qt.LeftButton
                and self._to_image(event.position(), clamp=False) is not None):
            self._drag_start = event.position()
            self._drag_current = event.position()
            self.update()
            event.accept()
        else:
            super().mousePressEvent(event)

    def mouseMoveEvent(self, event: QMouseEvent) -> None:
        if self._drag_start is not None:
            self._drag_current = event.position()
            self.update()
            event.accept()
        else:
            super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event: QMouseEvent) -> None:
        if self._drag_start is not None and event.button() == Qt.LeftButton:
            self._drag_current = event.position()
            try:
                self._finish_drag()
            finally:
                self._drag_start = self._drag_current = None
                self.update()
            event.accept()
        else:
            super().mouseReleaseEvent(event)

    def paintEvent(self, event) -> None:
        painter = QPainter(self)
        painter.fillRect(self.rect(), QColor("#171c24"))
        if self._pixmap is None or self._size is None:
            painter.setPen(QColor("#bec7d2"))
            painter.drawText(self.rect(), Qt.AlignCenter, "Chưa tải Depth")
            return
        rect = self.image_rect()
        painter.setRenderHint(QPainter.SmoothPixmapTransform)
        painter.drawPixmap(rect, self._pixmap, QRectF(self._pixmap.rect()))

        if self._roi is not None:
            roi = self._roi
            p0 = self.image_to_widget(roi.x, roi.y)
            p1 = self.image_to_widget(roi.x + roi.width, roi.y + roi.height)
            box = QRectF(p0, p1).normalized()
            painter.setPen(QPen(QColor("#51dd98") if roi.source is RoiSource.MANUAL
                                 else QColor("#f3c15e"), 2))
            painter.setBrush(Qt.NoBrush)
            painter.drawRect(box)
        if self._drag_start is not None and self._drag_current is not None:
            a = self._to_image(self._drag_start, clamp=True)
            b = self._to_image(self._drag_current, clamp=True)
            if a is not None and b is not None:
                box = QRectF(self.image_to_widget(a.x(), a.y()),
                             self.image_to_widget(b.x(), b.y())).normalized()
                painter.setPen(QPen(QColor("#51dd98"), 2, Qt.DashLine))
                painter.setBrush(Qt.NoBrush)
                painter.drawRect(box)
