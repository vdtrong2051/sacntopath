"""UXH-01.2-C01 Qt toolbar remains accessible without altering object names."""
import pytest
pytest.importorskip('PySide6')
from PySide6.QtWidgets import QApplication, QWidget
from scantopath.modules.viewer3d.presentation.live_tools import LiveViewerTools


def test_compass_primary_and_slim_origin_tooltips():
    app = QApplication.instance() or QApplication([])
    root = QWidget()
    bar = LiveViewerTools(root)
    try:
        assert bar.buttons['viewer3dToolAxes'].objectName() == 'viewer3dToolAxes'
        assert 'gizmo góc' in bar.buttons['viewer3dToolAxes'].toolTip()
        assert 'nét chính/phụ' in bar.grid_button.toolTip()
        assert 'không phải mặt sàn' in bar.grid_button.toolTip()
        assert bar.grid_button.objectName() == 'viewer3dToolGrid'
        seen = []
        bar.grid_changed.connect(lambda enabled, mode: seen.append((enabled, mode)))
        bar.set_grid(False, 'xz')
        bar.grid_button.setChecked(True)
        assert seen[-1] == (True, 'xz')
    finally:
        root.close()
