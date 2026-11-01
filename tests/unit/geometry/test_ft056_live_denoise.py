"""FT-05.6 geometry tests, synthetic-only; FT-02 default stays unfiltered."""
from types import SimpleNamespace as NS
import numpy as np
import pytest
from scantopath.modules.capture.application.live_calibration import LiveCalibrationSnapshot
from scantopath.modules.capture.application.live_stream import LiveNativeFrame, LiveRgbdFrame
from scantopath.modules.geometry.application.live_geometry import LiveGeometryService, LiveGeometryError
from scantopath.modules.geometry.application.live_denoise import local_depth_support_mask


def frame(depth):
    h,w=depth.shape
    p=NS(depth=NS(width=w,height=h),color=NS(width=10,height=10),
        depth_intrinsics=NS(width=w,height=h,fx=500.,fy=500.,cx=w/2,cy=h/2),
        color_intrinsics=NS(width=10,height=10,fx=500.,fy=500.,cx=5.,cy=5.),
        depth_distortion=NS(sdk_model=0,k1_k6_p1_p2=[0.]*8),
        color_distortion=NS(sdk_model=0,k1_k6_p1_p2=[0.]*8),
        depth_to_color=NS(rotation=[1.,0.,0.,0.,1.,0.,0.,0.,1.],translation_mm=[0.,0.,0.]),
        depth_scale_m_per_unit=.001,align_disabled=True)
    raw=LiveNativeFrame(color_mjpeg=b'jpeg',depth_y16_le=depth.tobytes(),
        color_width=10,color_height=10,depth_width=w,depth_height=h,
        color_frame_index=4,depth_frame_index=5,color_timestamp_us=1000,
        depth_timestamp_us=1001,depth_scale_m_per_unit=.001,
        device_name='Orbbec Gemini 2',firmware='fake',
        calibration=LiveCalibrationSnapshot.from_native_packet(p))
    return LiveRgbdFrame(raw,np.zeros((10,10,3),np.uint8),depth)


def test_geo56_01_invalid_sentinel_and_isolated_depth_spike_removed():
    d=np.full((9,9),1000,np.uint16)
    d[1,1]=65535;d[4,4]=3300
    f=frame(d)
    original=f.depth_u16.copy()
    off=LiveGeometryService.process(f,camera_generation=1,denoise_mode='off')
    std=LiveGeometryService.process(f,camera_generation=1,denoise_mode='standard')
    assert off.statistics.output_points==80
    assert std.statistics.output_points==79
    assert std.statistics.filtered_outliers==1
    assert std.statistics.missing_depth==1
    assert (4,4) not in {tuple(x) for x in std.depth_source_uv}
    np.testing.assert_array_equal(f.depth_u16,original)
    assert not std.points_xyz_m.flags.writeable


def test_geo56_02_edge_aware_preserves_two_real_surfaces():
    d=np.full((10,12),900,np.uint16)
    d[:,6:]=1300
    support=local_depth_support_mask(d,.001)
    assert support.all()  # both coherent surfaces, sharp jump untouched
    cloud=LiveGeometryService.process(frame(d),camera_generation=2,denoise_mode='standard')
    assert cloud.statistics.output_points==120
    assert cloud.statistics.filtered_outliers==0


def test_geo56_03_low_resolution_and_roi_lineage_backward_compatible():
    d=np.full((2,3),900,np.uint16)
    baseline=LiveGeometryService.process(frame(d),camera_generation=3)
    assert baseline.statistics.output_points==6
    std=LiveGeometryService.process(frame(d),camera_generation=3,denoise_mode='standard',depth_roi=(1,0,2,2))
    assert std.statistics.output_points==4
    np.testing.assert_array_equal(std.depth_source_uv,[[1,0],[2,0],[1,1],[2,1]])


def test_geo56_04_reject_unknown_modes_and_all_invalid_depth():
    with pytest.raises(LiveGeometryError,match='Expected off or standard'):
        LiveGeometryService.process(frame(np.full((9,9),900,np.uint16)),camera_generation=1,denoise_mode='magic')
    d=np.full((9,9),65535,np.uint16)
    with pytest.raises(LiveGeometryError) as e:
        LiveGeometryService.process(frame(d),camera_generation=1)
    assert e.value.code=='EMPTY_VALID_DEPTH'


def test_geo56_05_bounded_sample_after_filter_and_correct_stats():
    d=np.full((30,30),1000,np.uint16)
    cloud=LiveGeometryService.process(frame(d),camera_generation=2,point_budget=60,denoise_mode='standard')
    assert cloud.statistics.output_points==60
    assert cloud.statistics.valid_before_sampling==900
    assert cloud.statistics.skipped_for_sampling==840
    assert cloud.statistics.filtered_outliers==0
