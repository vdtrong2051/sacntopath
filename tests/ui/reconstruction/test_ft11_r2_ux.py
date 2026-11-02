"""FT-11 R2 Qt offscreen: UX states and existing workflows stay functional."""
import os
os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
import pytest
pytest.importorskip('PySide6')
from PySide6.QtWidgets import QApplication, QFrame, QVBoxLayout, QComboBox, QLabel
from PySide6.QtCore import QObject, Signal

from scantopath.modules.capture.domain.models import CameraState
from scantopath.modules.project_workspace.presentation.ft07_project_hub import ProjectHub
from scantopath.modules.reconstruction.presentation.reconstruction_workflow import ReconstructionPanel
from scantopath.modules.reconstruction.presentation.sequence_capture_ui import SequenceCaptureUi

class CameraStub(QObject):
    state_changed = Signal(object)
    keyframe_ready = Signal(object)
    keyframe_failed = Signal(str)
    def __init__(self):
        super().__init__()
        self.state = CameraState.IDLE
    def capture_keyframe(self, *, session_id, specimen_id):
        return True

class LiveStub(QFrame):
    scope_mode_changed = Signal(str)
    reference_mode_changed = Signal(str)
    def __init__(self):
        super().__init__()
        QVBoxLayout(self)
        self.scope_mode = QComboBox(self)
        self.scope_mode.addItem('Vật thể', 'object')
        self.reference_mode = QComboBox(self)
        self.reference_mode.addItem('ChArUco', 'charuco')

@pytest.fixture
def app():
    return QApplication.instance() or QApplication([])

def test_project_action_context_and_async_notices(app):
    hub = ProjectHub()
    assert hub.notice.isHidden()   # No empty blue banner
    hub.notice.setText('Không thể kiểm tra Snapshot.')
    assert not hub.notice.isHidden()
    hub.notice.clear()
    assert hub.notice.isHidden()
    called=[]
    hub._reset_button(hub.primary, 'Mở dự án', lambda: called.append(1))
    hub.set_controls(False, None, False)  # read-only navigation is valid
    assert hub.primary.isEnabled()
    hub.primary.click()
    hub._reset_button(hub.primary, '+ Tạo dự án', lambda: called.append(2))
    hub.set_controls(False, None, False)
    assert not hub.primary.isEnabled()
    assert called == [1]
    hub.deleteLater()

def test_capture_mode_is_explicit_and_does_not_reopen_camera(app):
    panel, camera = LiveStub(), CameraStub()
    ui=SequenceCaptureUi(panel,camera)
    assert ui.capture_mode.currentData() == 'multi'
    camera.state=CameraState.STREAMING
    camera.state_changed.emit(camera.state)
    assert ui.start_button.isEnabled()
    ui.capture_mode.setCurrentIndex(1)
    assert ui.capture_mode.currentData() == 'single'
    assert not ui.start_button.isEnabled()
    assert ui.start_button.isHidden()
    ui.capture_mode.setCurrentIndex(0)
    assert ui.start_button.isEnabled()
    ui.begin_shutdown()
    panel.close()

def test_processing_empty_states_and_populated_pose(app):
    panel=ReconstructionPanel()
    assert panel.pose_table.isHidden()
    assert not panel.pose_empty.isHidden()
    assert panel.history.isHidden()
    panel.set_tracking({'source_frame_count': 2, 'accepted_poses': 1,
        'frames':[{'sample_index': 0, 'status':'ANCHOR'}]})
    assert not panel.pose_table.isHidden()
    assert panel.pose_empty.isHidden()
    panel.clear_tracking()
    assert panel.pose_table.isHidden()
    panel.deleteLater()
