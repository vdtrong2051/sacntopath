"""FT-05.7 GUI scope controls and AutoCapture safety isolation."""
import inspect
import pytest
from PySide6.QtWidgets import QApplication
from scantopath.modules.capture.presentation.live_3d_panel import Live3DPanel
from scantopath.modules.capture.presentation.live_ui_controller import LiveCaptureUiController
from scantopath.modules.geometry.presentation.live_geometry_worker import LiveGeometryThread
from scantopath.modules.capture.presentation.auto_capture_controller import AutoCaptureController


def test_ft057_scope_combo_explicit_and_one_view():
    app=QApplication.instance() or QApplication([])
    pane=Live3DPanel()
    out=[]
    pane.scope_mode_changed.connect(out.append)
    assert pane.scope_mode.currentData()=='object'
    assert pane.findChild(type(pane.scope_mode),'captureLive3DScopeMode') is pane.scope_mode
    pane.scope_mode.setCurrentIndex(1)
    pane.scope_mode.setCurrentIndex(0)
    assert out==['scene','object']
    pane.deleteLater()


def test_ft057_worker_scope_switch_bounded_and_default_compatible():
    worker=LiveGeometryThread()
    assert worker.statistics()['scope_mode']=='scene'
    worker.set_scope_mode('object')
    assert worker.statistics()['scope_mode']=='object'
    worker.set_scope_mode('scene')
    assert worker.statistics()['scope_mode']=='scene'
    with pytest.raises(ValueError):
        worker.set_scope_mode('random')
    worker.request_stop()


def test_ft057_auto_capture_still_uses_original_tracking():
    source=inspect.getsource(AutoCaptureController._on_analysis)
    assert 'tracking.roi if tracking is not None and tracking.usable' in source
    assert 'roi_safety.evaluate(frame, roi)' in source
    assert 'display_stabilizer' not in source
    capture=inspect.getsource(LiveCaptureUiController._on_analysis_available)
    assert 'analysis_ready.emit(frame, result)' in capture


def test_ft057_live_ui_source_does_not_block_qt_for_vtk():
    from scantopath.modules.capture.presentation import live_3d_controller
    source=inspect.getsource(live_3d_controller.Live3DController._on_scope_mode)
    assert 'invalidate_scene()' in source
    assert 'set_geometry_scope_mode(mode)' in source
    assert 'result(timeout=' not in source
