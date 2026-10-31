"""UXH-01.2-C01: independent renderer-neutral style and safety contracts."""
import pytest
from scantopath.modules.viewer3d.infrastructure.spatial_visuals import (
    GRID_OPACITY, grid_line_rgb, origin_axes_length,
)


def test_origin_axis_size_is_deliberately_reduced():
    b = (2.0, 4.0, 3.0, 5.0, 6.0, 8.0)
    assert origin_axes_length(b) == pytest.approx(0.13)
    assert origin_axes_length(b) < 0.18 * 2.0
    assert origin_axes_length(b) > 0.0


@pytest.mark.parametrize('bounds', [
    (0, float('nan'), 0, 1, 0, 1),
    (1, 0, 0, 1, 0, 1),
    (0, 1, 0, float('inf'), 0, 1),
    (0, 1, 0, 1, 0),
])
def test_invalid_visual_bounds_rejected(bounds):
    with pytest.raises(ValueError, match='INVALID_VISUAL_BOUNDS'):
        origin_axes_length(bounds)


def test_major_minor_grid_has_a_real_visual_hierarchy():
    major = {i for i in range(42) if grid_line_rgb(i) == grid_line_rgb(20)}
    assert major == {0, 1, 10, 11, 20, 21, 30, 31, 40, 41}
    assert sum(grid_line_rgb(20)) > sum(grid_line_rgb(18))
    assert 0 < GRID_OPACITY < 0.35
    assert len({grid_line_rgb(i) for i in range(42)}) == 2


@pytest.mark.parametrize('bad', [-1, 42, 0.5, True, '0'])
def test_invalid_grid_segment_rejected(bad):
    with pytest.raises(ValueError, match='INVALID_GRID_SEGMENT'):
        grid_line_rgb(bad)
