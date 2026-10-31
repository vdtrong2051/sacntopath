"""Qt-only regression for the new independent Depth image measurement dialog."""
from PySide6.QtWidgets import QApplication, QDialog
from scantopath.ui.shell.depth_measure_dialog import DepthTwoPointDialog
from tests.unit.geometry.test_gd2_10_08_1_preview import xyzrgb_view


def test_depth_dialog_two_clicks_produce_float64_source_backed_result():
    app = QApplication.instance() or QApplication([])
    view = xyzrgb_view()
    dialog = DepthTwoPointDialog(view)
    try:
        assert dialog.done_button.isEnabled() is False
        a = view.depth_source_uv[0]
        b = view.depth_source_uv[-1]
        dialog.canvas.pixel_clicked.emit(int(a[0]), int(a[1]))
        assert dialog.first is not None
        assert dialog.result is None
        dialog.canvas.pixel_clicked.emit(int(b[0]), int(b[1]))
        assert dialog.result is not None
        assert dialog.result.point_indices == (0, len(view.points_xyz_m)-1)
        assert dialog.result.status == 'PROVISIONAL_NOT_METRIC_VALIDATED'
        assert dialog.done_button.isEnabled()
        assert 'ĐÃ ĐO A–B' in dialog.status.text()
        dialog.done_button.click()
        assert dialog.result is not None
        assert dialog.result.distance_mm >= 0
    finally:
        dialog.close()
