"""09.03: real JPEG fixture + Y16 byte-order tests; no camera/UI."""
from __future__ import annotations

from dataclasses import FrozenInstanceError
from io import BytesIO
import hashlib
import subprocess
import sys

import numpy as np
from PIL import Image
import pytest

from scantopath.acquisition.raw_rgbd import RawRgbdCapture
from scantopath.modules.capture.application.decoding import (
    RgbdDecodeError,
    RgbdDecoder,
)
from scantopath.modules.capture.infrastructure.jpeg_codec import (
    PillowMjpegDecoder,
)
from tests.support.raw_fixture import raw


def jpeg_bytes(width=32, height=16, *, mode="RGB") -> bytes:
    if mode == "L":
        image = Image.new("L", (width, height), 120)
    else:
        pixels = np.zeros((height, width, 3), dtype=np.uint8)
        pixels[:, :width // 2] = (250, 2, 0)
        pixels[:, width // 2:] = (0, 1, 250)
        image = Image.fromarray(pixels)

    out = BytesIO()

    image.save(
        out,
        format="JPEG",
        quality=100,
        subsampling=0,
    )
    return out.getvalue()


def valid_packet(*, jpeg=None, width=32, height=16) -> RawRgbdCapture:
    base = raw(session="t1", specimen="s1", capture_id="c1")

    color = jpeg_bytes() if jpeg is None else jpeg

    meta = base.metadata.model_copy(update={
        "color": base.metadata.color.model_copy(update={
            "width": width,
            "height": height,
            "payload_size_bytes": len(color),
        }),
        "color_intrinsics": base.metadata.color_intrinsics.model_copy(update={
            "width": width,
            "height": height,
        }),
    })

    return RawRgbdCapture(
        meta,
        color,
        base.depth_y16_le,
    )


def decoder():
    return RgbdDecoder(PillowMjpegDecoder())


def test_rgb_shape_dtype_and_channel_order():
    frame = decoder().decode(valid_packet())

    assert frame.color_rgb.shape == (16, 32, 3)
    assert frame.color_rgb.dtype == np.uint8

    # RGB, not BGR.
    assert frame.color_rgb[8, 3, 0] > 215
    assert frame.color_rgb[8, 3, 2] < 35

    assert frame.color_rgb[8, 29, 2] > 215
    assert frame.color_rgb[8, 29, 0] < 35


def test_depth_explicit_little_endian_and_extreme_values():
    packet = valid_packet()

    values = np.array(
        [[0, 1, 65535], [256, 1024, 4096]],
        dtype="<u2",
    )

    changed = RawRgbdCapture(
        packet.metadata,
        packet.color_mjpeg,
        values.tobytes(),
    )

    frame = decoder().decode(changed)

    assert frame.depth_u16.shape == (2, 3)
    assert frame.depth_u16.dtype == np.uint16

    np.testing.assert_array_equal(frame.depth_u16, values)

    # Cannot accidentally read as big-endian.
    assert frame.depth_u16[1, 0] == 256


def test_separate_color_and_depth_grids_and_metadata_untouched():
    packet = valid_packet()

    before = packet.metadata.model_dump(mode="json")

    frame = decoder().decode(packet)

    assert frame.color_rgb.shape[:2] == (16, 32)
    assert frame.depth_u16.shape == (2, 3)

    assert frame.metadata is packet.metadata
    assert frame.metadata.model_dump(mode="json") == before

    assert frame.metadata.alignment_mode == "disabled"
    assert frame.metadata.camera_pose is None
    assert frame.metadata.depth_scale_m_per_unit == 0.001


def test_no_raw_mutation_and_decoded_arrays_read_only():
    packet = valid_packet()

    before = (
        hashlib.sha256(packet.color_mjpeg).hexdigest(),
        hashlib.sha256(packet.depth_y16_le).hexdigest(),
    )

    frame = decoder().decode(packet)

    assert not frame.color_rgb.flags.writeable
    assert not frame.depth_u16.flags.writeable

    with pytest.raises(ValueError):
        frame.depth_u16[0, 0] = 12

    with pytest.raises(FrozenInstanceError):
        frame.metadata = None

    assert before == (
        hashlib.sha256(packet.color_mjpeg).hexdigest(),
        hashlib.sha256(packet.depth_y16_le).hexdigest(),
    )


def test_invalid_jpeg_marker_only_is_rejected():
    packet = valid_packet(
        jpeg=b"\xff\xd8not-a-real-jpeg\xff\xd9"
    )

    with pytest.raises(RgbdDecodeError) as error:
        decoder().decode(packet)

    assert error.value.code == "INVALID_MJPEG"


def test_truncated_jpeg_is_rejected():
    packet = valid_packet(
        jpeg=jpeg_bytes()[:-12]
    )

    with pytest.raises(RgbdDecodeError) as error:
        decoder().decode(packet)

    assert error.value.code == "INVALID_MJPEG"


def test_actual_jpeg_size_not_matching_metadata_is_rejected():
    # Actual JPEG is 32x16, metadata claims 31x16.
    packet = valid_packet(width=31, height=16)

    with pytest.raises(RgbdDecodeError) as error:
        decoder().decode(packet)

    assert error.value.code == "JPEG_DIMENSION_MISMATCH"


def test_grayscale_jpeg_is_rejected_not_silently_colorized():
    packet = valid_packet(
        jpeg=jpeg_bytes(mode="L")
    )

    with pytest.raises(RgbdDecodeError) as error:
        decoder().decode(packet)

    assert error.value.code == "UNSUPPORTED_JPEG_MODE"


def test_decoder_does_not_accept_wrong_type():
    with pytest.raises(TypeError):
        decoder().decode(None)


def test_codec_invalid_array_rejected_at_application_boundary():
    class WrongCodec:
        def decode(self, payload, *, width, height):
            return np.zeros(
                (height, width, 3),
                dtype=np.uint16,
            )

    with pytest.raises(RgbdDecodeError) as error:
        RgbdDecoder(WrongCodec()).decode(valid_packet())

    assert error.value.code == "INVALID_RGB_ARRAY"


def test_jpeg_pixel_limit_before_decompression():
    with pytest.raises(RgbdDecodeError) as error:
        PillowMjpegDecoder().decode(
            b"\xff\xd8",
            width=100_000,
            height=100_000,
        )

    assert error.value.code == "JPEG_LIMIT_EXCEEDED"


def test_decoder_import_does_not_initialize_ui_sdk_or_pillow():
    code = (
        "import sys; before = set(sys.modules); "
        "from scantopath.modules.capture.application.decoding "
        "import RgbdDecoder; "
        "from scantopath.modules.capture.infrastructure.jpeg_codec "
        "import PillowMjpegDecoder; "
        "added = set(sys.modules) - before; "
        "assert 'PySide6' not in added; "
        "assert 'PIL' not in added; "
        "assert 'scantopath.acquisition.native' not in added; "
        "assert 'scantopath.metadata.store' not in added"
    )

    proc = subprocess.run(
        [sys.executable, "-c", code],
        capture_output=True,
        text=True,
        check=False,
    )

    assert proc.returncode == 0, proc.stderr


def test_gemini2_resolution_profile_keeps_native_grids():
    # Synthetic data matching an observed profile; NOT physical camera evidence.
    packet = valid_packet(
        jpeg=jpeg_bytes(1920, 1080),
        width=1920,
        height=1080,
    )

    depth_bytes = np.full(
        (800, 1280),
        1250,
        dtype="<u2",
    ).tobytes()

    meta = packet.metadata.model_copy(update={
        "depth": packet.metadata.depth.model_copy(update={
            "width": 1280,
            "height": 800,
            "payload_size_bytes": len(depth_bytes),
        }),
        "depth_intrinsics": packet.metadata.depth_intrinsics.model_copy(update={
            "width": 1280,
            "height": 800,
        }),
    })

    frame = decoder().decode(
        RawRgbdCapture(
            meta,
            packet.color_mjpeg,
            depth_bytes,
        )
    )

    assert frame.color_rgb.shape == (1080, 1920, 3)
    assert frame.depth_u16.shape == (800, 1280)
    assert frame.depth_u16[400, 640] == 1250