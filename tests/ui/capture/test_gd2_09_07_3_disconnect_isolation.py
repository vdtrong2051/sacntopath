"""Qt lifecycle integration: a fatal child exit must not terminate the GUI."""
from __future__ import annotations
import os
import time

import numpy as np
import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
pytest.importorskip("PySide6")
from PySide6.QtWidgets import QApplication

from scantopath.modules.capture.application.live_stream import LiveCaptureService
from scantopath.modules.capture.domain.models import CameraState
from scantopath.modules.capture.infrastructure.process_camera import ProcessIsolatedCameraAdapter
from scantopath.modules.capture.presentation.live_controller import LiveCameraController
from scantopath.modules.capture.presentation.live_worker import LiveStreamWorker
from tests.support.process_camera_fakes import crash_read_camera, crash_close_camera


class _FakeDecoder:
    def decode(self, payload, *, width, height):
        assert payload == b"fake-jpeg"
        return np.zeros((height, width, 3), dtype=np.uint8)


@pytest.fixture(scope="module")
def app():
    return QApplication.instance() or QApplication([])


def _run_controller(app, factory):
    ctl = LiveCameraController(
        worker_factory=lambda: LiveStreamWorker(
            service_factory=lambda: LiveCaptureService(
                ProcessIsolatedCameraAdapter(camera_factory=factory), _FakeDecoder()
            )
        )
    )
    states, errors = [], []
    ctl.state_changed.connect(states.append)
    ctl.failure.connect(errors.append)
    assert ctl.start()
    deadline = time.monotonic() + 20
    while time.monotonic() < deadline:
        app.processEvents()
        if ctl.state is CameraState.FAILED and ctl.safe_to_dispose:
            break
        time.sleep(0.01)
    assert ctl.safe_to_dispose
    assert ctl.state is CameraState.FAILED
    assert ctl.error_code == "DEVICE_PROCESS_CRASH"
    assert errors == ["DEVICE_PROCESS_CRASH"]
    assert CameraState.OPENING in states
    assert CameraState.FAILED in states
    assert ctl.request_shutdown()
    app.processEvents()


def test_child_crashes_on_read_but_gui_stays_alive(app):
    _run_controller(app, crash_read_camera)


def test_child_crashes_on_close_but_gui_stays_alive(app):
    # The controller sends a stop after the first decoded frame.
    factory = crash_close_camera
    ctl = LiveCameraController(
        worker_factory=lambda: LiveStreamWorker(
            service_factory=lambda: LiveCaptureService(
                ProcessIsolatedCameraAdapter(camera_factory=factory), _FakeDecoder()
            )
        )
    )
    errors = []
    ctl.failure.connect(errors.append)
    assert ctl.start()
    deadline = time.monotonic() + 20
    stopped = False
    while time.monotonic() < deadline:
        app.processEvents()
        if ctl.state is CameraState.STREAMING and ctl.stats()[0] >= 2 and not stopped:
            assert ctl.stop()
            stopped = True
        if ctl.state is CameraState.FAILED and ctl.safe_to_dispose:
            break
        time.sleep(0.01)
    assert stopped
    assert ctl.safe_to_dispose
    assert ctl.state is CameraState.FAILED
    assert ctl.error_code == "DEVICE_PROCESS_CRASH"
    assert errors == ["DEVICE_PROCESS_CRASH"]
    assert ctl.request_shutdown()
    app.processEvents()
