"""Shared isolated Qt Viewer fixture for UXH anchor and delivery tests."""
from __future__ import annotations
from PySide6.QtCore import QObject, Signal
from PySide6.QtWidgets import QWidget, QVBoxLayout, QLabel
from scantopath.modules.viewer3d.presentation.live_view import LiveNavigationPreview
from scantopath.ui.shell.geometry_measurement import GeometryMeasurementPanel
from tests.support.uxh_geometry_measure import fixture, pick

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

    def mount_measurement(self, panel):
        # Same presentation mount contract as the actual viewer page.
        self.layout().addWidget(panel)


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
