"""UXH-01.7-A offscreen Qt tests; never start camera or VTK process."""
from __future__ import annotations

import os
os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')

import pytest
pytest.importorskip('PySide6')
from PySide6.QtWidgets import QApplication, QFrame, QLabel, QPushButton, QWidget

from scantopath.modules.viewer3d.presentation.view import Viewer3DPage
from scantopath.modules.viewer3d.presentation.interactive_controller import InteractiveViewer3DController
from scantopath.modules.capture.presentation.preview_widget import CapturePreviewWidget


@pytest.fixture
def qapp():
    return QApplication.instance() or QApplication([])


def test_viewer_named_slots_mount_order_and_legacy_navigation(qapp):
    page = Viewer3DPage()
    try:
        src = QLabel('PLY context', page)
        measure = QFrame(page)
        page.mount_source_info(src)
        page.mount_measurement(measure)
        assert page.source_info_slot.objectName() == 'viewer3dSourceInfoSlot'
        assert page.measurement_slot.objectName() == 'viewer3dMeasurementSlot'
        assert page.navigation_layout.objectName() == 'viewer3dNavigationLayout'
        assert page.source_info_slot.itemAt(0).widget() is src
        assert page.measurement_slot.itemAt(0).widget() is measure
        slots = [page.layout().itemAt(i).layout() for i in range(page.layout().count())]
        assert slots.index(page.source_info_slot) < slots.index(page.measurement_slot)
        assert slots.index(page.measurement_slot) < slots.index(page.navigation_layout)
        assert page.findChild(QWidget, 'viewer3dOrbitLeft') is not None
        with pytest.raises(ValueError, match='VIEWER_SOURCE_INFO_SLOT'):
            page.mount_source_info(QLabel('duplicate', page))
        with pytest.raises(ValueError, match='VIEWER_MEASUREMENT_SLOT'):
            page.mount_measurement(QFrame(page))
    finally:
        page.close()


def test_replay_slot_before_existing_replay_button(qapp):
    panel = CapturePreviewWidget()
    try:
        action = QPushButton('Xem XYZRGB 3D', panel)
        action.setObjectName('captureGeometryPreviewButton')
        panel.mount_replay_action(action)
        assert panel.replay_action_slot.objectName() == 'captureReplayActionSlot'
        assert panel.replay_action_slot.itemAt(0).widget() is action
        header = panel.layout().itemAt(0).layout()
        indices = [header.itemAt(i).layout() for i in range(header.count())]
        assert indices.index(panel.replay_action_slot) < header.indexOf(panel.replay_button)
        with pytest.raises(ValueError, match='CAPTURE_REPLAY_ACTION'):
            panel.mount_replay_action(action)
    finally:
        panel.close()


def test_interactive_controller_hides_legacy_nav_via_named_layout(qapp):
    parent = QWidget()
    controller = InteractiveViewer3DController(parent, session_factory=lambda: None)
    try:
        assert controller.page.navigation_layout.count() >= 8
        for i in range(controller.page.navigation_layout.count()):
            widget = controller.page.navigation_layout.itemAt(i).widget()
            if widget is not None:
                assert widget.isHidden()
        assert controller.page.preview.objectName() == 'viewer3dPreview'
        assert controller.tools.objectName() == 'viewer3dLiveTools'
    finally:
        controller._poll_timer.stop()
        controller.page.close()
        parent.close()


def test_geometry_action_integrates_into_real_shell(qapp):
    # Construction is lazy: no physical camera, SDK, SQLite writes or VTK host.
    from scantopath.ui.shell.main_window import ScanToPathMainWindow
    win = ScanToPathMainWindow()
    try:
        panel = win.capture_preview.panel
        assert panel.replay_action_slot.count() == 1
        assert panel.replay_action_slot.itemAt(0).widget() is win.geometry_preview.button
        assert win.geometry_preview.button.objectName() == 'captureGeometryPreviewButton'
        assert panel.replay_button.objectName() == 'captureReplayButton'
    finally:
        win.close()
