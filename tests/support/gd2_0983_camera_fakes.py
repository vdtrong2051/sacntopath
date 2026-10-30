"""09.08.3 deterministic, spawn-safe process fake; synthetic fixtures remain synthetic.

Never loads native SDK; suitable for subprocess isolation and persistence tests.
"""
from __future__ import annotations

import os

from scantopath.acquisition.raw_rgbd import RawRgbdCapture
from scantopath.modules.capture.application.live_stream import LiveCameraError, LiveNativeFrame
from tests.support.raw_fixture import raw


class PipelineFakeCamera:
    def __init__(self, mode: str = "normal") -> None:
        self.mode = mode
        self.index = 0
        self.opened = False

    def open(self) -> None:
        self.opened = True

    def read_next(self, *, per_attempt_timeout_ms: int, max_attempts: int):
        assert self.opened and max_attempts == 1
        self.index += 1
        return LiveNativeFrame(
            color_mjpeg=b"preview-not-RAW", depth_y16_le=b"\x02\x00" * 6,
            color_width=4, color_height=3, depth_width=3, depth_height=2,
            color_frame_index=self.index, depth_frame_index=self.index,
            color_timestamp_us=100_000 + self.index * 1000,
            depth_timestamp_us=101_000 + self.index * 1000,
            depth_scale_m_per_unit=0.001,
            device_name="FAKE_NOT_A_SENSOR", firmware="fake",
        )

    def capture_next_raw(self, *, session_id: str, specimen_id: str) -> RawRgbdCapture:
        assert self.opened
        if self.mode == "crash":
            os._exit(97)
        if self.mode == "timeout":
            raise TimeoutError("synthetic timeout")
        if self.mode == "bad":
            return object()
        self.index += 1
        packet = raw(
            session=session_id,
            specimen=specimen_id,
            capture_id=f"pipeline-fake-{self.index:04d}",
        )
        metadata = packet.metadata.model_copy(update={
            "color": packet.metadata.color.model_copy(update={
                "frame_index": self.index,
                "timestamp_us": 100_000 + self.index * 1000,
            }),
            "depth": packet.metadata.depth.model_copy(update={
                "frame_index": self.index,
                "timestamp_us": 101_000 + self.index * 1000,
            }),
        })
        return RawRgbdCapture(metadata, packet.color_mjpeg, packet.depth_y16_le)

    def close(self) -> None:
        self.opened = False


def good_pipeline_camera():
    return PipelineFakeCamera("normal")


def crashing_pipeline_camera():
    return PipelineFakeCamera("crash")


def timing_out_pipeline_camera():
    return PipelineFakeCamera("timeout")
