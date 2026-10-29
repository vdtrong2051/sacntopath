
"""GD2-09.05: lazy Gemini 2 adapter; owns one native source in one thread.

No SDK/module import or camera open is performed by importing this file.
"""
from __future__ import annotations

from collections.abc import Callable
from threading import get_ident
from typing import Any

from scantopath.modules.capture.application.live_stream import (
    LiveCameraError,
    LiveNativeFrame,
)


class Gemini2NativeCameraAdapter:
    def __init__(
        self,
        native_loader: Callable[[], Any] | None = None,
    ) -> None:
        self._native_loader = native_loader
        self._source: Any = None
        self._owner: int | None = None

    def _assert_owner(self) -> None:
        if (
            self._owner is not None
            and self._owner != get_ident()
        ):
            raise LiveCameraError("WRONG_THREAD")

    def open(self) -> None:
        if self._source is not None:
            raise LiveCameraError("ALREADY_OPEN")

        loader = self._native_loader

        if loader is None:
            from scantopath.acquisition.native import load_native
            loader = load_native

        source = None

        try:
            native = loader()
            source = native.OrbbecCameraSource()
            source.open()

        except Exception as exc:
            if source is not None:
                try:
                    source.close()
                except Exception:
                    pass

            raise LiveCameraError("OPEN_FAILED") from exc

        self._source = source
        self._owner = get_ident()

    def read_next(
        self,
        *,
        per_attempt_timeout_ms: int,
        max_attempts: int,
    ) -> LiveNativeFrame:
        self._assert_owner()

        if self._source is None:
            raise LiveCameraError("NOT_OPEN")

        if (
            type(per_attempt_timeout_ms) is not int
            or type(max_attempts) is not int
            or not 1 <= per_attempt_timeout_ms <= 1000
            or not 1 <= max_attempts <= 3
        ):
            raise ValueError("read timeout/attempts out of bounds")

        try:
            packet = self._source.read_next(
                per_attempt_timeout_ms=per_attempt_timeout_ms,
                max_attempts=max_attempts,
            )

        except RuntimeError as exc:
            # Matches the existing native C++ bounded-read timeout.
            if (
                "No complete RGB-D frameset received within bounded timeout"
                in str(exc)
            ):
                raise TimeoutError(
                    "bounded camera read timeout"
                ) from exc

            raise LiveCameraError("READ_FAILED") from exc

        except Exception as exc:
            raise LiveCameraError("READ_FAILED") from exc

        try:
            if (
                packet.validate() is not True
                or packet.align_disabled is not True
            ):
                raise ValueError("invalid native capture")

            if (
                packet.color.encoding.name != "MJPEG"
                or packet.depth.encoding.name != "Y16"
            ):
                raise ValueError("unexpected stream encoding")

            if packet.device.name != "Orbbec Gemini 2":
                raise ValueError("unexpected device")

            # pybind11 .bytes returns Python-owned copies.
            # No SDK frame pointer escapes this boundary.
            return LiveNativeFrame(
                color_mjpeg=packet.color.bytes,
                depth_y16_le=packet.depth.bytes,
                color_width=int(packet.color.width),
                color_height=int(packet.color.height),
                depth_width=int(packet.depth.width),
                depth_height=int(packet.depth.height),
                color_frame_index=int(
                    packet.color.frame_index
                ),
                depth_frame_index=int(
                    packet.depth.frame_index
                ),
                color_timestamp_us=int(
                    packet.color.timestamp_us
                ),
                depth_timestamp_us=int(
                    packet.depth.timestamp_us
                ),
                depth_scale_m_per_unit=float(
                    packet.depth_scale_m_per_unit
                ),
                device_name=str(packet.device.name),
                firmware=str(packet.device.firmware),
            )

        except Exception as exc:
            raise LiveCameraError(
                "INVALID_NATIVE_FRAME"
            ) from exc

    def close(self) -> None:
        self._assert_owner()

        source = self._source
        self._source = None
        self._owner = None

        if source is not None:
            try:
                source.close()
            except Exception as exc:
                raise LiveCameraError(
                    "CLOSE_FAILED"
                ) from exc
