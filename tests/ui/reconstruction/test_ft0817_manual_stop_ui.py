"""HF03 operator-owned scan: retain up to 96 frames without auto-stop."""
from __future__ import annotations

from types import SimpleNamespace as NS
import pytest
from PySide6.QtCore import QObject, Signal
from PySide6.QtWidgets import QApplication, QComboBox, QFrame, QVBoxLayout

from scantopath.modules.capture.domain.models import CameraState
from scantopath.modules.reconstruction.presentation import sequence_capture_ui as mod


class Camera(QObject):
    state_changed = Signal(object)
    keyframe_ready = Signal(object)
    keyframe_failed = Signal(str)

    def __init__(self):
        super().__init__()
        self.state = CameraState.STREAMING

    def capture_keyframe(self, **kwargs):
        return True


class Panel(QFrame):
    scope_mode_changed = Signal(str)
    reference_mode_changed = Signal(str)

    def __init__(self):
        super().__init__()
        QVBoxLayout(self)
        self.scope_mode = QComboBox(self)
        self.scope_mode.addItem('Vật thể','object')
        self.reference_mode = QComboBox(self)
        self.reference_mode.addItem('ChArUco','charuco')


class FakePacket:
    def __init__(self,i):
        self.metadata = NS(session_id='test-session',specimen_id='test-specimen',
            depth=NS(frame_index=i,timestamp_us=100_000+i*2_000_000))


@pytest.fixture
def ui():
    app=QApplication.instance() or QApplication([])
    panel,camera=Panel(),Camera()
    widget=mod.SequenceCaptureUi(panel,camera)
    widget._session_id='test-session'
    widget._specimen_id='test-specimen'
    widget._recording=True
    widget._update_controls()
    yield widget
    widget.begin_shutdown()
    panel.close()


def test_more_than_twenty_does_not_automatically_finish(monkeypatch,ui):
    monkeypatch.setattr(mod,'RawRgbdCapture',FakePacket)
    finished=[]
    monkeypatch.setattr(ui,'_finish_capture',lambda: finished.append(True))
    for i in range(88):
        ui._inflight=True
        ui._keyframe_ready(FakePacket(i))
        assert ui._recording
        assert not ui._stopping
    assert not finished
    assert ui._captured_total==88
    assert len(ui._packets)==88
    assert ui.stop_button.isEnabled()
    assert '88 frame' in ui.status.text()
    ui._inflight=False
    ui._stop()
    assert finished==[True]
    assert ui._stop_reason=='operator'


def test_transient_capture_failure_is_retryable(monkeypatch,ui):
    monkeypatch.setattr(mod,'RawRgbdCapture',FakePacket)
    finished=[]
    monkeypatch.setattr(ui,'_finish_capture',lambda: finished.append(True))
    ui._inflight=True
    ui._keyframe_failed('FRAME_TIMEOUT')
    assert ui._recording and not ui._stopping
    assert ui._failed_attempts==1
    assert ui._timer.isActive()
    assert finished==[]
    ui._inflight=True
    ui._keyframe_ready(FakePacket(0))
    assert ui._captured_total==1 and len(ui._packets)==1
    ui._timer.stop()


def test_terminal_camera_failure_still_safely_finishes(monkeypatch,ui):
    finished=[]
    monkeypatch.setattr(ui,'_finish_capture',lambda: finished.append(True))
    ui._camera_state(CameraState.FAILED)
    assert finished==[True]
    assert ui._stop_reason=='camera_stream_ended'
