"""FT-05.8 Qt/reference-mode boundaries and FT-03 / FT-05.7 safety regression."""
from __future__ import annotations
import inspect
import pytest
from PySide6.QtWidgets import QApplication
from scantopath.modules.capture.presentation.live_3d_panel import Live3DPanel
from scantopath.modules.capture.presentation.live_ui_controller import LiveCaptureUiController
from scantopath.modules.geometry.presentation.live_geometry_worker import LiveGeometryThread
from scantopath.modules.capture.presentation.auto_capture_controller import AutoCaptureController


def test_reference_combo_explicit_and_ft057_still_available():
    app = QApplication.instance() or QApplication([])
    panel = Live3DPanel()
    changes = []
    panel.reference_mode_changed.connect(changes.append)
    assert panel.scope_mode.currentData() == 'object'
    assert panel.reference_mode.currentData() == 'charuco'
    assert panel.reference_mode.count() == 2
    panel.reference_mode.setCurrentIndex(1)
    panel.reference_mode.setCurrentIndex(0)
    assert changes == ['depth', 'charuco']
    panel.scope_mode.setCurrentIndex(1)
    assert not panel.reference_mode.isEnabled()
    panel.scope_mode.setCurrentIndex(0)
    assert panel.reference_mode.isEnabled()
    panel.deleteLater()


def test_reference_mode_bounded_and_legacy_constructor_preserved():
    w = LiveGeometryThread()
    assert w.statistics()['scope_mode'] == 'scene'
    assert w.statistics()['reference_mode'] == 'depth'
    w.set_scope_mode('object')
    w.set_reference_mode('charuco')
    assert w.statistics()['reference_mode'] == 'charuco'
    w.set_reference_mode('depth')
    assert w.statistics()['reference_mode'] == 'depth'
    with pytest.raises(ValueError, match='REFERENCE_MODE_INVALID'):
        w.set_reference_mode('auto_fallback')
    w.request_stop()


def test_raw_and_autocapture_are_untouched():
    s=inspect.getsource(AutoCaptureController._on_analysis)
    assert 'roi_safety.evaluate(frame, roi)' in s
    assert 'tracking.roi if tracking is not None and tracking.usable' in s
    s=inspect.getsource(LiveCaptureUiController._on_analysis_available)
    assert 'analysis_ready.emit(frame, result)' in s


def test_mode_switch_invalidate_render_and_clear_qt():
    from scantopath.modules.capture.presentation.live_3d_controller import Live3DController
    body=inspect.getsource(Live3DController._on_reference_mode)
    assert 'invalidate_scene()' in body
    assert 'set_geometry_reference_mode(mode)' in body
    assert 'result(timeout=' not in body
