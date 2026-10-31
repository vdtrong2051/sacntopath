
"""GD2-10.03: deterministic validity, range and pixel-lineage tests."""
from dataclasses import replace

import numpy as np
import pytest

from scantopath.modules.geometry.application.calibration import (
    CalibrationContract,
)
from scantopath.modules.geometry.application.unprojection import (
    unproject_depth,
)
from scantopath.modules.geometry.application.validity import (
    DepthRangePolicy,
    GeometryValidityError,
    select_valid_geometry,
)
from tests.support.raw_fixture import raw


def _data():
    packet = raw()
    cal = CalibrationContract.from_metadata(packet.metadata)
    depth = packet.depth_u16_copy()
    proj = unproject_depth(
        depth,
        calibration=cal,
        capture_id=cal.capture_id,
    )
    return depth, cal, proj


def test_five_points_row_major_uv_and_metric_coordinates():
    _, cal, proj = _data()
    result = select_valid_geometry(proj, calibration=cal)

    assert result.points_xyz_m.shape == (5, 3)
    assert result.depth_source_uv.tolist() == [
        [1, 0], [2, 0], [0, 1], [1, 1], [2, 1],
    ]
    assert result.depth_valid.tolist() == [
        [False, True, True],
        [True, True, True],
    ]

    np.testing.assert_allclose(
        result.points_xyz_m[1],
        [0.033, -0.033, 0.099],
    )

    assert result.source_capture_id == cal.capture_id
    assert result.depth_scale_m_per_unit == 0.001
    assert (result.units, result.frame) == ("m", "depth_optical")
    assert result.provenance == "RAW_V2_PER_CAPTURE"


def test_counts_are_exclusive_and_sum_to_source_pixels():
    _, cal, proj = _data()
    result = select_valid_geometry(proj, calibration=cal)
    stats = result.statistics

    assert (
        stats.total_pixels,
        stats.accepted_points,
        stats.missing_depth,
    ) == (6, 5, 1)

    assert (
        stats.invalid_geometry
        == stats.below_min_depth
        == stats.above_max_depth
        == 0
    )

    assert stats.rejected_points == 1

    assert (
        sum(result.invalid_counts.values()) + stats.accepted_points
        == stats.total_pixels
    )


def test_min_max_filter_and_pixel_order():
    _, cal, proj = _data()

    result = select_valid_geometry(
        proj,
        calibration=cal,
        policy=DepthRangePolicy(0.05, 0.95),
    )

    assert result.depth_source_uv.tolist() == [
        [2, 0], [0, 1], [1, 1],
    ]

    np.testing.assert_allclose(
        result.points_xyz_m[:, 2],
        [0.099, 0.1, 0.9],
    )

    assert result.statistics.accepted_points == 3
    assert result.invalid_counts == {
        "missing_depth": 1,
        "invalid_geometry": 0,
        "below_min_depth": 1,
        "above_max_depth": 1,
    }


def test_source_arrays_untouched_and_result_arrays_read_only():
    depth, cal, proj = _data()

    raw_before = depth.copy()
    xyz_before = proj.xyz_m.copy()
    original_mask = proj.depth_valid_mask.copy()

    result = select_valid_geometry(proj, calibration=cal)

    np.testing.assert_array_equal(depth, raw_before)

    np.testing.assert_allclose(
        proj.xyz_m,
        xyz_before,
        equal_nan=True,
        rtol=0,
        atol=0,
    )

    np.testing.assert_array_equal(
        proj.depth_valid_mask,
        original_mask,
    )

    assert all(
        not array.flags.writeable
        for array in (
            result.points_xyz_m,
            result.depth_source_uv,
            result.depth_valid,
        )
    )

    assert not np.shares_memory(
        result.points_xyz_m,
        proj.xyz_m,
    )
    assert not np.shares_memory(
        result.depth_valid,
        proj.depth_valid_mask,
    )


def test_nonfinite_xyz_is_excluded_not_exported():
    _, cal, proj = _data()

    xyz = proj.xyz_m.copy()
    xyz[0, 2, 0] = np.inf

    result = select_valid_geometry(
        replace(proj, xyz_m=xyz),
        calibration=cal,
    )

    assert result.statistics.invalid_geometry == 1
    assert result.statistics.accepted_points == 4
    assert np.isfinite(result.points_xyz_m).all()
    assert (result.points_xyz_m[:, 2] > 0).all()


def test_inconsistent_metric_z_is_excluded():
    _, cal, proj = _data()

    xyz = proj.xyz_m.copy()
    xyz[1, 1, 2] += 0.2

    result = select_valid_geometry(
        replace(proj, xyz_m=xyz),
        calibration=cal,
    )

    assert result.statistics.invalid_geometry == 1
    assert result.statistics.accepted_points == 4


def test_empty_depth_fails_closed():
    _, cal, _ = _data()

    depth = np.zeros(
        (cal.depth_K.height, cal.depth_K.width),
        dtype=np.uint16,
    )

    proj = unproject_depth(
        depth,
        calibration=cal,
        capture_id=cal.capture_id,
    )

    with pytest.raises(GeometryValidityError) as err:
        select_valid_geometry(proj, calibration=cal)

    assert err.value.code == "EMPTY_VALID_DEPTH"


def test_all_filtered_depth_fails_closed():
    _, cal, proj = _data()

    with pytest.raises(GeometryValidityError) as err:
        select_valid_geometry(
            proj,
            calibration=cal,
            policy=DepthRangePolicy(2.0, 3.0),
        )

    assert err.value.code == "EMPTY_VALID_DEPTH"


@pytest.mark.parametrize("minimum,maximum", [
    (-1.0, None),
    (float("nan"), None),
    (float("inf"), None),
    (1.0, 1.0),
    (1.0, 0.9),
    (0.0, float("inf")),
])
def test_invalid_processing_range_rejected(minimum, maximum):
    with pytest.raises(GeometryValidityError) as err:
        DepthRangePolicy(minimum, maximum)

    assert err.value.code == "DEPTH_RANGE_INVALID"


def test_calibration_capture_mismatch_fails_closed():
    _, cal, proj = _data()

    with pytest.raises(GeometryValidityError) as err:
        select_valid_geometry(
            proj,
            calibration=replace(cal, capture_id="wrong"),
        )

    assert err.value.code == "CAPTURE_CONTEXT_MISMATCH"


@pytest.mark.parametrize("field,value", [
    ("depth_m", np.ones((3, 3), dtype=np.float64)),
    ("depth_valid_mask", np.ones((2, 3), dtype=np.uint8)),
    ("xyz_m", np.zeros((2, 3, 3), dtype=np.float32)),
])
def test_incompatible_projection_arrays_rejected(field, value):
    _, cal, proj = _data()

    with pytest.raises(GeometryValidityError) as err:
        select_valid_geometry(
            replace(proj, **{field: value}),
            calibration=cal,
        )

    assert err.value.code == "PROJECTION_INVALID"
