"""FT11 Windows/offscreen Qt smoke for task panel, without camera or VTK."""
import os
os.environ.setdefault('QT_QPA_PLATFORM','offscreen')
import pytest
pytest.importorskip('PySide6')
from PySide6.QtWidgets import QApplication
from scantopath.modules.reconstruction.presentation.reconstruction_workflow import ReconstructionPanel


def test_reconstruction_panel_tracks_rows_and_locks_actions():
    app = QApplication.instance() or QApplication([])
    p = ReconstructionPanel()
    assert not p.view_button.isEnabled()
    p.set_tracking({
        'source_frame_count': 3, 'accepted_poses':2,
        'frames': [
            {'sample_index':0,'status':'ANCHOR','quality':None},
            {'sample_index':1,'status':'DEGRADED','reject_code':'GEOMETRY_DEGENERATE',
             'quality':{'overlap':0.91,'inlier_rmse_m':0.003}},
            {'sample_index':2,'status':'RECOVERED','quality':{'overlap':0.98,'inlier_rmse_m':0.002}},
        ],
    })
    assert p.pose_table.topLevelItemCount()==3
    assert p.pose_table.topLevelItem(1).text(3)=='3.00'
    assert p.frames.text()=='Frame: 3'
    p.set_ready(True,False)
    assert p.view_button.isEnabled()
    p.set_ready(False,True)
    assert not p.open_source.isEnabled()
    p.deleteLater()
