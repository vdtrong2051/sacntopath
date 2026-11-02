"""FT08.16 ICP: adapt sampling to FT05.8's measured small-object mask.

No camera, RAW, Qt, SDK or GPU in these tests. No changes to FT05.8.
"""
from __future__ import annotations
import numpy as np
import pytest

from scantopath.modules.reconstruction.application.contracts import InputCloud, RegistrationConfig, RegistrationError
from scantopath.modules.reconstruction.application.live_pair import (
    LivePairView, _adaptive_object_registration_config,
)
from scantopath.modules.reconstruction.application.two_view_registration import register_two_views


def _view(points: np.ndarray, name: str) -> LivePairView:
    ref = dict(isolation_source='FT-05.8_CHARUCO', isolation_status='CHARUCO_OBJECT_FOUND',
               board_corners=19, board_support_fraction=0.71)
    cloud = InputCloud(name, np.asarray(points, dtype=np.float64), 'f'*64, (), None)
    return LivePairView(cloud, ref, (0,0,1280,800), len(points))


def _small_object_points():
    rng = np.random.default_rng(2026)
    # 75x80x50 mm shaped 3-D point distribution: coarse 20 mm grid <80 cells,
    # yet many independent 10/15 mm measured voxels are present.
    p = rng.uniform([0,0,0],[.075,.080,.050],size=(720,3))
    p[:,2] += .70
    return p


def test_small_nonplanar_object_refines_coarse_scale_and_preserves_gates():
    v0=_view(_small_object_points(),'view0')
    v1=_view(_small_object_points(),'view1')
    baseline=RegistrationConfig()
    metrics={}
    adapted=_adaptive_object_registration_config(v0,v1,baseline,metrics)
    assert adapted.voxel_scales_m[0] < .020
    assert adapted.min_correspondences == baseline.min_correspondences == 80
    assert adapted.min_overlap == baseline.min_overlap
    assert adapted.max_rmse_m == baseline.max_rmse_m
    assert adapted.min_covariance_ratio == baseline.min_covariance_ratio
    assert adapted.correspondences_m[0] <= baseline.correspondences_m[0]
    assert metrics['adaptive_voxel'] is True
    assert metrics['isolation_status']==['CHARUCO_OBJECT_FOUND']*2
    assert metrics['selected_measured_points']==[720]*2
    assert metrics['voxel_candidates_tested'][0]['voxel_m']==.02
    assert metrics['voxel_candidates_tested'][0]['view0_voxels_at_least'] < 80


def test_small_object_pair_runs_icp_instead_of_too_few_voxels():
    p0=_small_object_points()
    angle=.07
    c,s=np.cos(angle),np.sin(angle)
    R=np.array([[c,-s,0],[s,c,0],[0,0,1]])
    T=np.eye(4); T[:3,:3]=R; T[:3,3]=[.012,.005,.001]
    # Same static object from moving camera 1: inverse T.
    p1=(p0-T[:3,3])@R
    v0,v1=_view(p0,'v0'),_view(p1,'v1')
    cfg=_adaptive_object_registration_config(v0,v1,RegistrationConfig())
    result=register_two_views(v0.cloud,v1.cloud,cfg,initial_T_world_depth1=T)
    assert result.accepted, result.quality.reject_reasons
    assert result.quality.inlier_count >= 80
    np.testing.assert_allclose(result.T_world_depth_1,T,atol=.004)


def test_baseline_unchanged_when_coarse_voxels_sufficient():
    p=np.random.default_rng(44).uniform([-.2,-.2,.4],[.2,.2,.8],size=(1100,3))
    v0,v1=_view(p,'0'),_view(p,'1')
    cfg=RegistrationConfig()
    actual=_adaptive_object_registration_config(v0,v1,cfg)
    assert actual is cfg
    assert v0.source_ref['adaptive_voxel'] is False


def test_tiny_object_stays_blocked_does_not_relax_inlier_minimum():
    p=np.random.default_rng(21).uniform([0,0,.7],[.006,.006,.706],size=(600,3))
    v0,v1=_view(p,'0'),_view(p,'1')
    log={}
    with pytest.raises(RegistrationError) as err:
        _adaptive_object_registration_config(v0,v1,RegistrationConfig(),log)
    assert err.value.code == 'TOO_FEW_OBJECT_VOXELS'
    assert log['required_min_correspondences']==80
    assert len(log['voxel_candidates_tested'])>=2


def test_unchanged_object_mask_provenance_during_adaptation():
    p=_small_object_points()
    v0,v1=_view(p,'0'),_view(p,'1')
    before=p.tobytes()
    _adaptive_object_registration_config(v0,v1,RegistrationConfig())
    assert p.tobytes()==before
    assert v0.source_ref['isolation_source']=='FT-05.8_CHARUCO'
    assert v0.source_ref['icp_min_correspondences_unchanged']==80
