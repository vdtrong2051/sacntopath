
"""GD2-09.05 native adapter tests using an injected fake pybind11 module."""
from __future__ import annotations

from types import SimpleNamespace as NS

import numpy as np
import pytest

from scantopath.modules.capture.application.live_stream import (
    LiveCameraError,
)
from scantopath.modules.capture.infrastructure.native_camera import (
    Gemini2NativeCameraAdapter,
)


def native_packet():
    depth = np.array(
        [[0, 3, 18], [42, 256, 65535]],
        dtype="<u2",
    ).tobytes()

    return NS(
        validate=lambda: True,
        align_disabled=True,
        device=NS(
            name="Orbbec Gemini 2",
            firmware="mock",
        ),
        color=NS(
            encoding=NS(name="MJPEG"),
            width=5,
            height=4,
            frame_index=1,
            timestamp_us=100000,
            bytes=b"jpeg",
        ),
        depth=NS(
            encoding=NS(name="Y16"),
            width=3,
            height=2,
            frame_index=2,
            timestamp_us=101000,
            bytes=depth,
        ),
        depth_scale_m_per_unit=0.001,
    )


class FakeNativeSource:
    def __init__(
        self,
        *,
        packet=None,
        open_error=None,
        read_error=None,
    ):
        self.events = []
        self.packet = (
            packet if packet is not None
            else native_packet()
        )
        self.open_error = open_error
        self.read_error = read_error

    def open(self):
        self.events.append("open")

        if self.open_error is not None:
            raise self.open_error

    def read_next(self, **kw):
        self.events.append(("read", kw))

        if self.read_error is not None:
            raise self.read_error

        return self.packet

    def close(self):
        self.events.append("close")


def adapter(source):
    return Gemini2NativeCameraAdapter(
        native_loader=lambda: NS(
            OrbbecCameraSource=lambda: source
        )
    )


def test_lazy_adapter_no_open_until_requested():
    source = FakeNativeSource()
    camera = adapter(source)

    assert source.events == []

    camera.close()

    assert source.events == []


def test_native_packet_copied_and_validated():
    source = FakeNativeSource()
    camera = adapter(source)

    camera.open()

    frame = camera.read_next(
        per_attempt_timeout_ms=300,
        max_attempts=1,
    )

    camera.close()

    assert frame.color_mjpeg == b"jpeg"

    assert frame.depth_width == 3
    assert frame.depth_height == 2

    assert frame.color_width == 5
    assert frame.color_height == 4

    assert frame.depth_scale_m_per_unit == 0.001

    assert frame.depth_y16_le == np.array(
        [[0, 3, 18], [42, 256, 65535]],
        dtype="<u2",
    ).tobytes()

    assert source.events[0] == "open"
    assert source.events[2] == "close"


def test_open_failure_disposes_native_source():
    source = FakeNativeSource(
        open_error=RuntimeError("device absent")
    )
    camera = adapter(source)

    with pytest.raises(LiveCameraError) as exc:
        camera.open()

    assert exc.value.code == "OPEN_FAILED"
    assert source.events == ["open", "close"]


def test_bounded_native_timeout_recognized():
    source = FakeNativeSource(
        read_error=RuntimeError(
            "No complete RGB-D frameset received within bounded timeout"
        )
    )

    camera = adapter(source)
    camera.open()

    with pytest.raises(TimeoutError):
        camera.read_next(
            per_attempt_timeout_ms=300,
            max_attempts=1,
        )

    camera.close()


def test_invalid_packet_rejected():
    bad = native_packet()
    bad.depth.bytes = b"bad-size"

    source = FakeNativeSource(packet=bad)
    camera = adapter(source)

    camera.open()

    with pytest.raises(LiveCameraError) as exc:
        camera.read_next(
            per_attempt_timeout_ms=300,
            max_attempts=1,
        )

    camera.close()

    assert exc.value.code == "INVALID_NATIVE_FRAME"


def test_double_open_and_timeout_bounds():
    source = FakeNativeSource()
    camera = adapter(source)

    camera.open()

    with pytest.raises(LiveCameraError) as exc:
        camera.open()

    assert exc.value.code == "ALREADY_OPEN"

    with pytest.raises(ValueError):
        camera.read_next(
            per_attempt_timeout_ms=30000,
            max_attempts=1,
        )

    camera.close()

    assert source.events.count("open") == 1
    assert source.events.count("close") == 1
