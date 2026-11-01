"""FT-05.6: preserve raw AutoCapture input and make noise switch nonblocking."""
from pathlib import Path
from PySide6.QtWidgets import QApplication
from scantopath.modules.capture.presentation.live_3d_panel import Live3DPanel
from scantopath.modules.geometry.presentation.live_geometry_worker import LiveGeometryThread

_APP=None

def test_ui56_01_filter_toggle_visible_and_no_vtk_import():
    global _APP
    _APP=QApplication.instance() or QApplication([])
    panel=Live3DPanel()
    observed=[]
    panel.denoise_mode_changed.connect(observed.append)
    assert panel.denoise_toggle.isChecked()
    panel.denoise_toggle.setChecked(False)
    panel.denoise_toggle.setChecked(True)
    assert observed==['off','standard']


def test_ui56_02_worker_mode_change_safe_and_bounded():
    worker=LiveGeometryThread()
    worker.set_denoise_mode('off')
    assert worker.statistics()['denoise_mode']=='off'
    worker.set_denoise_mode('standard')
    assert worker.statistics()['denoise_mode']=='standard'
    worker.request_stop()
    assert worker.statistics()["worker_closing"] == 1


def test_ui56_03_auto_capture_remains_raw_tracking_not_smoothed_display():
    from scantopath.modules.capture.presentation import live_ui_controller
    import inspect
    source=inspect.getsource(live_ui_controller.LiveCaptureUiController._on_analysis_available)
    assert 'analysis_ready.emit(frame, result)' in source
    assert 'display_roi=self._display_stabilizer.update(frame_index, result)' in source
    assert 'analysis_ready.emit(frame, self._display_stabilizer' not in source
