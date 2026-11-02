"""C1 fast functional and negative tests; independent of camera and SQLite."""
import json
import numpy as np
import pytest

from scantopath.modules.reconstruction.application.c1_trusted_geometry import (
    C1Config, C1Error, filter_outliers, estimate_normals, measured_voxel,
    registration_check, validate_metric, neighbours,
)


def plane(seed=7,n=1600):
    rng=np.random.default_rng(seed)
    xy=rng.uniform(-0.05,0.05,(n,2))
    z=0.65+rng.normal(0,0.0003,(n,1))
    return np.column_stack((xy,z))


def test_knn_shapes():
    points=plane(n=100)
    d,idx=neighbours(points,points,5)
    assert d.shape==(100,5) and idx.shape==(100,5)
    assert d[:,0].max()<1e-8


def test_knn_invalid():
    with pytest.raises(C1Error,match='C1_KNN_INVALID'):
        neighbours(plane(n=100),plane(n=10),101)


def test_voxel_keeps_existing_measurements_and_source():
    pts=np.array([[0.,0.,1.],[0.001,0.001,1.001],[0.02,0,1.]],dtype=float)
    result,origins=measured_voxel(pts,[0,1,2],C1Config())
    assert len(result)==2
    assert any(np.array_equal(p,pts[0]) for p in result)
    assert 1 not in origins


def test_voxel_limit_rejects_not_silently_truncates():
    cfg=C1Config(max_points=500,voxel_m=.001)
    pts=np.column_stack((np.arange(600)*0.005,np.zeros(600),np.ones(600)))
    with pytest.raises(C1Error,match='C1_POINT_BUDGET_EXCEEDED'):
        measured_voxel(pts,np.zeros(len(pts)),cfg)


def test_sor_removes_extreme_outlier():
    pts=np.vstack((plane(n=1200),[8.,8.,8.]))
    clean,origin,report=filter_outliers(pts,np.zeros(len(pts)),C1Config())
    assert len(clean)<len(pts)
    assert np.max(clean[:,0])<1
    assert len(origin)==len(clean)
    assert report['removed_outliers']>=1


def test_normal_estimation_unit_and_camera_oriented():
    cfg=C1Config()
    pts=plane(n=450)
    normals,stats=estimate_normals(pts,np.zeros(len(pts)),{0:np.array([0.,0.,0.])},cfg)
    assert np.all(np.isfinite(normals))
    assert np.max(np.abs(np.linalg.norm(normals,axis=1)-1))<1e-5
    # Camera is below plane; normals point toward it on average.
    assert np.mean(normals[:,2]) < -.75
    assert stats['globally_outward_verified'] is False


def test_missing_camera_origin_rejected():
    with pytest.raises(C1Error,match='C1_CAMERA_ORIGIN_MISSING'):
        estimate_normals(plane(n=450),np.ones(450,dtype=np.int32),{0:np.zeros(3)},C1Config())


def test_registration_accepts_consistent_views():
    a=plane(n=800)
    b=a + np.array([.001,0.,0.])
    report=registration_check(a,b,C1Config())
    assert report['state']=='ACCEPTED_PROVISIONAL'
    assert report['overlap']>.90


def test_registration_rejects_wrong_pose():
    a=plane(n=700)
    b=a+np.array([.4,0,0])
    report=registration_check(a,b,C1Config())
    assert report['state']=='REJECTED'
    assert 'LOW_GEOMETRIC_OVERLAP' in report['reason']


def test_registration_rejects_too_few():
    a=plane(n=110)
    b=plane(n=25)
    assert registration_check(a,b,C1Config())['reason']=='TOO_FEW_POINTS'


def test_metric_missing_reference_is_not_tested():
    assert validate_metric(plane(n=250),None)['gate']=='NOT_TESTED'


def test_metric_reference_requires_axis_alignment():
    ref={'axes_mm':{'x':100.,'y':100.,'z':1.},
         'measurement_method':'caliper','reference_instrument':'caliper',
         'axis_alignment_confirmed':False}
    with pytest.raises(C1Error,match='C1_REFERENCE_EVIDENCE_INCOMPLETE'):
        validate_metric(plane(n=250),ref)


def test_metric_reference_provisional_pass_or_fail():
    pts=np.array([[0,0,0.5],[.1,.1,.6],[.03,.07,.56]],dtype=float)
    r={'axes_mm':{'x':100.,'y':100.,'z':100.},'measurement_method':'caliper',
       'reference_instrument':'digital caliper','axis_alignment_confirmed':True}
    result=validate_metric(pts,r)
    assert result['gate']=='DEMO_GATE_PASS_PROVISIONAL'
    assert result['metric_accuracy_verified'] is False
    r['axes_mm']['x']=140.
    assert validate_metric(pts,r)['gate']=='DEMO_GATE_FAIL'


def test_nan_and_malformed_rejected():
    with pytest.raises(C1Error,match='C1_XYZ_INVALID'):
        filter_outliers(np.array([[np.nan,0.,0.]]),np.array([0]),C1Config())


def test_no_infinite_normals_on_noisy_plane():
    a=plane(seed=15,n=650)
    n,info=estimate_normals(a,np.ones(len(a),dtype=np.int32),{1:np.array([0.,0.,0.])},C1Config())
    assert info['finite_fraction']==1.0
    assert n.shape==a.shape
