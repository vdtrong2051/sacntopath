"""GD2-09.07.2 real Qt tests, fake camera; no SDK/SQLite writes."""
from __future__ import annotations

import os
import time

import numpy as np
import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
pytest.importorskip("PySide6")

from PySide6.QtCore import QPoint, Qt
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication

from scantopath.application.contracts import WorkspaceId
from scantopath.modules.capture.application.live_stream import LiveCaptureService, LiveNativeFrame
from scantopath.modules.capture.domain.models import CameraState, RoiSource
from scantopath.modules.capture.presentation.depth_roi_overlay import DepthRoiOverlay
from scantopath.modules.capture.presentation.live_worker import LiveStreamWorker
from scantopath.ui.shell import ScanToPathMainWindow


@pytest.fixture(scope="module")
def app():
    return QApplication.instance() or QApplication([])


def until(app, predicate, timeout=8):
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        app.processEvents()
        if predicate():
            return
        time.sleep(0.01)
    raise AssertionError("Qt lifecycle gate timed out")


class FakeCamera:
    def __init__(self):
        self.count = 0
        self.depth = np.full((80, 120), 1800, dtype="<u2")
        self.depth[20:52, 25:69] = 630

    def open(self):
        pass

    def read_next(self, *, per_attempt_timeout_ms, max_attempts):
        import time
        time.sleep(0.015)
        self.count += 1
        return LiveNativeFrame(
            color_mjpeg=b"fake", depth_y16_le=self.depth.tobytes(),
            color_width=120, color_height=80,
            depth_width=120, depth_height=80,
            color_frame_index=self.count, depth_frame_index=self.count,
            color_timestamp_us=self.count*1000, depth_timestamp_us=self.count*1000,
            depth_scale_m_per_unit=0.001,
            device_name="Orbbec Gemini 2", firmware="test-only",
        )

    def close(self):
        pass


class FakeDecoder:
    def decode(self, payload, *, width, height):
        assert payload == b"fake"
        return np.full((height, width, 3), 65, dtype=np.uint8)


def worker_factory():
    return LiveStreamWorker(
        service_factory=lambda: LiveCaptureService(FakeCamera(), FakeDecoder())
    )


def test_overlay_manual_roi_respects_letterbox_and_resize(app):
    widget = DepthRoiOverlay()
    widget.resize(300, 300)
    widget.set_depth_image(np.full((80, 120), 120, dtype=np.uint8))
    widget.set_manual_enabled(True)
    widget.show()
    app.processEvents()
    rect = widget.image_rect()
    assert rect.width() == pytest.approx(300)
    assert rect.height() == pytest.approx(200)
    assert rect.top() == pytest.approx(50)
    samples = []
    widget.manual_roi_selected.connect(samples.append)

    def drag(x0, y0, x1, y1):
        p0 = widget.image_to_widget(x0, y0)
        p1 = widget.image_to_widget(x1, y1)
        a = QPoint(round(p0.x()), round(p0.y()))
        b = QPoint(round(p1.x()), round(p1.y()))
        QTest.mousePress(widget, Qt.LeftButton, pos=a)
        QTest.mouseMove(widget, pos=b)
        QTest.mouseRelease(widget, Qt.LeftButton, pos=b)
        app.processEvents()

    drag(15, 12, 65, 44)
    assert len(samples) == 1
    roi = samples[-1]
    assert roi.source is RoiSource.MANUAL
    assert abs(roi.x - 15) <= 2
    assert abs(roi.y - 12) <= 2
    assert abs(roi.width - 50) <= 2
    assert abs(roi.height - 32) <= 2
    widget.resize(500, 250)
    app.processEvents()
    drag(30, 18, 90, 58)
    assert len(samples) == 2
    assert abs(samples[-1].x - 30) <= 2
    assert abs(samples[-1].y - 18) <= 2
    assert samples[-1].frame_width == 120
    assert samples[-1].frame_height == 80
    widget.close()


def test_overlay_rejects_letterbox_clicks_and_tiny_drag(app):
    widget = DepthRoiOverlay()
    widget.resize(300, 300)
    widget.set_depth_image(np.ones((80,120), dtype=np.uint8))
    widget.set_manual_enabled(True)
    widget.show()
    app.processEvents()
    selected = []
    widget.manual_roi_selected.connect(selected.append)
    QTest.mousePress(widget, Qt.LeftButton, pos=QPoint(30, 5))
    QTest.mouseRelease(widget, Qt.LeftButton, pos=QPoint(50, 10))
    QTest.mousePress(widget, Qt.LeftButton, pos=QPoint(150, 150))
    QTest.mouseRelease(widget, Qt.LeftButton, pos=QPoint(150, 150))
    app.processEvents()
    assert selected == []
    widget.close()


def test_live_panel_starts_on_explicit_click_and_preserves_replay(app):
    win = ScanToPathMainWindow()
    win.capture_live.camera._worker_factory = worker_factory
    try:
        # Creation and navigation must not open the camera.
        assert win.capture_live.state is CameraState.IDLE
        assert win.capture_live.safe_to_dispose
        assert win.findChild(DepthRoiOverlay, "captureLiveDepthOverlay") is not None
        assert win.capture_preview.panel.objectName() == "capturePreview"
        assert win.capture_preview.panel.replay_button.objectName() == "captureReplayButton"
        assert len(win._pages) == 4
        win.show()
        win._navigate(WorkspaceId.CAPTURE)
        app.processEvents()
        assert win.capture_live.state is CameraState.IDLE
        assert win.capture_live.start()
        until(app, lambda: win.capture_live.state is CameraState.STREAMING)
        until(app, lambda: win.capture_live.panel.depth_overlay.image_size == (120, 80))
        until(app, lambda: win.capture_live.panel.displayed_roi is not None)
        assert win.capture_live.panel.displayed_roi.source is RoiSource.DEPTH_SUGGESTION

        # Manual ROI is authoritative and not overwritten by later auto tracking.
        live_panel = win.capture_live.panel
        live_panel.manual_button.setChecked(True)
        overlay = live_panel.depth_overlay
        overlay.resize(360, 240)
        app.processEvents()
        a = overlay.image_to_widget(10, 10)
        b = overlay.image_to_widget(45, 35)
        QTest.mousePress(overlay, Qt.LeftButton, pos=QPoint(round(a.x()), round(a.y())))
        QTest.mouseMove(overlay, pos=QPoint(round(b.x()), round(b.y())))
        QTest.mouseRelease(overlay, Qt.LeftButton, pos=QPoint(round(b.x()), round(b.y())))
        app.processEvents()
        roi = live_panel.manual_roi
        assert roi is not None and roi.source is RoiSource.MANUAL
        until(app, lambda: live_panel.displayed_roi is not None)
        assert live_panel.displayed_roi == roi
        live_panel.use_auto()
        assert live_panel.manual_roi is None
        assert win.capture_live.stop()
        until(app, lambda: win.capture_live.state is CameraState.CLOSED)
        assert live_panel.displayed_roi is None
        assert live_panel.depth_overlay.image_size is None
        assert win.capture_live.start()
        until(app, lambda: win.capture_live.state is CameraState.STREAMING)
        until(app, lambda: live_panel.depth_overlay.image_size == (120, 80))
        # Leaving Capture stops live streaming without changing RAW replay.
        win._navigate(WorkspaceId.PROJECTS)
        until(app, lambda: win.capture_live.state is CameraState.CLOSED)
        assert win.capture_live.safe_to_dispose is False  # analyzer remains resident until shutdown
    finally:
        win.close()
        until(app, lambda: not win.isVisible())
        assert win.capture_live.safe_to_dispose


def test_close_window_while_streaming_is_cooperative(app):
    win = ScanToPathMainWindow()
    win.capture_live.camera._worker_factory = worker_factory
    win.show()
    try:
        assert win.capture_live.start()
        until(app, lambda: win.capture_live.state is CameraState.STREAMING)
        win.close()
        # QMainWindow close must be blocked until camera AND analyzer exit.
        until(app, lambda: not win.isVisible())
        assert win.capture_live.camera.safe_to_dispose
        assert win.capture_live.safe_to_dispose
        assert win.capture_live.state in (CameraState.CLOSED, CameraState.FAILED)
    finally:
        if win.isVisible():
            win.close()
            until(app, lambda: not win.isVisible())
