"""Spawn-safe fake cameras for GD2-09.08.1. Never load SDK."""
from __future__ import annotations
import os
import time

from scantopath.modules.capture.application.live_stream import LiveNativeFrame, LiveCameraError
from tests.support.raw_fixture import raw


class FakeCaptureProcessCamera:
    def __init__(self, mode: str = 'normal'):
        self.mode = mode
        self.preview_count = 0
        self.capture_count = 0
        self.opened = False

    def open(self):
        self.opened = True

    def read_next(self, *, per_attempt_timeout_ms, max_attempts):
        assert self.opened and max_attempts == 1
        time.sleep(0.005)
        self.preview_count += 1
        i = self.preview_count
        return LiveNativeFrame(
            color_mjpeg=b'preview-not-a-valid-jpeg',
            depth_y16_le=b'\x02\x00' * 6,
            color_width=4, color_height=3, depth_width=3, depth_height=2,
            color_frame_index=i, depth_frame_index=i,
            color_timestamp_us=i*1000, depth_timestamp_us=i*1000,
            depth_scale_m_per_unit=0.001,
            device_name='Orbbec Gemini 2', firmware='fake'
        )

    def capture_next_raw(self, *, session_id, specimen_id):
        assert self.opened
        if self.mode == 'crash':
            os._exit(95)
        if self.mode == 'fail_device':
            raise LiveCameraError('DEVICE_PROCESS_CRASH')
        if self.mode == 'timeout':
            raise TimeoutError('capture bounded timeout')
        if self.mode == 'invalid':
            return object()
        self.capture_count += 1
        if self.mode == 'wrong_context':
            return raw(session='wrong_session', specimen=specimen_id, capture_id='fake-1')
        if self.mode == 'slow':
            time.sleep(0.20)
        return raw(session=session_id, specimen=specimen_id, capture_id=f'fake-{self.capture_count}')

    def close(self):
        self.opened = False


def normal_capture_camera():
    return FakeCaptureProcessCamera()


def crash_capture_camera():
    return FakeCaptureProcessCamera('crash')


def timeout_capture_camera():
    return FakeCaptureProcessCamera('timeout')


def invalid_capture_camera():
    return FakeCaptureProcessCamera('invalid')


def wrong_context_camera():
    return FakeCaptureProcessCamera('wrong_context')
