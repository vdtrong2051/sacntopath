
"""GD2-10.06: provisional distance ground truth and lineage gates."""
from dataclasses import FrozenInstanceError, replace
from math import sqrt

import numpy as np
import pytest

from scantopath.modules.geometry.application.measurements import (
    MeasurementError,
    measure_points,
    measure_selected_points,
    select_measurement_point,
)
from scantopath.modules.geometry.application.validity import (
    DepthRangePolicy,
    GeometryStatistics,
    ValidGeometry,
)


def cloud() -> ValidGeometry:
    xyz = np.array([
        [0.0, 0.0, 1.0],
        [0.3, 0.4, 1.0],
        [0.0, 0.0, 2.0],
    ], dtype=np.float64)

    uv = np.array(
        [[0, 0], [1, 0], [2, 0]],
        dtype=np.int32,
    )

    mask = np.ones((1, 3), dtype=np.bool_)

    for array in (xyz, uv, mask):
        array.setflags(write=False)

    return ValidGeometry(
        source_capture_id="capture-a",
        points_xyz_m=xyz,
        depth_source_uv=uv,
        depth_valid=mask,
        depth_scale_m_per_unit=0.001,
        statistics=GeometryStatistics(
            total_pixels=3,
            accepted_points=3,
            missing_depth=0,
            invalid_geometry=0,
            below_min_depth=0,
            above_max_depth=0,
        ),
        depth_policy=DepthRangePolicy(),
    )


def test_ground_truth_3_4_5_and_explicit_provisional_warning():
    result = measure_points(cloud(), 0, 1)

    assert result.distance_m == pytest.approx(0.5)
    assert result.distance_mm == pytest.approx(500.0)
    assert result.point_indices == (0, 1)

    assert (result.frame, result.units) == (
        "depth_optical", "m"
    )

    assert result.status == "PROVISIONAL_NOT_METRIC_VALIDATED"
    assert "not a validated physical dimension" in result.warning
    assert result.source_capture_id == "capture-a"


def test_non_axis_aligned_3d_distance_uses_z():
    result = measure_points(cloud(), 1, 2)

    assert result.distance_m == pytest.approx(sqrt(1.25))
    assert result.distance_mm == pytest.approx(
        1000 * sqrt(1.25)
    )


def test_same_index_zero_distance_remains_provisional():
    result = measure_points(cloud(), 1, 1)

    assert result.distance_m == 0
    assert result.distance_mm == 0
    assert result.status == "PROVISIONAL_NOT_METRIC_VALIDATED"


def test_selections_from_same_cloud_are_interoperable():
    geometry = cloud()

    a = select_measurement_point(geometry, 0)
    b = select_measurement_point(geometry, 1)

    assert a.cloud_revision_sha256 == b.cloud_revision_sha256
    assert len(a.cloud_revision_sha256) == 64

    assert measure_selected_points(a, b).distance_m == pytest.approx(
        0.5
    )


def test_different_capture_rejected():
    first = select_measurement_point(cloud(), 0)
    second = select_measurement_point(
        replace(cloud(), source_capture_id="capture-b"), 1
    )

    with pytest.raises(
        MeasurementError,
        match="same cloud revision",
    ) as error:
        measure_selected_points(first, second)

    assert error.value.code == "MEASUREMENT_FRAME_MISMATCH"


@pytest.mark.parametrize("field,value", [
    ("frame", "color_optical"),
    ("units", "mm"),
    ("cloud_revision_sha256", "0" * 64),
])
def test_rejects_mixed_frame_units_or_revision(field, value):
    geometry = cloud()

    first = select_measurement_point(geometry, 0)
    second = replace(
        select_measurement_point(geometry, 1),
        **{field: value},
    )

    with pytest.raises(MeasurementError) as error:
        measure_selected_points(first, second)

    assert error.value.code == "MEASUREMENT_FRAME_MISMATCH"


def test_cloud_content_change_invalidates_old_selection():
    original = cloud()
    first = select_measurement_point(original, 0)

    changed = original.points_xyz_m.copy()
    changed[2, 2] = 2.5

    second = select_measurement_point(
        replace(original, points_xyz_m=changed),
        1,
    )

    with pytest.raises(MeasurementError) as error:
        measure_selected_points(first, second)

    assert error.value.code == "MEASUREMENT_FRAME_MISMATCH"


@pytest.mark.parametrize("index", [-1, 3, 1.0, True])
def test_invalid_index_is_rejected(index):
    with pytest.raises(MeasurementError) as error:
        select_measurement_point(cloud(), index)

    assert error.value.code == "MEASUREMENT_POINT_INVALID"


def test_nonfinite_point_is_rejected():
    geometry = cloud()
    xyz = geometry.points_xyz_m.copy()
    xyz[0, 0] = np.nan

    with pytest.raises(MeasurementError) as error:
        select_measurement_point(
            replace(geometry, points_xyz_m=xyz),
            0,
        )

    assert error.value.code == "MEASUREMENT_POINT_INVALID"


def test_missing_pixel_lineage_is_rejected():
    geometry = cloud()
    mask = geometry.depth_valid.copy()
    mask[0, 0] = False

    with pytest.raises(MeasurementError) as error:
        select_measurement_point(
            replace(geometry, depth_valid=mask),
            0,
        )

    assert error.value.code == "MEASUREMENT_POINT_INVALID"


def test_no_source_mutation_and_result_is_frozen():
    geometry = cloud()
    original = geometry.points_xyz_m.copy()

    result = measure_points(geometry, 0, 1)

    np.testing.assert_array_equal(
        geometry.points_xyz_m,
        original,
    )

    with pytest.raises(FrozenInstanceError):
        result.distance_m = 2.0


def test_invalid_selection_type_rejected():
    with pytest.raises(MeasurementError) as error:
        measure_selected_points("bad", "bad")

    assert error.value.code == "MEASUREMENT_INPUT_INVALID"


def test_single_view_xyzrgb_can_be_measured_without_requiring_color_on_each_point():
    from scantopath.modules.geometry.application.service import (
        GeometryService,
    )
    from tests.support.raw_fixture import raw

    packet = raw()
    meta = packet.metadata

    rgb = np.zeros(
        (meta.color.height, meta.color.width, 3),
        dtype=np.uint8,
    )

    view = GeometryService.process(
        depth_u16=packet.depth_u16_copy(),
        color_rgb=rgb,
        metadata=meta,
        capture_id=meta.capture_id,
    )

    a = select_measurement_point(view, 0)
    b = select_measurement_point(view.geometry, 1)

    assert measure_selected_points(a, b).distance_m > 0
