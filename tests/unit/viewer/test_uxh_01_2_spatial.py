"""UXH-01.2: finite independent reference-plane contract."""
import math
import pytest
from scantopath.modules.viewer3d.application.spatial_reference import (
    build_reference_grid, GRID_MODES, HALF_LINES,
)

B = (1.2, 3.4, 2.4, 6.2, 4.5, 9.0)

@pytest.mark.parametrize('mode,axis,value', [
    ('xy', 2, 0.0), ('xz', 1, 0.0), ('yz', 0, 0.0), ('base', 2, 4.5),
])
def test_plane_equations_and_bounded_lines(mode, axis, value):
    plan = build_reference_grid(B, mode)
    assert plan.mode in GRID_MODES
    assert len(plan.segments) == 2 * (2 * HALF_LINES + 1)
    assert plan.normal_axis == axis and plan.plane_value == value
    assert plan.step > 0 and math.isfinite(plan.step)
    for p, q in plan.segments:
        assert p[axis] == value and q[axis] == value
        assert all(math.isfinite(v) for v in p + q)
    assert B == (1.2, 3.4, 2.4, 6.2, 4.5, 9.0)


def test_spacing_adapts_to_scene_extent():
    small = build_reference_grid((0, 1, 0, 1, 0, 1), 'xy')
    large = build_reference_grid((0, 100, 0, 100, 0, 1), 'xy')
    assert large.step > small.step
    assert len(large.segments) == len(small.segments)


@pytest.mark.parametrize('mode', ['floor', 'world', '', None, 0, 'XY'])
def test_reject_unknown_grid_modes(mode):
    with pytest.raises(ValueError, match='INVALID_REFERENCE_GRID'):
        build_reference_grid(B, mode)


@pytest.mark.parametrize('bounds', [
    (1, 0, 2, 3, 4, 5), (0, float('nan'), 2, 3, 4, 5),
    (0, float('inf'), 2, 3, 4, 5), (0, 1, 2, 3),
    (0, 1, 0, 1, 0, True),
])
def test_reject_bad_bounds(bounds):
    with pytest.raises(ValueError, match='INVALID_GRID_BOUNDS'):
        build_reference_grid(bounds, 'xy')


def test_depth_optical_axis_planes_are_not_world_floor():
    # z=0 is the depth sensor's image-plane location, not a real floor.
    plan = build_reference_grid((-.5, .5, -.5, .5, 1, 3), 'xy')
    assert all(p[2] == q[2] == 0 for p, q in plan.segments)
    assert build_reference_grid((-.5, .5, -.5, .5, 1, 3), 'base').plane_value == 1
