"""Small Qt smoke tests: FT08.17 controls reuse existing camera, no camera opened."""
from __future__ import annotations

import pytest
from PySide6.QtCore import QObject, Signal
from PySide6.QtWidgets import QApplication, QComboBox, QFrame, QVBoxLayout

from scantopath.modules.capture.domain.models import CameraState
from scantopath.modules.reconstruction.presentation.sequence_capture_ui import SequenceCaptureUi


class CameraStub(QObject):
    state_changed = Signal(object)
    keyframe_ready = Signal(object)
    keyframe_failed = Signal(str)

    def __init__(self):
        super().__init__()
        self.state = CameraState.IDLE
        self.requests = []

    def capture_keyframe(self, *, session_id, specimen_id):
        self.requests.append((session_id, specimen_id))
        return True


class PanelStub(QFrame):
    scope_mode_changed = Signal(str)
    reference_mode_changed = Signal(str)

    def __init__(self):
        super().__init__()
        QVBoxLayout(self)
        self.scope_mode = QComboBox(self)
        self.scope_mode.addItem('Vật thể', 'object')
        self.scope_mode.addItem('Toàn cảnh', 'scene')
        self.reference_mode = QComboBox(self)
        self.reference_mode.addItem('ChArUco', 'charuco')
        self.reference_mode.addItem('Depth', 'depth')


@pytest.fixture
def qt():
    app = QApplication.instance() or QApplication([])
    yield app


def test_controls_only_enable_on_existing_stream_and_charuco(qt):
    panel, camera = PanelStub(), CameraStub()
    ui = SequenceCaptureUi(panel, camera)
    assert not ui.start_button.isEnabled()
    camera.state = CameraState.STREAMING
    camera.state_changed.emit(camera.state)
    assert ui.start_button.isEnabled()
    panel.reference_mode.setCurrentIndex(1)
    panel.reference_mode_changed.emit('depth')
    assert not ui.start_button.isEnabled()
    panel.reference_mode.setCurrentIndex(0)
    panel.reference_mode_changed.emit('charuco')
    panel.scope_mode.setCurrentIndex(1)
    panel.scope_mode_changed.emit('scene')
    assert not ui.start_button.isEnabled()
    ui.begin_shutdown()
    panel.close()


def test_sampling_calls_same_live_camera_no_second_open(qt, tmp_path, monkeypatch):
    panel, camera = PanelStub(), CameraStub()
    ui = SequenceCaptureUi(panel, camera)
    camera.state = CameraState.STREAMING
    camera.state_changed.emit(camera.state)
    from PySide6.QtWidgets import QFileDialog
    monkeypatch.setattr(QFileDialog, 'getExistingDirectory', lambda *args: str(tmp_path))
    ui._start()  # schedules owned camera keyframe via its existing UI controller
    qt.processEvents()
    assert len(camera.requests) == 1
    assert camera.requests[0][0].startswith('b02ui_')
    assert ui.stop_button.isEnabled()
    assert not ui.start_button.isEnabled()
    ui.begin_shutdown()
    panel.close()
