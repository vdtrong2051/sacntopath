"""Top-level, picklable test cameras for process-isolation integration tests."""
from __future__ import annotations
import os
import time

from scantopath.modules.capture.application.live_stream import LiveCameraError, LiveNativeFrame


class FakeProcessCamera:
    def __init__(self, mode: str):
        self.mode = mode
        self.frame_index = 0

    def open(self):
        if self.mode == "exit_open":
            os._exit(91)
        if self.mode == "fail_open":
            raise LiveCameraError("OPEN_FAILED")

    def read_next(self, *, per_attempt_timeout_ms: int, max_attempts: int):
        assert max_attempts == 1
        if self.mode == "exit_read":
            os._exit(93)
        if self.mode == "hang_read":
            time.sleep(10)
        if self.mode == "timeout":
            raise TimeoutError("simulated dropped frameset")
        if self.mode == "read_error":
            raise LiveCameraError("READ_FAILED")
        if self.mode == "invalid_packet":
            return object()
        self.frame_index += 1
        return LiveNativeFrame(
            color_mjpeg=b"fake-jpeg",
            depth_y16_le=b"\x02\x00" * 6,
            color_width=4,
            color_height=3,
            depth_width=3,
            depth_height=2,
            color_frame_index=self.frame_index,
            depth_frame_index=self.frame_index,
            color_timestamp_us=1000 * self.frame_index,
            depth_timestamp_us=1000 * self.frame_index,
            depth_scale_m_per_unit=0.001,
            device_name="Orbbec Gemini 2",
            firmware="fake",
        )

    def close(self):
        if self.mode == "exit_close":
            os._exit(92)


def normal_camera():
    return FakeProcessCamera("normal")

def crash_open_camera():
    return FakeProcessCamera("exit_open")

def crash_read_camera():
    return FakeProcessCamera("exit_read")

def crash_close_camera():
    return FakeProcessCamera("exit_close")

def timeout_camera():
    return FakeProcessCamera("timeout")

def fail_open_camera():
    return FakeProcessCamera("fail_open")

def read_error_camera():
    return FakeProcessCamera("read_error")

def invalid_packet_camera():
    return FakeProcessCamera("invalid_packet")

def hang_camera():
    return FakeProcessCamera("hang_read")
