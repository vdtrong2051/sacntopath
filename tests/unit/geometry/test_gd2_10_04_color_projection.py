
"""GD2-10.04: synthetic D2C, distortion, visibility and rejection tests."""
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
    select_valid_geometry,
)
from scantopath.modules.geometry.application.color_projection import (
    ColorProjectionError,
    project_to_color,
)
from tests.support.raw_fixture import raw


def sample():
    packet = raw()
    calibration = CalibrationContract.from_metadata(
        packet.metadata
    )
    projection = unproject_depth(
        packet.depth_u16_copy(),
        calibration=calibration,
        capture_id=calibration.capture_id,
    )
    geometry = select_valid_geometry(
        projection, calibration=calibration
    )
    return geometry, calibration


def test_identity_projection_with_different_grids():
    geometry, calibration = sample()
    result = project_to_color(
        geometry, calibration=calibration
    )

    assert result.color_valid.tolist() == [True] * 5
    assert result.color_pixel_uv.tolist() == [
        [2, 1],
        [3, 1],
        [1, 2],
        [2, 2],
        [3, 2],
    ]

    np.testing.assert_allclose(
        result.color_uv[1],
        [2 + 4 / 3, 2 - 4 / 3],
    )
    assert result.sampling == "nearest_half_up"
    assert result.frame == "color_optical"


def test_nonidentity_translation_in_metres():
    geometry, calibration = sample()

    # 0.225 m translation corresponds to 225 mm D2C.
    calibration = replace(
        calibration,
        translation_C_D_m=(0.225, 0.0, 0.0),
    )

    result = project_to_color(
        geometry, calibration=calibration
    )

    assert result.color_pixel_uv[3].tolist() == [3, 2]
    assert result.color_valid[3]


def test_nonidentity_rotation():
    geometry, calibration = sample()

    calibration = replace(
        calibration,
        rotation_C_D=(
            0., -1., 0.,
            1.,  0., 0.,
            0.,  0., 1.,
        ),
    )

    result = project_to_color(
        geometry, calibration=calibration
    )

    np.testing.assert_allclose(
        result.color_uv[1],
        [2 + 4 / 3, 2 + 4 / 3],
    )
    assert result.color_pixel_uv[1].tolist() == [3, 3]


def test_point_behind_color_camera_is_rejected():
    geometry, calibration = sample()

    calibration = replace(
        calibration,
        translation_C_D_m=(0.0, 0.0, -1.0),
    )

    result = project_to_color(
        geometry, calibration=calibration
    )

    assert not result.color_valid[3]
    assert result.color_pixel_uv[3].tolist() == [-1, -1]


def test_outside_color_image_is_not_colored():
    geometry, calibration = sample()

    calibration = replace(
        calibration,
        translation_C_D_m=(2.0, 0.0, 0.0),
    )

    result = project_to_color(
        geometry, calibration=calibration
    )

    assert not result.color_valid.any()
    assert not result.in_color_bounds.any()


def test_zbuffer_rejects_farther_points():
    geometry, calibration = sample()

    # Make every projected point fall into one Color pixel.
    calibration = replace(
        calibration,
        color_K=replace(
            calibration.color_K,
            fx=0.1,
            fy=0.1,
        ),
    )

    result = project_to_color(
        geometry,
        calibration=calibration,
        occlusion_tolerance_m=0.0,
    )

    assert result.color_valid.tolist() == [
        True, False, False, False, False,
    ]
    assert result.occluded.tolist() == [
        False, True, True, True, True,
    ]


def test_equal_depth_collisions_remain_visible():
    packet = raw()
    calibration = CalibrationContract.from_metadata(
        packet.metadata
    )

    depth = packet.depth_u16_copy()
    depth[depth > 0] = 1000

    projection = unproject_depth(
        depth,
        calibration=calibration,
        capture_id=calibration.capture_id,
    )
    geometry = select_valid_geometry(
        projection, calibration=calibration
    )

    calibration = replace(
        calibration,
        color_K=replace(
            calibration.color_K,
            fx=0.1,
            fy=0.1,
        ),
    )

    result = project_to_color(
        geometry, calibration=calibration
    )
    assert result.color_valid.sum() == 5


def test_brown_conrady_radial_distortion():
    geometry, calibration = sample()

    distortion = replace(
        calibration.color_distortion,
        sdk_model=3,
        k1_k6_p1_p2=(
            0.5, 0., 0., 0., 0., 0., 0., 0.,
        ),
    )
    calibration = replace(
        calibration,
        color_distortion=distortion,
    )

    result = project_to_color(
        geometry, calibration=calibration
    )

    # x=1/3, y=-1/3, r²=2/9, radial=10/9.
    np.testing.assert_allclose(
        result.color_uv[1],
        [2 + 40 / 27, 2 - 40 / 27],
    )


def test_brown_conrady_tangential_distortion():
    geometry, calibration = sample()

    distortion = replace(
        calibration.color_distortion,
        sdk_model=3,
        k1_k6_p1_p2=(
            0., 0., 0., 0., 0., 0., 0.1, 0.2,
        ),
    )
    calibration = replace(
        calibration,
        color_distortion=distortion,
    )

    result = project_to_color(
        geometry, calibration=calibration
    )

    x = 1 / 3
    r2 = x * x
    projected_x = x + 0.2 * (r2 + 2 * x * x)
    projected_y = 0.1 * r2

    np.testing.assert_allclose(
        result.color_uv[4],
        [4 * projected_x + 2, 4 * projected_y + 2],
    )


@pytest.mark.parametrize("model", [1, 2, 4, 5, 9])
def test_unsupported_distortion_fails_closed(model):
    geometry, calibration = sample()

    distortion = replace(
        calibration.color_distortion,
        sdk_model=model,
    )
    calibration = replace(
        calibration,
        color_distortion=distortion,
    )

    with pytest.raises(ColorProjectionError) as error:
        project_to_color(
            geometry, calibration=calibration
        )

    assert error.value.code == "DISTORTION_MODEL_UNSUPPORTED"


def test_none_model_rejects_nonzero_coefficients():
    geometry, calibration = sample()

    distortion = replace(
        calibration.color_distortion,
        k1_k6_p1_p2=(0.1,) + (0.,) * 7,
    )
    calibration = replace(
        calibration,
        color_distortion=distortion,
    )

    with pytest.raises(ColorProjectionError) as error:
        project_to_color(
            geometry, calibration=calibration
        )

    assert error.value.code == "DISTORTION_COEFFICIENTS_INVALID"


def test_brown_model_rejects_unverified_k6_coefficients():
    geometry, calibration = sample()

    distortion = replace(
        calibration.color_distortion,
        sdk_model=3,
        k1_k6_p1_p2=(
            0., 0., 0., 0.1, 0., 0., 0., 0.,
        ),
    )
    calibration = replace(
        calibration,
        color_distortion=distortion,
    )

    with pytest.raises(ColorProjectionError) as error:
        project_to_color(
            geometry, calibration=calibration
        )

    assert error.value.code == "DISTORTION_COEFFICIENTS_INVALID"


def test_capture_mismatch_is_rejected():
    geometry, calibration = sample()

    calibration = replace(
        calibration,
        capture_id="different-capture",
    )

    with pytest.raises(ColorProjectionError) as error:
        project_to_color(
            geometry, calibration=calibration
        )

    assert error.value.code == "CAPTURE_CONTEXT_MISMATCH"


def test_nonfinite_geometry_is_rejected():
    geometry, calibration = sample()

    xyz = geometry.points_xyz_m.copy()
    xyz[0, 0] = np.nan
    geometry = replace(geometry, points_xyz_m=xyz)

    with pytest.raises(ColorProjectionError) as error:
        project_to_color(
            geometry, calibration=calibration
        )

    assert error.value.code == "GEOMETRY_INVALID"


def test_source_is_unchanged_and_output_read_only():
    geometry, calibration = sample()
    original = geometry.points_xyz_m.copy()

    result = project_to_color(
        geometry, calibration=calibration
    )

    np.testing.assert_array_equal(
        geometry.points_xyz_m, original
    )

    assert all(
        not array.flags.writeable
        for array in (
            result.color_uv,
            result.color_pixel_uv,
            result.color_valid,
            result.in_color_bounds,
            result.occluded,
            result.color_z_m,
        )
    )


@pytest.mark.parametrize(
    "epsilon",
    [-1.0, np.inf, np.nan],
)
def test_invalid_occlusion_tolerance_rejected(epsilon):
    geometry, calibration = sample()

    with pytest.raises(ColorProjectionError) as error:
        project_to_color(
            geometry,
            calibration=calibration,
            occlusion_tolerance_m=epsilon,
        )

    assert error.value.code == "OCCLUSION_POLICY_INVALID"
