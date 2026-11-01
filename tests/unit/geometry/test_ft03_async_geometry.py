"""FT-03 pure worker/QtCore synthetic checks. No Gemini 2 hardware or VTK."""
from __future__ import annotations

from threading import Event
from time import monotonic, sleep
from types import SimpleNamespace as NS

import numpy as np
import pytest
from PySide6.QtWidgets import QApplication

from scantopath.modules.capture.application.live_calibration import LiveCalibrationSnapshot
from scantopath.modules.capture.application.live_stream import LiveNativeFrame, LiveRgbdFrame
from scantopath.modules.geometry.application.live_geometry import LiveGeometryService
from scantopath.modules.geometry.presentation.live_geometry_worker import LiveGeometryThread


def frame(index: int = 1, *, missing_calibration: bool = False) -> LiveRgbdFrame:
    depth = np.full((2, 3), 900, dtype="<u2")
    packet = NS(
        depth=NS(width=3, height=2), color=NS(width=5, height=4),
        depth_intrinsics=NS(width=3, height=2, fx=3., fy=3., cx=1., cy=1.),
        color_intrinsics=NS(width=5, height=4, fx=5., fy=5., cx=2., cy=2.),
        depth_distortion=NS(sdk_model=0, k1_k6_p1_p2=[0.]*8),
        color_distortion=NS(sdk_model=0, k1_k6_p1_p2=[0.]*8),
        depth_to_color=NS(rotation=[1.,0.,0.,0.,1.,0.,0.,0.,1.],
                          translation_mm=[0., 0., 0.]),
        depth_scale_m_per_unit=0.001, align_disabled=True,
    )
    c = None if missing_calibration else LiveCalibrationSnapshot.from_native_packet(packet)
    native = LiveNativeFrame(
        color_mjpeg=b"jpeg", depth_y16_le=depth.tobytes(), color_width=5,
        color_height=4, depth_width=3, depth_height=2,
        color_frame_index=index, depth_frame_index=index,
        color_timestamp_us=index*1000, depth_timestamp_us=index*1000,
        depth_scale_m_per_unit=0.001, device_name="Orbbec Gemini 2", firmware="fake",
        calibration=c, calibration_error="LIVE_CALIBRATION_MISSING" if c is None else None,
    )
    return LiveRgbdFrame(native, np.zeros((4,5,3), dtype=np.uint8), depth)


_APP = None


def poll(predicate, *, timeout=4.0):
    # QApplication, not QCoreApplication: other FT-03 tests construct QWidget.
    global _APP
    _APP = QApplication.instance() or QApplication([])
    app = _APP
    deadline = monotonic() + timeout
    while monotonic() < deadline:
        app.processEvents()
        if predicate():
            return True
        sleep(0.005)
    return False


def close(worker):
    worker.request_stop()
    assert worker.wait(5000), "FT-03 worker failed to terminate"


def test_async_01_geometry_runs_in_worker_and_no_cloud_in_qt_signal():
    main_ident = None
    from threading import get_ident
    main_ident = get_ident()
    executed = []

    def processor(f, **kwargs):
        executed.append(get_ident())
        return LiveGeometryService.process(f, **kwargs)

    worker = LiveGeometryThread(processor=processor)
    notified = []
    worker.result_available.connect(lambda: notified.append(True))
    try:
        worker.change_generation(1)
        worker.start()
        assert worker.submit(1, frame(1))
        assert poll(lambda: bool(notified))
        result = worker.take_latest_result()
        assert result is not None and result[0:2] == (1, 1)
        assert result[2] is not None and result[3] is None
        assert executed and executed[0] != main_ident
        assert result[2].points_xyz_m.shape == (6, 3)
        assert worker.statistics()["pending_output"] == 0
    finally:
        close(worker)


def test_async_02_bounded_latest_wins_and_nonmonotonic_rejection():
    entered, release = Event(), Event()

    def processor(f, **kwargs):
        if f.source.depth_frame_index == 1:
            entered.set()
            assert release.wait(3)
        return LiveGeometryService.process(f, **kwargs)

    worker = LiveGeometryThread(processor=processor)
    try:
        worker.change_generation(1)
        worker.start()
        assert worker.submit(1, frame(1))
        assert entered.wait(3)
        assert worker.submit(1, frame(2))
        assert worker.submit(1, frame(3))
        assert not worker.submit(1, frame(2))
        assert worker.statistics()["pending_input"] == 1
        release.set()
        assert poll(lambda: worker.statistics()["frames_processed"] >= 2)
        result = worker.take_latest_result()
        assert result is not None and result[1] == 3
        s = worker.statistics()
        assert s["frames_dropped_input"] >= 1
        assert s["frames_rejected_order"] >= 1
        assert s["pending_input"] == 0 and s["pending_output"] == 0
    finally:
        release.set()
        close(worker)


def test_async_03_stale_processing_cannot_publish_after_generation_change():
    entered, release = Event(), Event()

    def processor(f, **kwargs):
        if f.source.depth_frame_index == 1:
            entered.set()
            assert release.wait(3)
        return LiveGeometryService.process(f, **kwargs)

    worker = LiveGeometryThread(processor=processor)
    try:
        worker.change_generation(1)
        worker.start()
        assert worker.submit(1, frame(1))
        assert entered.wait(3)
        worker.change_generation(2)
        assert not worker.submit(1, frame(2))
        assert worker.submit(2, frame(2))
        release.set()
        assert poll(lambda: worker.statistics()["frames_published"] == 1)
        result = worker.take_latest_result()
        assert result is not None and result[0:2] == (2, 2)
        assert worker.statistics()["frames_rejected_stale"] >= 1
    finally:
        release.set()
        close(worker)


def test_async_04_missing_calibration_reports_stable_error_and_recovers():
    worker = LiveGeometryThread()
    try:
        worker.change_generation(1)
        worker.start()
        assert worker.submit(1, frame(1, missing_calibration=True))
        assert poll(lambda: worker.statistics()["geometry_errors"] == 1)
        result = worker.take_latest_result()
        assert result[2] is None and result[3] == "LIVE_CALIBRATION_MISSING"
        assert worker.submit(1, frame(2))
        assert poll(lambda: worker.statistics()["frames_published"] == 1)
        result = worker.take_latest_result()
        assert result[2] is not None and result[3] is None
    finally:
        close(worker)


def test_async_05_stop_during_active_processing_never_publishes_stale():
    entered, release = Event(), Event()

    def processor(f, **kwargs):
        entered.set()
        assert release.wait(3)
        return LiveGeometryService.process(f, **kwargs)

    worker = LiveGeometryThread(processor=processor)
    worker.change_generation(1)
    worker.start()
    try:
        assert worker.submit(1, frame(1))
        assert entered.wait(3)
        worker.request_stop()
        assert not worker.submit(1, frame(2))
        release.set()
        assert worker.wait(5000)
        assert worker.take_latest_result() is None
        assert worker.statistics()["frames_published"] == 0
    finally:
        release.set()
        if worker.isRunning():
            close(worker)


def test_async_06_roi_lineage_and_bounded_input_output():
    worker = LiveGeometryThread()
    try:
        worker.change_generation(3)
        worker.start()
        assert worker.submit(3, frame(1), depth_roi=(1, 0, 2, 2))
        assert poll(lambda: worker.statistics()["frames_published"] == 1)
        result = worker.take_latest_result()
        assert result[2].statistics.output_points == 4
        assert result[2].camera_generation == 3
        assert result[2].units == "m"
        assert worker.statistics()["pending_input"] <= 1
        assert worker.statistics()["pending_output"] <= 1
    finally:
        close(worker)


def test_async_07_shutdown_generation_barrier_can_repeat_before_thread_reaped():
    worker = LiveGeometryThread()
    worker.change_generation(1)
    worker.start()
    worker.request_stop()
    # Qt's camera STOPPING and CLOSED callbacks can advance generation even while
    # geometry is finishing; this must not throw or allow new frames.
    worker.change_generation(2)
    worker.change_generation(3)
    assert not worker.submit(3, frame(3))
    assert worker.wait(5000)
    assert worker.statistics()["camera_generation"] == 3
