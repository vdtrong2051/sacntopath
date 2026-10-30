"""GD2-09.08.1: keyframe IPC, calibration, stale preview, lifecycle.

These tests never open physical Gemini 2, never write RAW or SQLite.
"""
from __future__ import annotations
from types import SimpleNamespace as NS

import pytest

from scantopath.acquisition.raw_rgbd import RawRgbdCapture
from scantopath.modules.capture.application.lifecycle import CameraLifecycle
from scantopath.modules.capture.application.live_stream import LiveCameraError, LiveCaptureService
from scantopath.modules.capture.domain.models import CameraState as S
from scantopath.modules.capture.infrastructure.native_camera import Gemini2NativeCameraAdapter
from scantopath.modules.capture.infrastructure.process_camera import ProcessIsolatedCameraAdapter
from tests.support.keyframe_camera_fakes import (
    normal_capture_camera, crash_capture_camera, timeout_capture_camera,
    invalid_capture_camera, wrong_context_camera,
)


class Decoder:
    def decode(self, payload, *, width, height):
        import numpy as np
        return np.zeros((height, width, 3), dtype='uint8')


def test_ipc_capture_is_distinct_from_preview_and_returns_owned_raw():
    adapter = ProcessIsolatedCameraAdapter(camera_factory=normal_capture_camera)
    adapter.open()
    try:
        preview = adapter.read_next(per_attempt_timeout_ms=300, max_attempts=1)
        assert preview.color_mjpeg.startswith(b'preview-')
        p1 = adapter.capture_next_raw(session_id='sess', specimen_id='spec')
        p2 = adapter.capture_next_raw(session_id='sess', specimen_id='spec')
        assert isinstance(p1, RawRgbdCapture)
        assert isinstance(p2, RawRgbdCapture)
        assert p1.metadata.capture_id != p2.metadata.capture_id
        assert p1.color_mjpeg.startswith(b'\xff\xd8')
        assert p1.color_mjpeg != preview.color_mjpeg
        assert p1.metadata.color_intrinsics.fx == 4.0
        assert p1.metadata.camera_pose is None
        assert p1.metadata.alignment_mode == 'disabled'
        assert p1.metadata.depth_scale_m_per_unit == 0.001
    finally:
        adapter.close()
    assert adapter.child_pid is None
    assert adapter.last_exit_code == 0


def test_capture_port_not_available_when_camera_closed():
    a = ProcessIsolatedCameraAdapter(camera_factory=normal_capture_camera)
    with pytest.raises(LiveCameraError, match='NOT_OPEN'):
        a.capture_next_raw(session_id='sess', specimen_id='spec')


def test_child_crash_on_capture_keeps_parent_alive():
    a = ProcessIsolatedCameraAdapter(camera_factory=crash_capture_camera)
    a.open()
    try:
        with pytest.raises(LiveCameraError) as e:
            a.capture_next_raw(session_id='sess', specimen_id='spec')
        assert e.value.code == 'DEVICE_PROCESS_CRASH'
    finally:
        try:
            a.close()
        except LiveCameraError:
            pass
    assert a.child_pid is None
    assert a.last_exit_code == 95


def test_capture_timeout_is_recoverable():
    a = ProcessIsolatedCameraAdapter(camera_factory=timeout_capture_camera)
    a.open()
    try:
        with pytest.raises(LiveCameraError) as e:
            a.capture_next_raw(session_id='sess', specimen_id='spec')
        assert e.value.code == 'CAPTURE_TIMEOUT'
        assert a.read_next(per_attempt_timeout_ms=300, max_attempts=1) is not None
    finally:
        a.close()
    assert a.last_exit_code == 0


def test_capture_invalid_packet_rejected_and_preview_remains_available():
    a = ProcessIsolatedCameraAdapter(camera_factory=invalid_capture_camera)
    a.open()
    try:
        with pytest.raises(LiveCameraError) as e:
            a.capture_next_raw(session_id='sess', specimen_id='spec')
        assert e.value.code == 'INVALID_KEYFRAME'
        assert a.read_next(per_attempt_timeout_ms=300, max_attempts=1) is not None
    finally:
        a.close()


def test_ipc_rejects_wrong_context():
    a = ProcessIsolatedCameraAdapter(camera_factory=wrong_context_camera)
    a.open()
    try:
        with pytest.raises(LiveCameraError) as e:
            a.capture_next_raw(session_id='sess', specimen_id='spec')
        assert e.value.code == 'INVALID_DEVICE_RESPONSE'
    finally:
        a.close()


def test_service_reuses_open_camera_and_does_not_touch_preview_buffer():
    camera = normal_capture_camera()
    service = LiveCaptureService(camera, Decoder())
    with pytest.raises(LiveCameraError) as e:
        service.capture_keyframe(session_id='sess', specimen_id='spec')
    assert e.value.code == 'NOT_OPEN'
    service.open()
    try:
        live = service.read_next()
        cap = service.capture_keyframe(session_id='sess', specimen_id='spec')
        assert cap.metadata.capture_id == 'fake-1'
        assert camera.preview_count == 1
        assert camera.capture_count == 1
        assert live.source.color_mjpeg != cap.color_mjpeg
    finally:
        service.close()


def test_lifecycle_capture_success_duplicate_stop_and_worker_failure():
    m = CameraLifecycle()
    assert not m.begin_capture()
    assert m.start() and m.opened()
    assert m.begin_capture() and m.state is S.CAPTURING
    assert not m.begin_capture()
    assert m.capture_finished() and m.state is S.STREAMING
    assert not m.capture_finished()
    assert m.begin_capture()
    assert m.stop() and m.state is S.STOPPING
    assert not m.capture_finished()
    assert m.finished() is S.CLOSED
    assert m.start() and m.opened() and m.begin_capture()
    m.record_failure('DEVICE_PROCESS_CRASH')
    assert not m.capture_finished()
    assert m.finished() is S.FAILED
    assert m.error_code == 'DEVICE_PROCESS_CRASH'


def _packet(index):
    zeros = (0.0,) * 8
    color = NS(encoding=NS(name='MJPEG'), bytes=b'\xff\xd8abc\xff\xd9',
               width=5, height=4, frame_index=index, timestamp_us=100000 + 1000*index)
    depth = NS(encoding=NS(name='Y16'), bytes=b'\x03\x00'*6,
               width=3, height=2, frame_index=index, timestamp_us=100500 + 1000*index)
    return NS(
        validate=lambda: True, align_disabled=True, frame_sync_requested=True,
        color=color, depth=depth,
        device=NS(name='Orbbec Gemini 2', firmware='test', usb_connection='USB3.0',pid=1648),
        color_intrinsics=NS(width=5,height=4,fx=4.,fy=4.,cx=2.,cy=2.),
        depth_intrinsics=NS(width=3,height=2,fx=3.,fy=3.,cx=1.,cy=1.),
        color_distortion=NS(sdk_model=0,k1_k6_p1_p2=zeros),
        depth_distortion=NS(sdk_model=0,k1_k6_p1_p2=zeros),
        depth_to_color=NS(rotation=(1.,0.,0.,0.,1.,0.,0.,0.,1.), translation_mm=(-13.7,0.,0.)),
        depth_scale_m_per_unit=0.001,
    )


class NativeSource:
    def __init__(self, *, stale=False):
        self.i=0
        self.stale=stale
    def open(self):pass
    def read_next(self, **kwargs):
        self.i += 1
        return _packet(1 if self.stale else self.i)
    def close(self):pass


def test_native_capture_from_live_source_has_sdk_calibration_and_new_frame():
    source=NativeSource()
    a=Gemini2NativeCameraAdapter(native_loader=lambda: NS(OrbbecCameraSource=lambda: source))
    a.open()
    try:
        preview=a.read_next(per_attempt_timeout_ms=300,max_attempts=1)
        cap=a.capture_next_raw(session_id='sess',specimen_id='spec')
        assert preview.color_frame_index == 1
        assert cap.metadata.color.frame_index == 2
        assert cap.metadata.kind.value == 'orbbec'
        assert cap.metadata.measured is True
        assert cap.metadata.depth_to_color.translation_mm == (-13.7,0.,0.)
        assert cap.metadata.color_intrinsics.width == 5
        assert cap.metadata.depth_intrinsics.width == 3
        assert cap.metadata.depth_distortion.k1_k6_p1_p2 == (0.0,)*8
        assert cap.metadata.camera_pose is None
    finally:
        a.close()


def test_native_rejects_repeated_frameset_after_preview():
    a=Gemini2NativeCameraAdapter(native_loader=lambda: NS(OrbbecCameraSource=lambda: NativeSource(stale=True)))
    a.open()
    try:
        a.read_next(per_attempt_timeout_ms=300,max_attempts=1)
        with pytest.raises(LiveCameraError) as e:
            a.capture_next_raw(session_id='sess',specimen_id='spec')
        assert e.value.code == 'INVALID_KEYFRAME'
    finally:
        a.close()
