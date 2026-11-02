"""Narrow synthetic contract checks; not proof of actual Gemini 2 reconstruction."""
from __future__ import annotations
import numpy as np
from scantopath.modules.reconstruction.application.contracts import (
    RegistrationConfig, InputCloud, RegistrationError)
from scantopath.modules.reconstruction.application.two_view_registration import (
    register_two_views, _apply)


def cloud(label, points):
    return InputCloud(label, points.astype(np.float64), 'f' * 64, ())


def object_points():
    rng = np.random.default_rng(18)
    # Irregular 3D specimen; deliberately NOT a plane or symmetric sphere.
    p = rng.uniform(-0.11, 0.11, size=(3500, 3))
    p[:, 2] += 0.85 + 0.14 * p[:, 0] * p[:, 1] + 0.09 * p[:, 0] ** 2
    return p


def test_known_transform_and_direction():
    p0 = object_points()
    a = 0.08
    R = np.array([[np.cos(a), 0, np.sin(a)], [0, 1, 0],
                  [-np.sin(a), 0, np.cos(a)]])
    T = np.eye(4); T[:3, :3] = R; T[:3, 3] = [0.013, -0.009, 0.015]
    source = _apply(p0, np.linalg.inv(T))
    rng = np.random.default_rng(44)
    # Small acquisition noise; identical shape in two camera frames.
    source = source + rng.normal(0, 0.0006, size=source.shape)
    output = register_two_views(cloud('c0', p0), cloud('c1', source))
    assert output.accepted, output.quality.reject_reasons
    assert np.linalg.norm(output.T_world_depth_1[:3, 3] - T[:3, 3]) < 0.008
    assert np.linalg.norm(output.T_world_depth_1[:3, :3] - R) < 0.06
    assert output.quality.overlap >= 0.28
    assert output.quality.inlier_rmse_m < 0.009


def test_bad_overlap_rejected():
    p0 = object_points()
    rng = np.random.default_rng(88)
    p1 = rng.uniform(2.0, 3.0, size=(3500, 3))
    result = register_two_views(cloud('c0', p0), cloud('c1', p1))
    assert not result.accepted
    assert result.T_world_depth_1 is None
    assert result.world_xyz_0 is None


def test_planar_degenerate_rejected():
    rng = np.random.default_rng(6)
    p = rng.uniform(-0.2, 0.2, size=(2000, 3)); p[:, 2] = 0.6
    result = register_two_views(cloud('c0', p), cloud('c1', p + [0.004, 0, 0]))
    assert not result.accepted
    assert 'GEOMETRY_DEGENERATE' in result.quality.reject_reasons


def test_duplicate_capture_cannot_be_reconstruction():
    p = object_points()
    try:
        register_two_views(cloud('a', p), cloud('a', p.copy()))
    except RegistrationError as exc:
        assert exc.code == 'DUPLICATE_CAPTURE'
    else:
        raise AssertionError('Same capture incorrectly accepted')


def test_two_views_with_partial_overlap():
    p = object_points()
    # One scan sees the first 85%; another sees the last 80%. Common 65%.
    a = p[:2950]
    b = p[700:] + [0.012, -0.003, 0.004]
    result = register_two_views(cloud('r0', a), cloud('r1', b))
    assert result.accepted, result.quality.reject_reasons
    assert result.quality.overlap >= 0.28


def test_replay_without_distinct_view_motion_rejected():
    p = object_points()
    result = register_two_views(cloud('frame0', p), cloud('frame1', p.copy()))
    assert not result.accepted
    assert 'NO_DISTINCT_VIEW_MOTION' in result.quality.reject_reasons
