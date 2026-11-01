"""FT-03 Capture/Qt fanout integration, synthetic camera; no SDK or disk writes."""
from __future__ import annotations

from time import monotonic, sleep
from types import SimpleNamespace as NS

import numpy as np
from PySide6.QtWidgets import QApplication, QVBoxLayout, QWidget

from scantopath.application.contracts import WorkspaceId
from scantopath.modules.capture.application.live_calibration import LiveCalibrationSnapshot
from scantopath.modules.capture.application.live_stream import LiveCaptureService, LiveNativeFrame
from scantopath.modules.capture.domain.models import CameraState
from scantopath.modules.capture.presentation.live_worker import LiveStreamWorker
from scantopath.modules.capture.presentation.live_ui_controller import LiveCaptureUiController


def fake_frame(index):
    depth = np.full((4, 6), 1000, dtype="<u2")
    packet = NS(
        depth=NS(width=6, height=4), color=NS(width=8, height=6),
        depth_intrinsics=NS(width=6, height=4, fx=6., fy=6., cx=2.5, cy=1.5),
        color_intrinsics=NS(width=8, height=6, fx=8., fy=8., cx=3.5, cy=2.5),
        depth_distortion=NS(sdk_model=0, k1_k6_p1_p2=[0.]*8),
        color_distortion=NS(sdk_model=0, k1_k6_p1_p2=[0.]*8),
        depth_to_color=NS(rotation=[1.,0.,0.,0.,1.,0.,0.,0.,1.],
                          translation_mm=[0.,0.,0.]),
        depth_scale_m_per_unit=.001, align_disabled=True,
    )
    return LiveNativeFrame(
        color_mjpeg=b"synthetic", depth_y16_le=depth.tobytes(),
        color_width=8, color_height=6, depth_width=6, depth_height=4,
        color_frame_index=index, depth_frame_index=index,
        color_timestamp_us=index*1000, depth_timestamp_us=index*1000,
        depth_scale_m_per_unit=.001, device_name="Orbbec Gemini 2",
        firmware="fake", calibration=LiveCalibrationSnapshot.from_native_packet(packet),
    )


class FakeCamera:
    def __init__(self):
        self.i = 0
    def open(self):
        self.i = 0
    def read_next(self, **kwargs):
        sleep(0.015)
        self.i += 1
        return fake_frame(self.i)
    def close(self):
        pass
    def capture_next_raw(self, **kwargs):
        raise AssertionError("FT-03 must never capture RAW")


class FakeDecoder:
    def decode(self, data, *, width, height):
        return np.zeros((height, width, 3), dtype=np.uint8)


class FakeView(QWidget):
    def __init__(self):
        super().__init__()
        self.capture_preview = NS(panel=QWidget())
        self.workspace = QWidget(self)
        layout = QVBoxLayout(self.workspace)
        host = QWidget(self.workspace)
        host.setObjectName("workspaceScrollContent")
        host_layout = QVBoxLayout(host)
        host_layout.addWidget(self.capture_preview.panel)
        layout.addWidget(host)
    def page_for(self, workspace):
        assert workspace == WorkspaceId.CAPTURE
        return self.workspace


def spin(app, cond, timeout=5.0):
    until = monotonic() + timeout
    while monotonic() < until:
        app.processEvents()
        if cond():
            return True
        sleep(0.005)
    return False


def test_async_07_live_controller_preview_and_geometry_fanout(monkeypatch):
    app = QApplication.instance() or QApplication([])
    view = FakeView()
    worker_factory = lambda: LiveStreamWorker(
        service_factory=lambda: LiveCaptureService(FakeCamera(), FakeDecoder()))
    controller = LiveCaptureUiController(view, worker_factory=worker_factory)
    outputs, errors = [], []
    controller.geometry_available.connect(lambda: outputs.append(controller.take_latest_geometry()))
    controller.geometry_failed.connect(errors.append)
    try:
        assert controller.start()
        assert spin(app, lambda: controller.state is CameraState.STREAMING)
        assert spin(app, lambda: len(outputs) >= 2)
        assert outputs[-1] is not None
        assert outputs[-1].statistics.output_points == 24
        assert controller.geometry_statistics()["frames_published"] >= 2
        assert errors == []
        assert controller.stop()
        assert spin(app, lambda: controller.state is CameraState.CLOSED)
        previous = controller._generation
        assert controller.take_latest_geometry() is None
        assert controller.start()
        assert spin(app, lambda: controller.state is CameraState.STREAMING)
        assert spin(app, lambda: controller.geometry_statistics()["camera_generation"] > previous)
        assert spin(app, lambda: len(outputs) >= 3)
    finally:
        controller.begin_shutdown()
        assert spin(app, lambda: controller.safe_to_dispose, timeout=8.0)
        view.close()
