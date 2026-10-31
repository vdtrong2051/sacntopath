"""Depth-aligned A/B picker: no Render Host, Qt viewport pick, or RAW I/O.

Clicks address the Depth optical pixel grid, then original float64 XYZ rows.
Only source-backed, PROVISIONAL single-view measurement is supported.
"""
from __future__ import annotations

from PySide6.QtCore import QPointF, QRectF, Qt, Signal
from PySide6.QtGui import QColor, QImage, QPainter, QPen
from PySide6.QtWidgets import QDialog, QHBoxLayout, QLabel, QPushButton, QVBoxLayout, QWidget

from scantopath.modules.geometry.application.depth_pixel_picker import DepthPixelPicker
from scantopath.modules.geometry.application.measurements import (
    MeasurementError, select_measurement_point, measure_selected_points,
)


class DepthSelectorCanvas(QWidget):
    pixel_clicked = Signal(int, int)

    def __init__(self, image: QImage, parent=None):
        super().__init__(parent)
        self.image = image
        self.markers: list[tuple[str, int, int]] = []
        self.setMinimumSize(580, 380)
        self.setMouseTracking(True)

    def image_rect(self) -> QRectF:
        area = self.contentsRect()
        factor = min(area.width() / self.image.width(), area.height() / self.image.height())
        dw = self.image.width() * factor
        dh = self.image.height() * factor
        return QRectF(area.x() + (area.width()-dw)/2,
                      area.y() + (area.height()-dh)/2, dw, dh)

    def mouseReleaseEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            pos = event.position()
            rect = self.image_rect()
            if rect.contains(pos):
                u = min(self.image.width()-1, max(0, int((pos.x()-rect.x()) * self.image.width()/rect.width())))
                v = min(self.image.height()-1, max(0, int((pos.y()-rect.y()) * self.image.height()/rect.height())))
                self.pixel_clicked.emit(u, v)
                event.accept()
                return
        super().mouseReleaseEvent(event)

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.fillRect(self.rect(), QColor(22, 31, 43))
        rect = self.image_rect()
        painter.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform, False)
        painter.drawImage(rect, self.image)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        for label, u, v in self.markers:
            x = rect.x() + (u+0.5)*rect.width()/self.image.width()
            y = rect.y() + (v+0.5)*rect.height()/self.image.height()
            color = QColor('#ffd84d') if label == 'A' else QColor('#28e4d2')
            painter.setPen(QPen(QColor('black'), 5))
            painter.drawEllipse(QPointF(x,y), 8, 8)
            painter.setPen(QPen(color, 3))
            painter.drawEllipse(QPointF(x,y), 8, 8)
            painter.setPen(QPen(color, 2))
            painter.drawText(QPointF(x+11, y-10), label)
        painter.end()


class DepthTwoPointDialog(QDialog):
    """One A and one B via independent, synchronous depth-pixel selection."""

    def __init__(self, view, parent=None):
        super().__init__(parent)
        self.setWindowTitle('Đo A–B trên ảnh Depth — khoảng cách 3D')
        self.setObjectName('uxhDepthTwoPointDialog')
        self.picker = DepthPixelPicker(view)
        self._view = view
        self.first = None
        self.result = None
        rgb = self.picker.make_rgb_depth_image()
        image = QImage(rgb.data, self.picker.width, self.picker.height,
                       rgb.strides[0], QImage.Format.Format_RGB888).copy()
        self.canvas = DepthSelectorCanvas(image, self)
        self.canvas.setObjectName('uxhDepthSelectorCanvas')
        self.status = QLabel('BƯỚC 1/2: Chọn A trên ảnh Depth. Vùng đen là Depth không hợp lệ.', self)
        self.status.setObjectName('uxhDepthMeasureStatus')
        self.status.setWordWrap(True)
        caption = QLabel(
            f'RAW Depth {self.picker.width} × {self.picker.height} | '
            'tọa độ depth_optical (m), khoảng cách Euclid 3D. '
            'Điểm có màu dùng RGB thật; điểm xám vẫn có Depth. '
            'PROVISIONAL_NOT_METRIC_VALIDATED.', self)
        caption.setWordWrap(True)
        self.reset_button = QPushButton('Chọn lại A/B', self)
        self.done_button = QPushButton('Sử dụng kết quả', self)
        self.done_button.setEnabled(False)
        self.cancel_button = QPushButton('Đóng', self)
        actions = QHBoxLayout()
        actions.addWidget(self.reset_button)
        actions.addStretch(1)
        actions.addWidget(self.cancel_button)
        actions.addWidget(self.done_button)
        layout = QVBoxLayout(self)
        layout.addWidget(caption)
        layout.addWidget(self.status)
        layout.addWidget(self.canvas, 1)
        layout.addLayout(actions)
        self.resize(1120, 760)
        self.canvas.pixel_clicked.connect(self._clicked)
        self.reset_button.clicked.connect(self.clear)
        self.done_button.clicked.connect(self.accept)
        self.cancel_button.clicked.connect(self.reject)

    def clear(self):
        self.first = None
        self.result = None
        self.canvas.markers.clear()
        self.canvas.update()
        self.done_button.setEnabled(False)
        self.status.setText('BƯỚC 1/2: Chọn điểm A trên ảnh Depth.')

    def _clicked(self, u: int, v: int):
        if self.result is not None:
            self.status.setText('Đã hoàn thành. Chọn “Sử dụng kết quả” hoặc “Chọn lại A/B”.')
            return
        hit = self.picker.hit(u, v)
        if hit is None:
            label = 'B' if self.first is not None else 'A'
            self.status.setText(f'Không có Depth hợp lệ gần ({u}, {v}) cho {label}. '
                                'Chọn vùng có điểm sáng/màu, không phải vùng đen.')
            return
        try:
            selected = select_measurement_point(self._view.geometry, hit.index)
            if self.first is None:
                self.first = selected
                self.canvas.markers = [('A', hit.u, hit.v)]
                suffix = ' (đã dịch tới pixel hợp lệ gần nhất)' if hit.snapped else ''
                self.status.setText(f'BƯỚC 2/2: A = XYZ #{hit.index} tại Depth ({hit.u},{hit.v}){suffix}. '
                                    'Chọn B trên cùng ảnh Depth.')
            else:
                result = measure_selected_points(self.first, selected)
                self.result = result
                self.canvas.markers.append(('B', hit.u, hit.v))
                self.done_button.setEnabled(True)
                self.status.setText(f'ĐÃ ĐO A–B: {result.distance_m:.6f} m = '
                                    f'{result.distance_mm:.3f} mm | XYZ {result.point_indices} | '
                                    'PROVISIONAL_NOT_METRIC_VALIDATED')
        except MeasurementError as exc:
            self.status.setText('Từ chối điểm Depth: ' + exc.code + '. Nhấn Chọn lại A/B.')
            self.clear()
            return
        self.canvas.update()
