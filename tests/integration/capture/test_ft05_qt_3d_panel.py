"""FT-05 embedded Qt viewport smoke: no camera or VTK service spawned."""
from __future__ import annotations

import os
os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')

from PySide6.QtWidgets import QApplication
from scantopath.modules.capture.presentation.live_capture_panel import LiveCapturePanel


def test_ft05_three_views_same_live_panel_and_reset():
    app=QApplication.instance() or QApplication([])
    panel=LiveCapturePanel()
    try:
        assert panel.rgb_image is not None
        assert panel.depth_overlay is not None
        assert panel.cloud_view.objectName()=='captureLive3DPanel'
        assert panel.cloud_view.image.objectName()=='captureLive3DImage'
        assert not panel.cloud_view.reset_button.isEnabled()
        panel.cloud_view.show_frame(bytes([10,20,30]*4),2,2,points=1)
        assert panel.cloud_view.reset_button.isEnabled()
        assert 'điểm' in panel.cloud_view.status.text()
        panel.cloud_view.clear('Dừng')
        assert not panel.cloud_view.reset_button.isEnabled()
        assert panel.capture_button is not None
    finally:
        panel.close()
        panel.deleteLater()
