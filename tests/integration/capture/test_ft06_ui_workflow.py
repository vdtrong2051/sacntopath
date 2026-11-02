"""FT-06 responsive widget/quick workflow and sampled Depth mask assertions."""
import numpy as np
from PySide6.QtWidgets import QApplication, QSplitter
from scantopath.modules.capture.presentation.live_capture_panel import LiveCapturePanel
from scantopath.modules.capture.presentation.live_3d_panel import Live3DPanel
from scantopath.modules.capture.presentation.depth_roi_overlay import DepthRoiOverlay


def _app():
    return QApplication.instance() or QApplication([])


def test_ft06_ui_compact_splitters_and_visible_quick_actions():
    _app()
    panel = LiveCapturePanel()
    assert isinstance(panel.main_splitter, QSplitter)
    assert isinstance(panel.camera_panes, QSplitter)
    assert panel.main_splitter.count() == 2
    assert panel.camera_panes.count() == 2
    assert panel.details_button.isCheckable()
    assert not panel.roi_safety_status.isVisible()
    assert panel.cloud_view.freeze_button.objectName() == 'captureLiveFreezeButton'
    panel.cloud_view.set_snapshot_state('live')
    assert panel.cloud_view.freeze_button.isEnabled()
    assert not panel.cloud_view.snapshot_button.isEnabled()
    panel.cloud_view.set_snapshot_state('frozen')
    assert panel.cloud_view.snapshot_button.isEnabled()
    assert panel.cloud_view.resume_button.isEnabled()
    panel.cloud_view.set_snapshot_state('saving')
    assert not panel.cloud_view.resume_button.isEnabled()
    assert not panel.cloud_view.snapshot_button.isEnabled()
    panel.close()


def test_ft06_depth_mask_matches_depth_grid():
    _app()
    overlay = DepthRoiOverlay()
    overlay.set_depth_image(np.zeros((8, 10), dtype=np.uint8))
    mask = np.zeros((8, 10), dtype=np.uint8)
    mask[3:5, 2:5] = 255
    overlay.set_sampled_mask(mask)
    assert overlay._selected_pixmap is not None
    overlay.set_depth_image(np.ones((8, 10), dtype=np.uint8))
    assert overlay._selected_pixmap is not None
    import pytest
    with pytest.raises(ValueError, match='FT06_MASK_GRID_MISMATCH'):
        overlay.set_sampled_mask(np.zeros((2, 2), dtype=np.uint8))
    overlay.clear()
    assert overlay._selected_pixmap is None
    overlay.close()
