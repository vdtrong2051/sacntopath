"""Static safety regression: FT-06 R1 only changes display-side geometry."""
import inspect
from PySide6.QtWidgets import QApplication
from scantopath.modules.capture.presentation.live_3d_panel import Live3DPanel
from scantopath.modules.capture.presentation.live_ui_controller import LiveCaptureUiController
from scantopath.modules.geometry.presentation.live_geometry_worker import LiveGeometryThread
from scantopath.modules.capture.presentation.auto_capture_controller import AutoCaptureController


def test_visual_mode_opt_in_ui_and_worker_generation():
    app=QApplication.instance() or QApplication([])
    panel=Live3DPanel()
    try:
        assert panel.enhance_toggle.isChecked()
        assert panel.enhance_toggle.objectName()=='captureLiveVisualDepthEnhancement'
        changes=[]
        panel.enhancement_mode_changed.connect(changes.append)
        panel.enhance_toggle.setChecked(False)
        panel.enhance_toggle.setChecked(True)
        assert changes==['off','visual']
    finally:
        panel.close()
        panel.deleteLater()
    worker=LiveGeometryThread()
    assert worker.statistics()['enhancement_mode']=='visual'
    worker.set_enhancement_mode('off')
    assert worker.statistics()['enhancement_mode']=='off'
    worker.request_stop()


def test_raw_capture_and_auto_keyframe_stay_isolated():
    source=inspect.getsource(AutoCaptureController._on_analysis)
    assert 'roi_safety.evaluate(frame, roi)' in source
    source=inspect.getsource(LiveCaptureUiController._pump_preview)
    assert 'worker.submit(self._generation, frame, depth_roi=rect)' in source
    assert 'self.panel.manual_roi if' in source
