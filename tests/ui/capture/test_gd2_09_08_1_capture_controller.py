"""GD2-09.08.1 capture integration through QThread, no Gemini 2 required."""
from __future__ import annotations
import os
import time

import numpy as np
import pytest

os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
pytest.importorskip('PySide6')
from PySide6.QtWidgets import QApplication
from scantopath.modules.capture.application.live_stream import LiveCaptureService
from scantopath.modules.capture.domain.models import CameraState as S
from scantopath.modules.capture.presentation.live_worker import LiveStreamWorker
from scantopath.modules.capture.presentation.live_controller import LiveCameraController
from tests.support.keyframe_camera_fakes import FakeCaptureProcessCamera


@pytest.fixture(scope='module')
def app():
    return QApplication.instance() or QApplication([])


class Decoder:
    def decode(self, payload, *, width, height):
        return np.zeros((height,width,3),dtype=np.uint8)


def until(app, pred, timeout=5):
    deadline=time.monotonic()+timeout
    while time.monotonic()<deadline:
        app.processEvents()
        if pred():
            app.processEvents()
            return
        time.sleep(.005)
    raise AssertionError('CAPTURE_CONTROLLER_TIMEOUT')


def new_controller(camera):
    return LiveCameraController(worker_factory=lambda: LiveStreamWorker(
        service_factory=lambda: LiveCaptureService(camera, Decoder())
    ))


def close_controller(app,ctl):
    ctl.request_shutdown()
    until(app,lambda:ctl.safe_to_dispose)


def test_qt_controller_receives_raw_after_capture_and_resumes_stream(app):
    camera=FakeCaptureProcessCamera()
    ctl=new_controller(camera)
    done=[]
    errors=[]
    states=[]
    ctl.keyframe_ready.connect(done.append)
    ctl.keyframe_failed.connect(errors.append)
    ctl.state_changed.connect(states.append)
    try:
        assert ctl.start()
        until(app, lambda:ctl.state is S.STREAMING)
        assert ctl.capture_keyframe(session_id='sess',specimen_id='spec')
        assert ctl.state is S.CAPTURING
        assert not ctl.capture_keyframe(session_id='sess',specimen_id='spec')
        until(app, lambda:len(done)==1)
        assert ctl.state is S.STREAMING
        assert done[0].metadata.capture_id=='fake-1'
        assert camera.capture_count==1
        assert ctl.capture_keyframe(session_id='sess',specimen_id='spec')
        until(app,lambda:len(done)==2)
        assert done[0].metadata.capture_id != done[1].metadata.capture_id
        assert errors == []
        assert S.CAPTURING in states
        assert ctl.stop()
        until(app,lambda:ctl.state is S.CLOSED and ctl.safe_to_dispose)
    finally:
        close_controller(app,ctl)


def test_qt_capture_error_returns_to_streaming_without_false_success(app):
    camera=FakeCaptureProcessCamera('timeout')
    ctl=new_controller(camera)
    done=[]
    errors=[]
    ctl.keyframe_ready.connect(done.append)
    ctl.keyframe_failed.connect(errors.append)
    try:
        assert ctl.start()
        until(app,lambda:ctl.state is S.STREAMING)
        assert ctl.capture_keyframe(session_id='sess', specimen_id='spec')
        until(app,lambda:len(errors)==1)
        assert errors == ['CAPTURE_TIMEOUT']
        assert done == []
        assert ctl.state is S.STREAMING
        assert ctl.stop()
        until(app,lambda:ctl.safe_to_dispose)
    finally:
        close_controller(app,ctl)


def test_qt_stop_during_inflight_capture_does_not_emit_late_keyframe(app):
    camera=FakeCaptureProcessCamera('slow')
    ctl=new_controller(camera)
    done=[]
    ctl.keyframe_ready.connect(done.append)
    try:
        assert ctl.start()
        until(app,lambda:ctl.state is S.STREAMING)
        assert ctl.capture_keyframe(session_id='sess',specimen_id='spec')
        assert ctl.stop()
        until(app,lambda:ctl.safe_to_dispose)
        assert ctl.state is S.CLOSED
        assert done == []
    finally:
        close_controller(app,ctl)


def test_qt_fatal_capture_error_is_terminal_only_after_worker_cleanup(app):
    camera=FakeCaptureProcessCamera('fail_device')
    ctl=new_controller(camera)
    successes=[]
    errors=[]
    ctl.keyframe_ready.connect(successes.append)
    ctl.failure.connect(errors.append)
    try:
        assert ctl.start()
        until(app,lambda:ctl.state is S.STREAMING)
        assert ctl.capture_keyframe(session_id='sess',specimen_id='spec')
        until(app,lambda:ctl.safe_to_dispose and ctl.state is S.FAILED)
        assert successes == []
        assert ctl.error_code == 'DEVICE_PROCESS_CRASH'
        assert errors == ['DEVICE_PROCESS_CRASH']
    finally:
        close_controller(app,ctl)


def test_live_panel_preserves_manual_roi_while_capturing(app):
    from scantopath.modules.capture.presentation.live_capture_panel import LiveCapturePanel
    from scantopath.modules.capture.domain.models import DepthRoi
    panel=LiveCapturePanel()
    try:
        panel.set_state(S.STREAMING)
        roi=DepthRoi(x=2,y=3,width=12,height=14,frame_width=30,frame_height=40)
        panel.manual_button.setChecked(True)
        panel._on_manual_selected(roi)
        panel.set_state(S.CAPTURING)
        assert panel.manual_roi == roi
        assert panel.manual_button.isChecked()
        assert not panel.manual_button.isEnabled()
        assert panel.stop_button.isEnabled()
        panel.set_state(S.STREAMING)
        assert panel.manual_roi == roi
        assert panel.manual_button.isEnabled()
    finally:
        panel.deleteLater()
