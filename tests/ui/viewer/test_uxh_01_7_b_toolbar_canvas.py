"""UXH-01.7-B: Qt-only toolbar hierarchy/canvas, no VTK/Orbbec hardware."""
from __future__ import annotations

import os
os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')

import pytest
pytest.importorskip('PySide6')
from PySide6.QtWidgets import QApplication, QWidget
from scantopath.modules.viewer3d.presentation.live_tools import LiveViewerTools
from scantopath.modules.viewer3d.presentation.interactive_controller import InteractiveViewer3DController


@pytest.fixture
def toolbar():
    app = QApplication.instance() or QApplication([])
    parent = QWidget()
    parent.resize(850, 600)
    t = LiveViewerTools(parent)
    parent.show()
    t.show()
    app.processEvents()
    yield t
    parent.close()
    app.processEvents()


def test_primary_tools_and_legacy_names_are_retained(toolbar):
    assert toolbar.advanced_button.objectName() == 'viewer3dToolAdvanced'
    assert toolbar.advanced_menu.objectName() == 'viewer3dAdvancedMenu'
    assert toolbar.buttons['viewer3dToolSelect'].isVisible()
    assert toolbar.buttons['viewer3dToolOrbit'].isVisible()
    assert toolbar.buttons['viewer3dToolPan'].isVisible()
    assert toolbar.buttons['viewer3dToolFit'].isVisible()
    for name in ('viewer3dToolAxes', 'viewer3dToolZoomIn',
                 'viewer3dToolZoomOut', 'viewer3dToolGrid', 'viewer3dToolLayer'):
        assert name in toolbar.buttons
        assert toolbar.buttons[name].objectName() == name
        assert toolbar.buttons[name].isHidden()
    assert toolbar.advanced_menu.actions()
    assert toolbar.height() < 350  # not the prior 9-button vertical stack


def test_advanced_actions_dispatch_existing_signals(toolbar):
    events = []
    toolbar.camera_action.connect(events.append)
    for name, expected in (
        ('viewer3dActionAxes', 'axes'),
        ('viewer3dActionZoomIn', 'zoom_in'),
        ('viewer3dActionZoomOut', 'zoom_out'),
    ):
        action = next(a for a in toolbar.advanced_menu.actions() if a.objectName() == name)
        action.trigger()
        assert events[-1] == expected
    toolbar.buttons['viewer3dToolFit'].click()
    assert events[-1] == 'reset'


def test_grid_and_layer_keyboard_contracts_keep_menu_in_sync(toolbar):
    grid_events = []
    layer_events = []
    toolbar.grid_changed.connect(lambda enabled, mode: grid_events.append((enabled, mode)))
    toolbar.layer_changed.connect(layer_events.append)
    toolbar._advanced_grid_action.trigger()
    assert not toolbar.grid_button.isChecked()
    assert grid_events[-1] == (False, 'xy')
    toolbar._grid_plane_actions['xz'].trigger()
    assert toolbar.grid_button.isChecked()
    assert toolbar.grid_mode == 'xz'
    assert grid_events[-1] == (True, 'xz')
    toolbar.set_grid(False, 'yz')
    assert not toolbar._advanced_grid_action.isChecked()
    assert toolbar._grid_plane_actions['yz'].isChecked()
    toolbar.grid_button.toggle()  # existing G shortcut target
    assert toolbar._advanced_grid_action.isChecked()
    assert grid_events[-1] == (True, 'yz')
    toolbar._advanced_layer_action.trigger()
    assert layer_events[-1] is False
    assert not toolbar.layer_button.isChecked()
    toolbar.set_layer(True)
    assert toolbar._advanced_layer_action.isChecked()
    toolbar.layer_button.toggle()  # existing L shortcut target
    assert layer_events[-1] is False


def test_interactive_viewer_canvas_is_compact_without_hiding_disclosures():
    app = QApplication.instance() or QApplication([])
    parent = QWidget()
    controller = InteractiveViewer3DController(parent, session_factory=lambda: None)
    try:
        controller._poll_timer.stop()
        parent.resize(1100, 800)
        parent.show()
        controller.page.resize(1000, 700)
        controller.page.show()
        app.processEvents()
        assert controller.page.layout().getContentsMargins() == (12, 8, 12, 8)
        assert controller.page.layout().spacing() == 6
        assert controller.page.surface.layout().count() == 1
        assert controller.page.preview.objectName() == 'viewer3dPreview'
        assert controller.page.navigation_layout.objectName() == 'viewer3dNavigationLayout'
        assert controller.page.source_info_slot.objectName() == 'viewer3dSourceInfoSlot'
        assert controller.page.measurement_slot.objectName() == 'viewer3dMeasurementSlot'
        assert controller.page.note is not None
        assert controller.page.state.isVisible()
        assert controller.page.note.isVisible()
    finally:
        controller.page.close()
        parent.close()
        app.processEvents()
