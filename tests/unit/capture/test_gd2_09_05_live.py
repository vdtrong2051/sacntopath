
"""GD2-09.05 application tests: no SDK, Qt or filesystem."""
from __future__ import annotations

from dataclasses import replace

import numpy as np
import pytest

from scantopath.modules.capture.application.live_stream import (
    LiveCameraError,
    LiveCaptureService,
    LiveNativeFrame,
    LiveRgbdFrame,
)


def packet() -> LiveNativeFrame:
    return LiveNativeFrame(
        color_mjpeg=b"jpeg-bytes",
        depth_y16_le=np.array(
            [
                [0, 12, 300],
                [800, 1500, 65535],
            ],
            dtype="<u2",
        ).tobytes(),
        color_width=5,
        color_height=4,
        depth_width=3,
        depth_height=2,
        color_frame_index=21,
        depth_frame_index=22,
        color_timestamp_us=100000,
        depth_timestamp_us=103308,
        depth_scale_m_per_unit=0.001,
        device_name="Orbbec Gemini 2",
        firmware="test-only",
    )


class FakeCamera:
    def __init__(self, result=None):
        self.events = []
        self.result = result or packet()

    def open(self):
        self.events.append("open")

    def read_next(
        self,
        *,
        per_attempt_timeout_ms,
        max_attempts,
    ):
        self.events.append(
            ("read", per_attempt_timeout_ms, max_attempts)
        )
        return self.result

    def close(self):
        self.events.append("close")


class FakeDecoder:
    def decode(self, payload, *, width, height):
        assert payload == b"jpeg-bytes"
        return np.full(
            (height, width, 3),
            9,
            dtype=np.uint8,
        )


def test_live_frame_has_no_capture_identity_or_pose():
    src = packet()

    assert not hasattr(src, "capture_id")
    assert not hasattr(src, "camera_pose")
    assert src.depth_scale_m_per_unit == 0.001


def test_service_does_not_open_implicitly():
    camera = FakeCamera()
    service = LiveCaptureService(camera, FakeDecoder())

    assert camera.events == []

    with pytest.raises(LiveCameraError) as exc:
        service.read_next()

    assert exc.value.code == "NOT_OPEN"
    assert camera.events == []


def test_frame_decode_grids_and_owned_readonly_copies():
    camera = FakeCamera()
    service = LiveCaptureService(camera, FakeDecoder())

    service.open()
    frame = service.read_next(
        per_attempt_timeout_ms=300
    )
    service.close()

    assert camera.events == [
        "open",
        ("read", 300, 1),
        "close",
    ]

    assert frame.color_rgb.shape == (4, 5, 3)
    assert frame.depth_u16.shape == (2, 3)

    assert frame.color_rgb.dtype == np.uint8
    assert frame.depth_u16.dtype == np.uint16

    assert frame.color_rgb.flags.owndata
    assert frame.depth_u16.flags.owndata

    assert not frame.color_rgb.flags.writeable
    assert not frame.depth_u16.flags.writeable

    assert frame.depth_u16.tolist() == [
        [0, 12, 300],
        [800, 1500, 65535],
    ]


def test_live_frame_clones_supplied_arrays():
    source = packet()

    color = np.ones(
        (4, 5, 3),
        dtype=np.uint8,
    )

    depth = np.ones(
        (2, 3),
        dtype=np.uint16,
    )

    frame = LiveRgbdFrame(source, color, depth)

    color[0, 0, 0] = 100
    depth[0, 0] = 99

    assert frame.color_rgb[0, 0, 0] == 1
    assert frame.depth_u16[0, 0] == 1


@pytest.mark.parametrize(
    "field,value",
    [
        ("color_width", 0),
        ("depth_height", -1),
        ("color_mjpeg", bytearray(b"jpeg-bytes")),
        ("depth_y16_le", b"bad"),
        ("depth_scale_m_per_unit", float("nan")),
        ("color_timestamp_us", -1),
    ],
)
def test_invalid_live_native_fields_rejected(field, value):
    with pytest.raises(ValueError):
        replace(packet(), **{field: value})


def test_service_rejects_non_contract_packet():
    camera = FakeCamera(result=object())
    service = LiveCaptureService(camera, FakeDecoder())

    service.open()

    with pytest.raises(LiveCameraError) as exc:
        service.read_next()

    service.close()

    assert exc.value.code == "INVALID_NATIVE_FRAME"


def test_service_rejects_second_open():
    camera = FakeCamera()
    service = LiveCaptureService(camera, FakeDecoder())

    service.open()

    with pytest.raises(LiveCameraError) as exc:
        service.open()

    service.close()

    assert exc.value.code == "ALREADY_OPEN"
    assert camera.events.count("open") == 1
