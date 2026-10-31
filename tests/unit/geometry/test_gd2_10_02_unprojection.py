
"""GD2-10.02: independent pinhole numerical checks, synthetic only."""
from dataclasses import replace

import numpy as np
import pytest

from scantopath.modules.geometry.application.calibration import (
    CalibrationContract,
)
from scantopath.modules.geometry.application.unprojection import (
    DepthProjectionError,
    unproject_depth,
)
from tests.support.raw_fixture import raw


def fixture():
    packet = raw()
    depth = packet.depth_u16_copy()
    calibration = CalibrationContract.from_metadata(packet.metadata)
    return depth, calibration


def test_known_pixel_xyz_in_metres_and_native_depth_grid():
    depth, c = fixture()
    result = unproject_depth(
        depth, calibration=c, capture_id=c.capture_id
    )

    assert result.xyz_m.shape == (2, 3, 3)
    assert result.xyz_m.dtype == np.float64
    assert result.frame == "depth_optical"
    assert result.units == "m"

    np.testing.assert_allclose(
        result.xyz_m[1, 1],
        (0., 0., 0.9),
        atol=1e-14,
    )
    np.testing.assert_allclose(
        result.xyz_m[0, 2],
        (0.033, -0.033, 0.099),
        atol=1e-14,
    )
    np.testing.assert_allclose(
        result.xyz_m[1, 0],
        (-1 / 30, 0., 0.1),
        atol=1e-14,
    )


def test_depth_zero_is_missing_not_origin_and_mask_keeps_pixel_index():
    depth, c = fixture()
    result = unproject_depth(
        depth, calibration=c, capture_id=c.capture_id
    )

    assert np.isnan(result.xyz_m[0, 0]).all()
    assert result.depth_m[0, 0] == 0
    assert not result.depth_valid_mask[0, 0]
    assert result.depth_valid_mask[0, 2]
    assert int(result.depth_valid_mask.sum()) == 5
    assert np.isfinite(
        result.xyz_m[result.depth_valid_mask]
    ).all()


def test_does_not_change_source_depth_and_results_are_read_only():
    depth, c = fixture()
    before = depth.copy()

    result = unproject_depth(
        depth, calibration=c, capture_id=c.capture_id
    )

    np.testing.assert_array_equal(depth, before)
    assert not np.shares_memory(result.xyz_m, depth)
    assert all(
        not x.flags.writeable
        for x in (
            result.xyz_m,
            result.depth_m,
            result.depth_valid_mask,
        )
    )


def test_capture_id_mismatch_is_rejected():
    depth, c = fixture()

    with pytest.raises(DepthProjectionError) as e:
        unproject_depth(
            depth,
            calibration=c,
            capture_id="different-capture",
        )

    assert e.value.code == "CAPTURE_CONTEXT_MISMATCH"


@pytest.mark.parametrize("depth", [
    np.zeros((2, 2), dtype=np.uint16),
    np.ones((2, 3), dtype=np.float32),
    np.ones((2, 3, 1), dtype=np.uint16),
    np.ones((2, 3), dtype=np.int16),
])
def test_rejects_wrong_shape_or_encoding(depth):
    _, c = fixture()

    with pytest.raises(DepthProjectionError) as e:
        unproject_depth(
            depth,
            calibration=c,
            capture_id=c.capture_id,
        )

    assert e.value.code == "DEPTH_ARRAY_INVALID"


def test_rejects_noncontiguous_depth():
    depth, c = fixture()
    depth_view = np.pad(
        depth, ((0, 0), (0, 1))
    )[:, :3]

    assert not depth_view.flags.c_contiguous

    with pytest.raises(DepthProjectionError) as e:
        unproject_depth(
            depth_view,
            calibration=c,
            capture_id=c.capture_id,
        )

    assert e.value.code == "DEPTH_ARRAY_INVALID"


@pytest.mark.parametrize("model", [1, 2, 3, 4, 5])
def test_refuses_unverified_depth_distortion_instead_of_using_pinhole(model):
    depth, c = fixture()

    c = replace(
        c,
        depth_distortion=replace(
            c.depth_distortion,
            sdk_model=model,
        ),
    )

    with pytest.raises(DepthProjectionError) as e:
        unproject_depth(
            depth,
            calibration=c,
            capture_id=c.capture_id,
        )

    assert e.value.code == "DISTORTION_MODEL_UNSUPPORTED"


def test_nonzero_coefficients_in_none_model_are_rejected():
    depth, c = fixture()

    c = replace(
        c,
        depth_distortion=replace(
            c.depth_distortion,
            k1_k6_p1_p2=(0.1,) + (0.,) * 7,
        ),
    )

    with pytest.raises(DepthProjectionError) as e:
        unproject_depth(
            depth,
            calibration=c,
            capture_id=c.capture_id,
        )

    assert e.value.code == "DISTORTION_COEFFICIENTS_INVALID"


def test_depth_scale_is_per_capture():
    depth, c = fixture()
    doubled = replace(
        c,
        depth_scale_m_per_unit=.002,
    )

    a = unproject_depth(
        depth, calibration=c, capture_id=c.capture_id
    )
    b = unproject_depth(
        depth, calibration=doubled, capture_id=c.capture_id
    )

    np.testing.assert_allclose(
        b.xyz_m[a.depth_valid_mask],
        2 * a.xyz_m[a.depth_valid_mask],
    )


def test_all_missing_depth_returns_empty_mask_for_10_03_to_handle():
    depth, c = fixture()
    depth[:] = 0

    result = unproject_depth(
        depth, calibration=c, capture_id=c.capture_id
    )

    assert not result.depth_valid_mask.any()
    assert np.isnan(result.xyz_m).all()


def test_nonfinite_xyz_is_rejected():
    depth, c = fixture()

    c = replace(
        c,
        depth_scale_m_per_unit=1e307,
    )

    with pytest.raises(DepthProjectionError) as e:
        unproject_depth(
            depth,
            calibration=c,
            capture_id=c.capture_id,
        )

    assert e.value.code == "NONFINITE_PROJECTION"
