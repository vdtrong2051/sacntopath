
"""GD2-10.01: synthetic, hardware-free calibration contract checks."""
from dataclasses import FrozenInstanceError
from math import nan

import pytest

from scantopath.domain.raw_rgbd import RawDepthToColorExtrinsics, RawDistortion
from scantopath.modules.geometry.application.calibration import CalibrationContract, CalibrationError
from tests.support.raw_fixture import raw


def metadata(**replacements):
    return raw().metadata.model_copy(update=replacements)


def test_converts_extrinsic_mm_to_m_and_preserves_grid_sizes():
    d2c = RawDepthToColorExtrinsics(
        rotation=(1., 0., 0., 0., 1., 0., 0., 0., 1.),
        translation_mm=(-13.7, 1.0, 0.0),
    )
    c = CalibrationContract.from_metadata(metadata(depth_to_color=d2c))
    assert c.capture_id == "fixed-raw-id"
    assert (c.depth_K.width, c.depth_K.height) == (3, 2)
    assert (c.color_K.width, c.color_K.height) == (5, 4)
    assert c.translation_C_D_m == pytest.approx((-0.0137, 0.001, 0.0))
    assert c.depth_scale_m_per_unit == 0.001
    assert c.units == "m" and c.frame == "depth_optical"
    with pytest.raises(FrozenInstanceError):
        c.capture_id = "modified"


@pytest.mark.parametrize("sdk_model", [-1, 6, 99])
def test_unknown_distortion_fails_closed(sdk_model):
    d = RawDistortion(sdk_model=sdk_model, k1_k6_p1_p2=(0.,) * 8)
    with pytest.raises(CalibrationError) as e:
        CalibrationContract.from_metadata(metadata(depth_distortion=d))
    assert e.value.code == "DISTORTION_MODEL_UNSUPPORTED"


@pytest.mark.parametrize("sdk_model", [0, 1, 2, 3, 4, 5])
def test_known_sdk_ids_are_retained_without_claiming_projection(sdk_model):
    d = RawDistortion(sdk_model=sdk_model, k1_k6_p1_p2=(0.,) * 8)
    c = CalibrationContract.from_metadata(metadata(color_distortion=d))
    assert c.color_distortion.sdk_model == sdk_model


def test_zero_distortion_model_does_not_hide_nonzero_coefficients():
    d = RawDistortion(sdk_model=0, k1_k6_p1_p2=(0.1,) + (0.,) * 7)
    with pytest.raises(CalibrationError) as e:
        CalibrationContract.from_metadata(metadata(depth_distortion=d))
    assert e.value.code == "DISTORTION_COEFFICIENTS_INVALID"


def test_invalid_focal_length_and_depth_scale():
    original = raw().metadata
    bad = original.depth_intrinsics.model_copy(update={"fx": nan})
    with pytest.raises(CalibrationError) as e:
        CalibrationContract.from_metadata(metadata(depth_intrinsics=bad))
    assert e.value.code == "INTRINSICS_INVALID"
    with pytest.raises(CalibrationError) as e:
        CalibrationContract.from_metadata(metadata(depth_scale_m_per_unit=0.0))
    assert e.value.code == "DEPTH_SCALE_INVALID"


def test_mismatched_pixel_grids_rejected():
    original = raw().metadata
    bad = original.depth.model_copy(update={"width": 4})
    with pytest.raises(CalibrationError) as e:
        CalibrationContract.from_metadata(metadata(depth=bad))
    assert e.value.code == "INTRINSICS_INVALID"


def test_reflection_is_not_accepted_as_camera_rotation():
    bad = RawDepthToColorExtrinsics(
        rotation=(-1., 0., 0., 0., 1., 0., 0., 0., 1.),
        translation_mm=(0., 0., 0.),
    )
    with pytest.raises(CalibrationError) as e:
        CalibrationContract.from_metadata(metadata(depth_to_color=bad))
    assert e.value.code == "EXTRINSICS_INVALID"


def test_source_metadata_remains_unmodified():
    original = raw().metadata
    before = original.model_dump(mode="json")
    CalibrationContract.from_metadata(original)
    assert original.model_dump(mode="json") == before
