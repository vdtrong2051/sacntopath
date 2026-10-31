"""GD2-10.08.2: visible A/B anchors, line, and screen-state invalidation."""
from __future__ import annotations

import pytest
from PySide6.QtCore import Qt, Signal, QObject
from PySide6.QtGui import QPixmap, QColor
from PySide6.QtWidgets import QApplication, QWidget, QVBoxLayout, QLabel

from scantopath.modules.viewer3d.presentation.live_view import LiveNavigationPreview
from scantopath.ui.shell.geometry_measurement import GeometryMeasurementPanel
from tests.unit.geometry.test_gd2_10_08_2_measurement_ui import fixture, pick


def test_visible_anchor_overlay_renders_two_labeled_points(qt_app):
    widget = LiveNavigationPreview('test')
    widget.resize(480, 300)
    image = QPixmap(480, 300)
    image.fill(QColor('#1c2633'))
    widget.setPixmap(image)
    widget.show()
    qt_app.processEvents()
    baseline = widget.grab().toImage()
    widget.set_measurement_anchors([('A', (0.25, 0.65))])
    qt_app.processEvents()
    a_image = widget.grab().toImage()
    widget.set_measurement_anchors([('A', (0.25, 0.65)), ('B', (0.75, 0.35))])
    qt_app.processEvents()
    ab_image = widget.grab().toImage()
    # The screenshot must change when A is added and when B/line is added.
    from hashlib import sha256
    def digest(image):
        bits = image.constBits()
        return sha256(bytes(bits)).hexdigest()
    assert len({digest(baseline), digest(a_image), digest(ab_image)}) == 3
    assert len(widget._measurement_anchors) == 2
    widget.set_measurement_anchors([])
    assert widget._measurement_anchors == ()
    widget.close()


@pytest.fixture
def qt_app():
    return QApplication.instance() or QApplication([])


class Page(QWidget):
    point_requested = Signal(float, float)
    navigation_requested = Signal(str, float, float)

    def __init__(self):
        super().__init__()
        layout = QVBoxLayout(self)
        layout.addWidget(QLabel('head', self))
        layout.addWidget(QLabel('status', self))
        self.preview = LiveNavigationPreview('test', self)
        layout.addWidget(self.preview)


class Viewer(QObject):
    scene_inspection = Signal(object)
    point_pick_completed = Signal(object)

    def __init__(self):
        super().__init__()
        self.page = Page()
        self._descriptor = None
        self._current_source = None
        self._pending_source = None
        self._live_phase = 'idle'
        self._legacy_mode = False
        self._expected_scene_revision = None
        self._last_frame_revision = 2
        self._selected = None
        self.modes = []

    def _set_tool_mode(self, value):
        self.modes.append(value)


def prepare(tmp_path, qt_app):
    view, receipt = fixture(tmp_path)
    viewer = Viewer()
    panel = GeometryMeasurementPanel(viewer, viewer)
    panel.bind_preview(receipt, view)
    viewer._current_source = receipt.path
    viewer._descriptor = type('Scene', (), {
        'source_sha256': receipt.ply_sha256,
        'point_count': receipt.colored_points,
        'geometry_kind': 'points',
    })()
    viewer._expected_scene_revision = 3
    viewer._live_phase = 'ready'
    panel._poll()
    panel.mode_button.setChecked(True)
    return view, receipt, viewer, panel


def test_A_B_has_visible_anchors_and_line_then_clears_on_camera_change(qt_app, tmp_path):
    view, receipt, viewer, panel = prepare(tmp_path, qt_app)
    try:
        viewer.page.point_requested.emit(0.20, 0.30)
        viewer._selected = pick(view, receipt, 0)
        viewer.point_pick_completed.emit(viewer._selected)
        assert panel._anchors == [('A', (0.20, 0.30))]
        assert viewer.page.preview._measurement_anchors == tuple(panel._anchors)
        assert 'NEO A' in panel.readout.text()
        viewer.page.point_requested.emit(0.70, 0.80)
        viewer._selected = pick(view, receipt, 1)
        viewer.point_pick_completed.emit(viewer._selected)
        assert len(panel._anchors) == 2
        assert 'ĐÃ ĐO' in panel.readout.text()
        assert ' mm' in panel.readout.text()
        assert viewer.page.preview._measurement_anchors == tuple(panel._anchors)
        viewer._last_frame_revision += 1
        panel._poll()
        assert panel._anchors == []
        assert panel._session.first is None
        assert panel._session.last is None
        assert 'Góc nhìn đã thay đổi' in panel.readout.text()
    finally:
        panel.dispose()
        viewer.page.close()


def test_missed_B_keeps_A_and_clear_button_removes_anchors(qt_app, tmp_path):
    view, receipt, viewer, panel = prepare(tmp_path, qt_app)
    try:
        viewer.page.point_requested.emit(0.3, 0.4)
        viewer._selected = pick(view, receipt, 0)
        viewer.point_pick_completed.emit(viewer._selected)
        viewer.page.point_requested.emit(0.9, 0.9)
        viewer.point_pick_completed.emit(None)
        assert len(panel._anchors) == 1
        assert len(viewer.page.preview._measurement_anchors) == 1
        panel.clear_button.click()
        assert panel._anchors == []
        assert viewer.page.preview._measurement_anchors == ()
    finally:
        panel.dispose()
        viewer.page.close()
