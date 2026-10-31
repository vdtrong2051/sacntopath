"""UXH-01.2 Qt grid contract; no Render Host or camera required."""
import pytest
pytest.importorskip('PySide6')
from PySide6.QtWidgets import QApplication, QWidget
from scantopath.modules.viewer3d.presentation.live_tools import LiveViewerTools


def test_grid_modes_and_signal_contract():
    app = QApplication.instance() or QApplication([])
    root = QWidget()
    toolbar = LiveViewerTools(root)
    changes = []
    toolbar.grid_changed.connect(lambda enabled, mode: changes.append((enabled, mode)))
    try:
        for mode in ('xy', 'xz', 'yz', 'base'):
            toolbar.set_grid(False, mode)
            assert not toolbar.grid_button.isChecked()
            assert toolbar.grid_mode == mode
            toolbar.grid_button.setChecked(True)
            assert changes[-1] == (True, mode)
        assert toolbar.grid_button.objectName() == 'viewer3dToolGrid'
        assert 'không phải mặt sàn' in toolbar.grid_button.toolTip()
        with pytest.raises(ValueError, match='INVALID_REFERENCE_GRID'):
            toolbar.set_grid(True, 'unknown')
    finally:
        root.close()
