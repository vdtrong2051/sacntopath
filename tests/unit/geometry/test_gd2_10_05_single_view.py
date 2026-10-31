
"""GD2-10.05: synthetic XYZRGB, provenance and fail-closed tests."""
from hashlib import sha256

import numpy as np
import pytest

from scantopath.modules.geometry.application.service import (
    GeometryService,
    SingleViewError,
)
from scantopath.modules.geometry.application.validity import DepthRangePolicy
from scantopath.modules.geometry.application.color_projection import (
    ColorProjectionError,
)
from tests.support.raw_fixture import raw


def sample():
    packet = raw()
    meta = packet.metadata
    rgb = np.zeros(
        (meta.color.height, meta.color.width, 3),
        dtype=np.uint8,
    )

    for v in range(meta.color.height):
        for u in range(meta.color.width):
            rgb[v, u] = (25 * u, 30 * v, 200)

    return packet, rgb


def process(packet, rgb, **options):
    return GeometryService.process(
        depth_u16=packet.depth_u16_copy(),
        color_rgb=rgb,
        metadata=packet.metadata,
        capture_id=packet.metadata.capture_id,
        **options,
    )


def test_known_rgb_pixels_from_independent_color_grid():
    packet, rgb = sample()
    result = process(packet, rgb)

    assert result.points_xyz_m.shape == (5, 3)
    assert result.depth_source_uv.tolist() == [
        [1, 0], [2, 0], [0, 1], [1, 1], [2, 1],
    ]
    assert result.colored_point_indices.tolist() == [
        0, 1, 2, 3, 4,
    ]
    assert result.color_pixel_uv.tolist() == [
        [2, 1], [3, 1], [1, 2], [2, 2], [3, 2],
    ]
    assert result.colors_rgb.tolist() == [
        [50, 30, 200],
        [75, 30, 200],
        [25, 60, 200],
        [50, 60, 200],
        [75, 60, 200],
    ]

    assert result.color_status == "XYZRGB_ALL_COLORED"
    assert result.frame == "depth_optical"
    assert result.units == "m"
    assert result.metric_validated is False


def test_quality_counts_and_unverified_timestamps():
    packet, rgb = sample()
    result = process(packet, rgb)
    q = result.quality_stats

    assert (
        q.total_depth_pixels,
        q.valid_xyz_points,
        q.rejected_depth_pixels,
    ) == (6, 5, 1)

    assert (q.colored_points, q.uncolored_xyz_points) == (5, 0)
    assert q.timestamp_delta_us == 1000
    assert q.timestamp_domain == "sdk_reported_unverified"
    assert result.source_integrity_status == "NOT_VERIFIED_BY_GEOMETRY"


def test_partial_color_does_not_invent_rgb():
    packet, rgb = sample()
    meta = packet.metadata

    moved = meta.depth_to_color.model_copy(
        update={"translation_mm": (225.0, 0.0, 0.0)}
    )
    packet = type(packet)(
        metadata=meta.model_copy(
            update={"depth_to_color": moved}
        ),
        color_mjpeg=packet.color_mjpeg,
        depth_y16_le=packet.depth_y16_le,
    )

    result = process(packet, rgb)

    n = result.points_xyz_m.shape[0]
    m = result.colors_rgb.shape[0]

    assert n == 5
    assert 0 < m < n
    assert result.color_status == "XYZRGB_PARTIAL_COLOR"
    assert result.colors_rgb.shape == (m, 3)
    assert result.quality_stats.uncolored_xyz_points == n - m
    np.testing.assert_array_equal(
        result.colored_point_indices,
        np.flatnonzero(result.color_valid),
    )


def test_no_color_does_not_claim_xyzrgb_pass():
    packet, rgb = sample()
    meta = packet.metadata

    moved = meta.depth_to_color.model_copy(
        update={"translation_mm": (2000.0, 0.0, 0.0)}
    )
    packet = type(packet)(
        metadata=meta.model_copy(
            update={"depth_to_color": moved}
        ),
        color_mjpeg=packet.color_mjpeg,
        depth_y16_le=packet.depth_y16_le,
    )

    result = process(packet, rgb)

    assert result.points_xyz_m.shape == (5, 3)
    assert result.colors_rgb.shape == (0, 3)
    assert result.colored_point_indices.size == 0
    assert result.color_status == "XYZ_ONLY_NO_VALID_COLOR"


def test_input_unchanged_and_output_read_only():
    packet, rgb = sample()
    depth = packet.depth_u16_copy()

    before_depth = depth.copy()
    before_rgb = rgb.copy()

    result = GeometryService.process(
        depth_u16=depth,
        color_rgb=rgb,
        metadata=packet.metadata,
        capture_id=packet.metadata.capture_id,
    )

    np.testing.assert_array_equal(depth, before_depth)
    np.testing.assert_array_equal(rgb, before_rgb)

    assert not np.shares_memory(result.colors_rgb, rgb)

    assert all(
        not array.flags.writeable
        for array in (
            result.points_xyz_m,
            result.depth_source_uv,
            result.depth_valid,
            result.colors_rgb,
            result.color_valid,
            result.color_pixel_uv,
            result.colored_point_indices,
        )
    )


def test_depth_range_filters_xyz_and_color_together():
    packet, rgb = sample()

    result = process(
        packet,
        rgb,
        depth_policy=DepthRangePolicy(0.05, 0.95),
    )

    assert result.points_xyz_m.shape == (3, 3)
    assert result.color_valid.shape == (3,)
    assert result.colors_rgb.shape[0] <= 3
    assert result.depth_source_uv.tolist() == [
        [2, 0], [0, 1], [1, 1],
    ]


def test_source_hashes_are_not_claimed_verified():
    packet, rgb = sample()

    hashes = {
        "color.mjpg": sha256(packet.color_mjpeg).hexdigest(),
        "depth.y16": sha256(packet.depth_y16_le).hexdigest(),
    }

    result = process(
        packet,
        rgb,
        source_raw_sha256=hashes,
    )

    assert dict(result.source_raw_sha256) == hashes
    assert result.source_integrity_status == "NOT_VERIFIED_BY_GEOMETRY"
    assert len(result.calibration_fingerprint) == 64
    assert (
        process(packet, rgb).calibration_fingerprint
        == result.calibration_fingerprint
    )


@pytest.mark.parametrize("bad", [
    {"depth.y16": "0" * 64},
    {"color.mjpg": "0" * 64, "depth.y16": "ABC"},
])
def test_bad_source_hashes_rejected(bad):
    packet, rgb = sample()

    with pytest.raises(SingleViewError) as err:
        process(packet, rgb, source_raw_sha256=bad)

    assert err.value.code == "SOURCE_HASH_INVALID"


@pytest.mark.parametrize("bad_rgb", [
    np.zeros((2, 3, 3), dtype=np.uint8),
    np.zeros((4, 5, 3), dtype=np.float32),
    np.zeros((4, 5), dtype=np.uint8),
])
def test_invalid_rgb_array_rejected(bad_rgb):
    packet, _ = sample()

    with pytest.raises(SingleViewError) as err:
        process(packet, bad_rgb)

    assert err.value.code == "RGB_ARRAY_INVALID"


def test_noncontiguous_color_array_rejected():
    packet, rgb = sample()
    bad = np.pad(
        rgb,
        ((0, 0), (0, 1), (0, 0)),
    )[:, :5]

    assert not bad.flags.c_contiguous

    with pytest.raises(SingleViewError) as err:
        process(packet, bad)

    assert err.value.code == "RGB_ARRAY_INVALID"


def test_capture_mismatch_rejected():
    packet, rgb = sample()

    with pytest.raises(SingleViewError) as err:
        GeometryService.process(
            depth_u16=packet.depth_u16_copy(),
            color_rgb=rgb,
            metadata=packet.metadata,
            capture_id="other",
        )

    assert err.value.code == "CAPTURE_CONTEXT_MISMATCH"


def test_unsupported_color_distortion_rejected():
    packet, rgb = sample()
    meta = packet.metadata

    distortion = meta.color_distortion.model_copy(
        update={"sdk_model": 4}
    )
    packet = type(packet)(
        metadata=meta.model_copy(
            update={"color_distortion": distortion}
        ),
        color_mjpeg=packet.color_mjpeg,
        depth_y16_le=packet.depth_y16_le,
    )

    with pytest.raises(ColorProjectionError) as err:
        process(packet, rgb)

    assert err.value.code == "DISTORTION_MODEL_UNSUPPORTED"


def test_empty_depth_rejected():
    packet, rgb = sample()

    with pytest.raises(ValueError) as err:
        GeometryService.process(
            depth_u16=np.zeros_like(packet.depth_u16_copy()),
            color_rgb=rgb,
            metadata=packet.metadata,
            capture_id=packet.metadata.capture_id,
        )

    assert getattr(err.value, "code", None) == "EMPTY_VALID_DEPTH"
