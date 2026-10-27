"""R5.2 Qt-only live image and continuous gesture adapter.

No VTK, file I/O, or shared-memory references are allowed in this UI module.
"""
from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtGui import QImage, QPixmap

from .view import NavigationPreview
from ..application.picking import image_click_uv


class LiveNavigationPreview(NavigationPreview):
    """Preserves the existing viewer3dPreview identity and mouse API."""

    def __init__(self, text: str, parent=None):
        super().__init__(text, parent)
        self._last_pos = None
        self._dragged = False
        self.live_enabled = True
        self.interaction_mode = 'orbit'

    def mousePressEvent(self, event):
        if (self.live_enabled and event.button() in (Qt.LeftButton, Qt.RightButton, Qt.MiddleButton)
                and self.pixmap() is not None and not self.pixmap().isNull()):
            self._origin = event.position().toPoint()
            self._last_pos = self._origin
            self._button = event.button()
            self._dragged = False
            event.accept()
            return
        super().mousePressEvent(event)

    def mouseMoveEvent(self, event):
        if self.live_enabled and self._last_pos is not None and self._button is not None:
            pos = event.position().toPoint()
            delta = pos - self._last_pos
            self._last_pos = pos
            if delta.x() or delta.y():
                self._dragged = True
                if self._button == Qt.LeftButton and self.interaction_mode == 'select':
                    pass  # Drag in selection mode never moves the camera or picks.
                elif self._button == Qt.LeftButton and self.interaction_mode != 'pan':
                    self.gesture.emit('orbit', delta.x() * .45, delta.y() * .45)
                else:
                    self.gesture.emit('pan', float(delta.x()), float(delta.y()))
            event.accept()
            return
        super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event):
        if self.live_enabled and self._last_pos is not None and event.button() == self._button:
            was_click = not self._dragged and self._button == Qt.LeftButton
            self._last_pos = self._origin = self._button = None
            self._dragged = False
            if was_click and self._pick_enabled and self.interaction_mode == 'select':
                pix = self.pixmap()
                if pix is not None and not pix.isNull():
                    try:
                        uv = image_click_uv(float(event.position().x()), float(event.position().y()),
                                            self.width(), self.height(), pix.width(), pix.height())
                    except ValueError:
                        uv = None
                    if uv is not None:
                        self.point_clicked.emit(*uv)
            event.accept()
            return
        super().mouseReleaseEvent(event)

    def cancel_drag(self):
        self._last_pos = self._origin = self._button = None
        self._dragged = False


def rgb_snapshot_to_pixmap(frame) -> QPixmap:
    """Copy immutable bottom-up VTK RGB24 pixels into a Qt-owned QImage.

    Shared memory has already been copied and ACKed by the R4.3 worker.
    This never holds a raw memoryview past the caller's scope.
    """
    width, height = frame.width, frame.height
    if (type(width) is not int or type(height) is not int or
            not 128 <= width <= 1024 or not 128 <= height <= 1024 or
            type(frame.rgb) is not bytes or len(frame.rgb) != width * height * 3):
        raise ValueError('INVALID_RGB_FRAME')
    image = QImage(frame.rgb, width, height, width * 3, QImage.Format_RGB888)
    if image.isNull():
        raise ValueError('INVALID_QT_IMAGE')
    # VTK GetRGBImage stores row 0 at the bottom; QLabel expects top-left origin.
    return QPixmap.fromImage(image.copy().flipped(Qt.Vertical))
