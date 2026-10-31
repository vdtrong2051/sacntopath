"""No Qt/VTK/RAW required: test exact Depth pixel -> float64 XYZ index."""
from types import SimpleNamespace

import numpy as np
import pytest

from scantopath.modules.geometry.application.depth_pixel_picker import DepthPixelPicker, DepthPickError


def fixture():
    # Three valid points in a 3x4 Depth grid, one has no RGB.
    return SimpleNamespace(
        frame='depth_optical', units='m', metric_validated=False,
        points_xyz_m=np.array([[0., 0., 0.3], [0.1, 0.2, 0.5], [0.2, 0.1, 0.7]], dtype=np.float64),
        depth_source_uv=np.array([[1, 0], [2, 1], [3, 2]], dtype=np.int32),
        depth_valid=np.array([[False, True, False, False], [False, False, True, False],
                              [False, False, False, True]], dtype=np.bool_),
        colored_point_indices=np.array([0, 2], dtype=np.int32),
        colors_rgb=np.array([[255, 10, 20], [20, 70, 180]], dtype=np.uint8),
    )


def test_exact_depth_id_is_original_xyz_index_not_rgb_subset():
    picker = DepthPixelPicker(fixture())
    hit = picker.hit(2, 1)
    assert hit.index == 1 and not hit.snapped
    assert picker.hit(-1, 0) is None
    assert picker.hit(0, 2, radius=0) is None


def test_depth_aligned_image_has_gray_for_uncolored_and_black_for_missing():
    rgb = DepthPixelPicker(fixture()).make_rgb_depth_image()
    assert rgb.shape == (3, 4, 3)
    assert rgb[0, 1].tolist() == [255, 10, 20]
    assert rgb[2, 3].tolist() == [20, 70, 180]
    assert len(set(rgb[1, 2])) == 1  # valid depth, no mapped RGB
    assert rgb[2, 0].tolist() == [0, 0, 0]


def test_duplicate_depth_pixel_fails_closed():
    a = fixture()
    a.depth_source_uv[1] = a.depth_source_uv[0]
    with pytest.raises(DepthPickError) as exc:
        DepthPixelPicker(a)
    assert exc.value.code == 'DEPTH_PIXEL_MAPPING_INVALID' or exc.value.code == 'DEPTH_PIXEL_DUPLICATE'


def test_unverified_provenance_rejected():
    a = fixture()
    a.metric_validated = True
    with pytest.raises(DepthPickError) as exc:
        DepthPixelPicker(a)
    assert exc.value.code == 'DEPTH_PROVENANCE_INVALID'
