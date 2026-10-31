"""R5.2 Qt-only live image and continuous gesture adapter.

No VTK, file I/O, or shared-memory references are allowed in this UI module.
"""
from __future__ import annotations

from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QImage, QPixmap

from .view import NavigationPreview
from ..application.picking import image_click_uv


class LiveNavigationPreview(NavigationPreview):
    """Preserves the existing viewer3dPreview identity and mouse API."""

    selection_drag_ignored = Signal()

    def __init__(self, text: str, parent=None):
        super().__init__(text, parent)
        self._last_pos = None
        self._dragged = False
        self.live_enabled = True
        self.interaction_mode = 'orbit'
        # GUI-only annotations of VTK-confirmed selections. Not geometry data.
        self._measurement_anchors = ()


    def set_measurement_anchors(self, anchors) -> None:
        """Store up to two normalized on-screen locations, labels A/B only."""
        import math
        if not isinstance(anchors, (tuple, list)) or len(anchors) > 2:
            raise ValueError('INVALID_MEASUREMENT_ANCHORS')
        accepted = []
        for index, item in enumerate(anchors):
            if (not isinstance(item, (tuple, list)) or len(item) != 2 or
                    item[0] != ('A', 'B')[index] or
                    not isinstance(item[1], (tuple, list)) or len(item[1]) != 2 or
                    any(isinstance(a, bool) or not isinstance(a, (float, int)) or
                        not math.isfinite(a) or not 0 <= a <= 1 for a in item[1])):
                raise ValueError('INVALID_MEASUREMENT_ANCHORS')
            accepted.append((item[0], (float(item[1][0]), float(item[1][1]))))
        self._measurement_anchors = tuple(accepted)
        self.update()

    def paintEvent(self, event) -> None:
        super().paintEvent(event)
        pix = self.pixmap()
        if not self._measurement_anchors or pix is None or pix.isNull():
            return
        from PySide6.QtCore import QPointF, QRectF
        from PySide6.QtGui import QColor, QPainter, QPen
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        x0 = (self.width() - pix.width()) / 2.0
        y0 = (self.height() - pix.height()) / 2.0
        positions = []
        for label, (u, v) in self._measurement_anchors:
            positions.append((label, QPointF(
                x0 + u * (pix.width() - 1),
                y0 + (1.0 - v) * (pix.height() - 1),
            )))
        if len(positions) == 2:
            painter.setPen(QPen(QColor('#f9e78b'), 3))
            painter.drawLine(positions[0][1], positions[1][1])
        for label, pos in positions:
            color = QColor('#ffbc40') if label == 'A' else QColor('#4ce9dc')
            painter.setPen(QPen(QColor('#142032'), 2))
            painter.setBrush(color)
            painter.drawEllipse(pos, 8, 8)
            # Keep a visible letter for both anchors, even on colored RAW data.
            side = -23.0 if label == 'A' else 7.0
            box = QRectF(pos.x() + side, pos.y() - 30.0, 19.0, 19.0)
            painter.setPen(QPen(color, 1))
            painter.setBrush(QColor('#142032'))
            painter.drawRoundedRect(box, 4, 4)
            painter.drawText(box, Qt.AlignCenter, label)
        painter.end()

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
                if self._button == Qt.LeftButton and self.interaction_mode == 'select':
                    # GD2-10.08.2: one pixel of pointer jitter is not a drag.
                    # Keep the initial press as the reference even across
                    # multiple mouseMoveEvents. Six pixels is a real drag.
                    origin = self._origin
                    if origin is not None:
                        offset = pos - origin
                        if offset.x() * offset.x() + offset.y() * offset.y() >= 36:
                            self._dragged = True
                else:
                    self._dragged = True
                    if self._button == Qt.LeftButton and self.interaction_mode != 'pan':
                        self.gesture.emit('orbit', delta.x() * .45, delta.y() * .45)
                    else:
                        self.gesture.emit('pan', float(delta.x()), float(delta.y()))
            event.accept()
            return
        super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event):
        if self.live_enabled and self._last_pos is not None and event.button() == self._button:
            was_click = not self._dragged and self._button == Qt.LeftButton
            was_select_drag = (self._dragged and self._button == Qt.LeftButton
                               and self.interaction_mode == 'select')
            self._last_pos = self._origin = self._button = None
            self._dragged = False
            if was_select_drag:
                self.selection_drag_ignored.emit()
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
