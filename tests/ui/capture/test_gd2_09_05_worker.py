
"""GD2-09.05 Qt worker tests: fake service only, no Gemini 2 hardware."""
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
    LiveCameraError,
    LiveCaptureService,
    LiveNativeFrame,
)
from scantopath.modules.capture.presentation.live_worker import (
    LiveStreamWorker,
)


@pytest.fixture(scope="module")
def qapp():
    return QApplication.instance() or QApplication([])


def _until(qapp, predicate, timeout=8.0):
    deadline = time.monotonic() + timeout

    while time.monotonic() < deadline:
        qapp.processEvents()

        if predicate():
            qapp.processEvents()
            return

        time.sleep(0.01)

    raise AssertionError(
        "Live worker did not reach expected state"
    )


class FakeCamera:
    def __init__(
        self,
        *,
        fail_open=False,
        fail_read=False,
    ):
        self.events = []
        self.fail_open = fail_open
        self.fail_read = fail_read

        self.counter = 0
        self.owner = None

        self._depth = np.array(
            [[0, 1], [500, 65535]],
            dtype="<u2",
        ).tobytes()

    def open(self):
        self.owner = threading.get_ident()
        self.events.append(("open", self.owner))

        if self.fail_open:
            raise LiveCameraError("OPEN_FAILED")

    def read_next(
        self,
        *,
        per_attempt_timeout_ms,
        max_attempts,
    ):
        assert self.owner == threading.get_ident()
        assert per_attempt_timeout_ms == 300
        assert max_attempts == 1

        if self.fail_read:
            raise LiveCameraError("READ_FAILED")

        time.sleep(0.004)
        self.counter += 1

        return LiveNativeFrame(
            color_mjpeg=b"jpeg",
            depth_y16_le=self._depth,
            color_width=4,
            color_height=3,
            depth_width=2,
            depth_height=2,
            color_frame_index=self.counter,
            depth_frame_index=self.counter,
            color_timestamp_us=self.counter * 1000,
            depth_timestamp_us=self.counter * 1000,
            depth_scale_m_per_unit=0.001,
            device_name="Orbbec Gemini 2",
            firmware="fake",
        )

    def close(self):
        assert self.owner == threading.get_ident()
        self.events.append(("close", self.owner))


class FakeDecoder:
    def decode(self, payload, *, width, height):
        assert payload == b"jpeg"

        return np.ones(
            (height, width, 3),
            dtype=np.uint8,
        )


def _worker(camera):
    return LiveStreamWorker(
        service_factory=lambda: LiveCaptureService(
            camera,
            FakeDecoder(),
        )
    )


def test_live_worker_latest_only_and_stop(qapp):
    camera = FakeCamera()
    worker = _worker(camera)
    notices = []

    worker.frame_available.connect(
        lambda: notices.append(True)
    )

    worker.start()

    try:
        _until(
            qapp,
            lambda: worker.stats()[0] >= 15,
        )

        published, dropped = worker.stats()

        assert published >= 15
        assert dropped >= 14

        # There is only one pending Qt wake-up.
        assert len(notices) <= 2

        frame = worker.take_latest()

        assert frame is not None
        assert frame.color_rgb.flags.owndata
        assert frame.depth_u16.flags.owndata

        assert not frame.color_rgb.flags.writeable
        assert not frame.depth_u16.flags.writeable

    finally:
        worker.request_stop()

        _until(
            qapp,
            lambda: not worker.isRunning(),
        )

    assert camera.events[0][0] == "open"
    assert camera.events[-1][0] == "close"

    assert (
        camera.events[0][1]
        == camera.events[-1][1]
    )


def test_open_failure_reports_code_and_closes(qapp):
    camera = FakeCamera(fail_open=True)
    worker = _worker(camera)
    errors = []

    worker.failed.connect(errors.append)
    worker.start()

    _until(
        qapp,
        lambda: not worker.isRunning() and bool(errors),
    )

    assert errors == ["OPEN_FAILED"]
    assert camera.events[-1][0] == "close"


def test_read_failure_reports_code_and_closes(qapp):
    camera = FakeCamera(fail_read=True)
    worker = _worker(camera)
    errors = []

    worker.failed.connect(errors.append)
    worker.start()

    _until(
        qapp,
        lambda: not worker.isRunning() and bool(errors),
    )

    assert errors == ["READ_FAILED"]
    assert camera.events[-1][0] == "close"


def test_stop_before_start_never_opens_camera(qapp):
    camera = FakeCamera()
    worker = _worker(camera)

    worker.request_stop()

    finished = []
    worker.finished.connect(
        lambda: finished.append(True)
    )

    worker.start()

    _until(
        qapp,
        lambda: bool(finished),
    )

    assert camera.events == []
