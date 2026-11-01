"""FT-05.7 conservative planar-support segmentation; synthetic deterministic data."""
from types import SimpleNamespace as NS
import numpy as np
import pytest
from scantopath.modules.geometry.application.live_object_isolation import (
    isolate_object_depth, IsolationConfig,
)
from scantopath.modules.geometry.application.live_geometry import LiveGeometryService,LiveGeometryError
from scantopath.modules.capture.application.live_calibration import LiveCalibrationSnapshot
from scantopath.modules.capture.application.live_stream import LiveNativeFrame,LiveRgbdFrame


def scene():
    d = np.full((160, 240), 1000, np.uint16)
    d[60:105, 90:150] = 940
    return d


def k(d):
    h, w = d.shape
    return NS(fx=230.,fy=230.,cx=w/2.,cy=h/2.)


def frame(d):
    h,w=d.shape
    p=NS(depth=NS(width=w,height=h),color=NS(width=10,height=10),
         depth_intrinsics=NS(width=w,height=h,fx=230.,fy=230.,cx=w/2.,cy=h/2.),
         color_intrinsics=NS(width=10,height=10,fx=500.,fy=500.,cx=5.,cy=5.),
         depth_distortion=NS(sdk_model=0,k1_k6_p1_p2=[0.]*8),
         color_distortion=NS(sdk_model=0,k1_k6_p1_p2=[0.]*8),
         depth_to_color=NS(rotation=[1.,0.,0.,0.,1.,0.,0.,0.,1.],translation_mm=[0.,0.,0.]),
         depth_scale_m_per_unit=.001,align_disabled=True)
    raw=LiveNativeFrame(color_mjpeg=b'jpeg',depth_y16_le=d.tobytes(),
        color_width=10,color_height=10,depth_width=w,depth_height=h,
        color_frame_index=4,depth_frame_index=5,color_timestamp_us=1000,
        depth_timestamp_us=1001,depth_scale_m_per_unit=.001,
        device_name='Orbbec Gemini 2',firmware='fake',
        calibration=LiveCalibrationSnapshot.from_native_packet(p))
    return LiveRgbdFrame(raw,np.zeros((10,10,3),np.uint8),d)


def test_ft057_01_only_elevated_component_not_support_plane():
    d=scene()
    saved=d.copy()
    result=isolate_object_depth(d,.001,k(d))
    assert result.status=='OBJECT_FOUND'
    assert 2200 <= result.selected_pixels <= 2700
    assert not result.object_mask[20,20] and result.object_mask[70,110]
    assert not result.object_mask.flags.writeable
    np.testing.assert_array_equal(saved,d)


def test_ft057_02_flat_scene_fails_closed():
    d=np.full((160,240),1000,np.uint16)
    result=isolate_object_depth(d,.001,k(d))
    assert not result.usable
    assert result.object_mask is None


def test_ft057_03_tight_roi_without_background_fails_closed():
    d=scene()
    result=isolate_object_depth(d,.001,k(d),depth_roi=(95,65,40,30))
    assert not result.usable
    assert result.object_mask is None


def test_ft057_04_invalid_and_missing_pixels_never_filled():
    d=scene();d[70,110]=0;d[80,120]=65535
    out=isolate_object_depth(d,.001,k(d))
    assert out.usable
    assert not out.object_mask[70,110] and not out.object_mask[80,120]
    assert out.object_mask[90,130]


def test_ft057_05_no_support_noise_fails_closed():
    rng=np.random.default_rng(24)
    d=rng.integers(500,1900,size=(160,240),dtype=np.uint16)
    r=isolate_object_depth(d,.001,k(d))
    assert not r.usable and r.object_mask is None


def test_ft057_06_roi_lineage_and_native_xyz_mask():
    d=scene()
    isolate=isolate_object_depth(d,.001,k(d),depth_roi=(50,35,140,100))
    assert isolate.usable
    f=frame(d)
    scene_cloud=LiveGeometryService.process(f,camera_generation=1,
                                            depth_roi=(50,35,140,100))
    object_cloud=LiveGeometryService.process(f,camera_generation=1,
        depth_roi=(50,35,140,100),object_mask=isolate.object_mask)
    assert object_cloud.statistics.output_points < scene_cloud.statistics.output_points
    uv=object_cloud.depth_source_uv
    assert np.all(isolate.object_mask[uv[:,1],uv[:,0]])
    assert object_cloud.coordinate_frame=='depth_optical'
    assert object_cloud.units=='m' and not object_cloud.metric_validated
    with pytest.raises(LiveGeometryError,match='native Depth bool grid'):
        LiveGeometryService.process(f,camera_generation=1,object_mask=np.ones((2,3),bool))


def test_ft057_07_two_objects_ambiguous_not_silent():
    d=np.full((160,240),1000,np.uint16)
    d[45:83,50:90]=930;d[95:133,140:180]=930
    r=isolate_object_depth(d,.001,k(d))
    assert r.status=='ISOLATION_AMBIGUOUS_OBJECTS'
    assert r.object_mask is None


def test_ft057_08_config_and_roi_limits():
    d=scene()
    with pytest.raises(ValueError):
        IsolationConfig(sample_step=0)
    with pytest.raises(ValueError):
        isolate_object_depth(d,.001,k(d),depth_roi=(200,0,50,30))
    with pytest.raises(ValueError):
        isolate_object_depth(d,0,k(d))
