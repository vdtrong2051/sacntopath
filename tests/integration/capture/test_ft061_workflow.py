"""FT-06.1 wiring checks, never invoke Gemini2 or a VTK process."""
from __future__ import annotations
import inspect
from PySide6.QtWidgets import QApplication
from scantopath.modules.capture.presentation.live_ui_controller import LiveCaptureUiController
from scantopath.modules.capture.presentation.live_3d_controller import Live3DController
from scantopath.modules.capture.presentation.live_capture_panel import LiveCapturePanel
from scantopath.modules.capture.presentation.auto_capture_controller import AutoCaptureController


def test_charuco_auto_region_does_not_use_legacy_display_roi_and_manual_still_works():
    source=inspect.getsource(LiveCaptureUiController._pump_preview)
    assert 'self.panel.manual_roi if' in source
    assert "self._geometry_reference_mode == 'charuco'" in source
    assert 'else self.panel.displayed_roi' in source
    assert 'worker.submit(self._generation, frame, depth_roi=rect)' in source


def test_auto_capture_safety_is_untouched():
    source=inspect.getsource(AutoCaptureController._on_analysis)
    assert 'roi_safety.evaluate(frame, roi)' in source
    assert 'tracking.roi if tracking is not None and tracking.usable' in source


def test_object_bbox_is_secondary_overlay_only():
    app=QApplication.instance() or QApplication([])
    panel=LiveCapturePanel()
    try:
        assert panel.cloud_view.tracking_info.objectName()=='captureLiveObjectTrackingStatus'
        assert panel.depth_overlay._object_bbox is None
        assert panel.depth_overlay.roi is None
        panel.depth_overlay.set_object_bbox(None, 'LOST')
        assert panel.depth_overlay.roi is None
    finally:
        panel.close()
        panel.deleteLater()


def test_geometry_failure_clears_cloud_and_tracking_does_not_create_geometry():
    code=inspect.getsource(Live3DController._on_geometry_failed)
    assert 'self._object_tracker.missed()' in code
    assert 'self._worker.invalidate_scene()' in code
    tracker=inspect.getsource(Live3DController._update_tracking_ui)
    assert 'set_object_bbox' in tracker
    assert 'submit_cloud' not in tracker
