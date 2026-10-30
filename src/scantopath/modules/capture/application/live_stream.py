
"""GD2-09.05: hardware-independent live RGB-D contract and decoding.

A live frame is NOT a registered RAW capture: no fabricated Capture ID or pose.
"""
from __future__ import annotations

from dataclasses import dataclass
from math import isfinite

import numpy as np

from .ports import NativeCameraPort
from scantopath.acquisition.raw_rgbd import RawRgbdCapture
from .decoding import MjpegDecoderPort, RgbdDecodeError


class LiveCameraError(RuntimeError):
    def __init__(self, code: str) -> None:
        self.code = code
        super().__init__(code)


@dataclass(frozen=True, slots=True)
class LiveNativeFrame:
    """Owned raw stream bytes + source facts; never persisted by 09.05."""

    color_mjpeg: bytes
    depth_y16_le: bytes
    color_width: int
    color_height: int
    depth_width: int
    depth_height: int
    color_frame_index: int
    depth_frame_index: int
    color_timestamp_us: int
    depth_timestamp_us: int
    depth_scale_m_per_unit: float
    device_name: str
    firmware: str

    def __post_init__(self) -> None:
        for name in (
            "color_width",
            "color_height",
            "depth_width",
            "depth_height",
        ):
            v = getattr(self, name)
            if type(v) is not int or v <= 0:
                raise ValueError(f"invalid {name}")

        for name in (
            "color_frame_index",
            "depth_frame_index",
            "color_timestamp_us",
            "depth_timestamp_us",
        ):
            v = getattr(self, name)
            if type(v) is not int or v < 0:
                raise ValueError(f"invalid {name}")

        if (
            self.color_width * self.color_height > 32_000_000
            or self.depth_width * self.depth_height > 32_000_000
        ):
            raise ValueError("frame pixel limit exceeded")

        if (
            type(self.color_mjpeg) is not bytes
            or not 0 < len(self.color_mjpeg) <= 64 * 1024 * 1024
        ):
            raise ValueError("invalid MJPEG bytes")

        if (
            type(self.depth_y16_le) is not bytes
            or len(self.depth_y16_le)
            != self.depth_width * self.depth_height * 2
        ):
            raise ValueError("invalid Y16 byte count")

        if (
            not isinstance(self.device_name, str)
            or not self.device_name.strip()
        ):
            raise ValueError("device_name required")

        if not isinstance(self.firmware, str):
            raise ValueError("invalid firmware")

        if (
            isinstance(self.depth_scale_m_per_unit, bool)
            or not isinstance(
                self.depth_scale_m_per_unit, (float, int)
            )
            or not isfinite(self.depth_scale_m_per_unit)
            or self.depth_scale_m_per_unit <= 0
        ):
            raise ValueError("invalid depth scale")


@dataclass(frozen=True, slots=True)
class LiveRgbdFrame:
    """Independent, read-only NumPy copies in each native stream grid."""

    source: LiveNativeFrame
    color_rgb: np.ndarray
    depth_u16: np.ndarray

    def __post_init__(self) -> None:
        m = self.source

        if not isinstance(m, LiveNativeFrame):
            raise TypeError("source must be LiveNativeFrame")

        if (
            not isinstance(self.color_rgb, np.ndarray)
            or self.color_rgb.dtype != np.uint8
            or self.color_rgb.shape
            != (m.color_height, m.color_width, 3)
        ):
            raise ValueError("invalid RGB array")

        if (
            not isinstance(self.depth_u16, np.ndarray)
            or self.depth_u16.dtype != np.uint16
            or self.depth_u16.shape
            != (m.depth_height, m.depth_width)
        ):
            raise ValueError("invalid depth array")

        color = np.array(
            self.color_rgb,
            copy=True,
            order="C",
        )
        depth = np.array(
            self.depth_u16,
            copy=True,
            order="C",
        )

        color.setflags(write=False)
        depth.setflags(write=False)

        object.__setattr__(self, "color_rgb", color)
        object.__setattr__(self, "depth_u16", depth)


class LiveCaptureService:
    """One camera owner, no Qt, filesystem, or camera construction."""

    def __init__(
        self,
        camera: NativeCameraPort,
        decoder: MjpegDecoderPort,
    ) -> None:
        self._camera = camera
        self._decoder = decoder
        self._opened = False

    def open(self) -> None:
        if self._opened:
            raise LiveCameraError("ALREADY_OPEN")

        self._camera.open()
        self._opened = True

    def read_next(
        self,
        *,
        per_attempt_timeout_ms: int = 300,
    ) -> LiveRgbdFrame:
        if not self._opened:
            raise LiveCameraError("NOT_OPEN")

        packet = self._camera.read_next(
            per_attempt_timeout_ms=per_attempt_timeout_ms,
            max_attempts=1,
        )

        if not isinstance(packet, LiveNativeFrame):
            raise LiveCameraError("INVALID_NATIVE_FRAME")

        try:
            rgb = self._decoder.decode(
                packet.color_mjpeg,
                width=packet.color_width,
                height=packet.color_height,
            )
        except (
            RgbdDecodeError,
            ValueError,
            TypeError,
            OSError,
        ) as exc:
            raise LiveCameraError("DECODE_FAILED") from exc

        try:
            depth = np.frombuffer(
                packet.depth_y16_le,
                dtype="<u2",
            ).reshape(
                packet.depth_height,
                packet.depth_width,
            )

            return LiveRgbdFrame(packet, rgb, depth)

        except (TypeError, ValueError) as exc:
            raise LiveCameraError(
                "INVALID_NATIVE_FRAME"
            ) from exc

    def capture_keyframe(self, *, session_id: str, specimen_id: str) -> RawRgbdCapture:
        """A fresh RAW frameset, NOT a frame taken from decoded live preview."""
        if not self._opened:
            raise LiveCameraError("NOT_OPEN")
        capture = self._camera.capture_next_raw(
            session_id=session_id, specimen_id=specimen_id
        )
        if not isinstance(capture, RawRgbdCapture):
            raise LiveCameraError("INVALID_KEYFRAME")
        if (capture.metadata.session_id != session_id or
                capture.metadata.specimen_id != specimen_id):
            raise LiveCameraError("INVALID_KEYFRAME")
        return capture

    def close(self) -> None:
        self._opened = False
        self._camera.close()
