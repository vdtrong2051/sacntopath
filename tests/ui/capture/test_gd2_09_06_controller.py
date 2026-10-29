"""GD2-09.06 Qt lifecycle integration tests; no physical camera or SDK."""
from __future__ import annotations

import os
import threading
import time

import numpy as np
import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
pytest.importorskip("PySide6")

from PySide6.QtWidgets import QApplication

from scantopath.modules.capture.application.live_stream import (
    LiveCameraError, LiveCaptureService, LiveNativeFrame,
)
from scantopath.modules.capture.domain.models import CameraState as S
from scantopath.modules.capture.presentation.live_controller import LiveCameraController
from scantopath.modules.capture.presentation.live_worker import LiveStreamWorker


@pytest.fixture(scope="module")
def app():
    return QApplication.instance() or QApplication([])


def until(app, predicate, timeout=5):
    end = time.monotonic() + timeout
    while time.monotonic() < end:
        app.processEvents()
        if predicate():
            app.processEvents()
            return
        time.sleep(0.005)
    raise AssertionError("QT_LIFECYCLE_WAIT_TIMEOUT")


class FakeDecoder:
    def decode(self, payload, *, width, height):
        return np.zeros((height, width, 3), dtype=np.uint8)


class FakeCamera:
    def __init__(self, *, open_delay=0, read_delay=0.01, fail_open=False,
                 fail_read=False, fail_close=False, read_timeouts=False):
        self.open_delay = open_delay
        self.read_delay = read_delay
        self.fail_open = fail_open
        self.fail_read = fail_read
        self.fail_close = fail_close
        self.read_timeouts = read_timeouts
        self.events = []
        self.owner = None
        self.counter = 0
        self.read_entered = threading.Event()

    def open(self):
        self.owner = threading.get_ident()
        self.events.append("open")
        time.sleep(self.open_delay)
        if self.fail_open:
            raise LiveCameraError("OPEN_FAILED")

    def read_next(self, *, per_attempt_timeout_ms, max_attempts):
        assert self.owner == threading.get_ident()
        assert per_attempt_timeout_ms == 300 and max_attempts == 1
        self.read_entered.set()
        time.sleep(self.read_delay)
        if self.fail_read:
            raise LiveCameraError("READ_FAILED")
        if self.read_timeouts:
            raise TimeoutError("fake bounded read timeout")
        self.counter += 1
        return LiveNativeFrame(
            color_mjpeg=b"fake-jpeg", depth_y16_le=b"\0\0" * 6,
            color_width=4, color_height=3, depth_width=3, depth_height=2,
            color_frame_index=self.counter, depth_frame_index=self.counter,
            color_timestamp_us=self.counter * 1000,
            depth_timestamp_us=self.counter * 1000,
            depth_scale_m_per_unit=0.001, device_name="Orbbec Gemini 2",
            firmware="fake",
        )

    def close(self):
        assert self.owner == threading.get_ident()
        self.events.append("close")
        if self.fail_close:
            raise LiveCameraError("CLOSE_FAILED")


def new_controller(cameras, *, opening_timeout_ms=5000, stopping_timeout_ms=5000):
    def factory():
        camera = cameras[len(created)]
        created.append(camera)
        return LiveStreamWorker(
            service_factory=lambda: LiveCaptureService(camera, FakeDecoder())
        )
    created = []
    return LiveCameraController(
        worker_factory=factory,
        opening_timeout_ms=opening_timeout_ms,
        stopping_timeout_ms=stopping_timeout_ms,
    )


def terminate_cleanly(app, controller):
    controller.request_shutdown()
    until(app, lambda: controller.safe_to_dispose)
    app.processEvents()


def test_start_stream_stop_reopen_without_double_open(app):
    cameras = [FakeCamera(), FakeCamera()]
    ctl = new_controller(cameras)
    states = []
    ctl.state_changed.connect(states.append)
    try:
        assert ctl.state is S.IDLE
        assert ctl.start()
        assert ctl.state is S.OPENING
        assert not ctl.start()
        until(app, lambda: ctl.state is S.STREAMING)
        until(app, lambda: cameras[0].counter >= 3)
        assert ctl.take_latest() is not None
        assert ctl.stop()
        assert not ctl.start()  # no restart until old worker is reaped
        until(app, lambda: ctl.state is S.CLOSED and ctl.safe_to_dispose)
        assert cameras[0].events.count("open") == 1
        assert cameras[0].events.count("close") == 1
        assert ctl.start()
        until(app, lambda: ctl.state is S.STREAMING)
        assert ctl.stop()
        until(app, lambda: ctl.state is S.CLOSED and ctl.safe_to_dispose)
        assert cameras[1].events.count("open") == 1
        assert cameras[1].events.count("close") == 1
        assert states.count(S.STREAMING) == 2
    finally:
        terminate_cleanly(app, ctl)


def test_stop_during_open_does_not_late_stream(app):
    camera = FakeCamera(open_delay=0.10)
    ctl = new_controller([camera])
    try:
        assert ctl.start()
        assert ctl.stop()
        until(app, lambda: ctl.safe_to_dispose and ctl.state is S.CLOSED)
        assert camera.events == ["open", "close"] or camera.events == []
        assert ctl.take_latest() is None
    finally:
        terminate_cleanly(app, ctl)


def test_open_failure_retry_only_after_cleanup(app):
    cameras = [FakeCamera(fail_open=True), FakeCamera()]
    ctl = new_controller(cameras)
    errors = []
    ctl.failure.connect(errors.append)
    try:
        assert ctl.start()
        until(app, lambda: ctl.safe_to_dispose and ctl.state is S.FAILED)
        assert ctl.error_code == "OPEN_FAILED"
        assert errors == ["OPEN_FAILED"]
        assert not ctl.stop()
        assert ctl.retry()
        until(app, lambda: ctl.state is S.STREAMING)
        assert ctl.stop()
        until(app, lambda: ctl.state is S.CLOSED and ctl.safe_to_dispose)
        assert camera_events_closed(cameras)
    finally:
        terminate_cleanly(app, ctl)


def camera_events_closed(cameras):
    return all(c.events.count("close") == 1 for c in cameras)


def test_read_failure_never_false_closed(app):
    camera = FakeCamera(fail_read=True)
    ctl = new_controller([camera])
    try:
        assert ctl.start()
        until(app, lambda: ctl.safe_to_dispose and ctl.state is S.FAILED)
        assert ctl.error_code == "READ_FAILED"
        assert camera.events[-1] == "close"
    finally:
        terminate_cleanly(app, ctl)


def test_open_timeout_waits_for_real_native_cleanup(app):
    camera = FakeCamera(open_delay=0.15)
    ctl = new_controller([camera], opening_timeout_ms=20)
    try:
        assert ctl.start()
        until(app, lambda: ctl.state is S.STOPPING)
        assert not ctl.safe_to_dispose  # no fake CLOSED before exit
        assert not ctl.start()
        until(app, lambda: ctl.safe_to_dispose and ctl.state is S.FAILED)
        assert ctl.error_code == "OPEN_TIMEOUT"
        assert camera.events[-1] == "close"
    finally:
        terminate_cleanly(app, ctl)


def test_stop_timeout_does_not_destroy_active_worker(app):
    camera = FakeCamera(read_delay=0.18)
    ctl = new_controller([camera], stopping_timeout_ms=20)
    try:
        assert ctl.start()
        until(app, lambda: ctl.state is S.STREAMING and camera.read_entered.is_set())
        assert ctl.stop()
        until(app, lambda: ctl.error_code == "STOP_TIMEOUT")
        assert ctl.state is S.STOPPING and not ctl.safe_to_dispose
        until(app, lambda: ctl.safe_to_dispose and ctl.state is S.FAILED)
        assert camera.events[-1] == "close"
    finally:
        terminate_cleanly(app, ctl)


def test_close_failure_after_stop_reported(app):
    camera = FakeCamera(fail_close=True)
    ctl = new_controller([camera])
    try:
        assert ctl.start()
        until(app, lambda: ctl.state is S.STREAMING)
        assert ctl.stop()
        until(app, lambda: ctl.safe_to_dispose and ctl.state is S.FAILED)
        assert ctl.error_code == "CLOSE_FAILED"
    finally:
        terminate_cleanly(app, ctl)


def test_shutdown_handshake_prevents_restart(app):
    camera = FakeCamera()
    ctl = new_controller([camera])
    ready = []
    ctl.shutdown_ready.connect(lambda: ready.append(True))
    assert ctl.start()
    until(app, lambda: ctl.state is S.STREAMING)
    assert ctl.request_shutdown() is False
    assert not ctl.start()
    until(app, lambda: bool(ready) and ctl.safe_to_dispose)
    assert ctl.state is S.CLOSED
    assert not ctl.start()


def test_no_frame_leaks_during_stop(app):
    camera = FakeCamera()
    ctl = new_controller([camera])
    try:
        assert ctl.start()
        until(app, lambda: ctl.state is S.STREAMING)
        until(app, lambda: camera.counter > 2)
        assert ctl.stop()
        assert ctl.take_latest() is None
        until(app, lambda: ctl.safe_to_dispose)
    finally:
        terminate_cleanly(app, ctl)


def test_failed_factory_is_terminal_without_leaking_worker(app):
    ctl = LiveCameraController(worker_factory=lambda: object())
    errors = []
    ctl.failure.connect(errors.append)
    assert ctl.start() is False
    assert ctl.state is S.FAILED
    assert ctl.safe_to_dispose
    assert errors == ["START_FAILED"]


def test_unexpected_worker_exit_reports_failure(app):
    camera = FakeCamera()
    created = []

    def factory():
        worker = LiveStreamWorker(
            service_factory=lambda: LiveCaptureService(camera, FakeDecoder())
        )
        created.append(worker)
        return worker

    ctl = LiveCameraController(worker_factory=factory)
    errors = []
    ctl.failure.connect(errors.append)
    try:
        assert ctl.start()
        until(app, lambda: ctl.state is S.STREAMING)
        # Simulate unexpected worker exit without requesting controller stop.
        created[0].request_stop()
        until(app, lambda: ctl.safe_to_dispose and ctl.state is S.FAILED)
        assert ctl.error_code == "WORKER_UNEXPECTED_EXIT"
        assert errors == ["WORKER_UNEXPECTED_EXIT"]
    finally:
        terminate_cleanly(app, ctl)
