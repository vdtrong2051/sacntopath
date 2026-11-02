"""Targeted FT-08 B-01 tests: reuse existing FT-05.8/05.7 Depth masks."""
from __future__ import annotations
from types import ModuleType, SimpleNamespace as NS
import sys
import numpy as np
import pytest
from scantopath.modules.reconstruction.application import live_pair
from scantopath.modules.reconstruction.application.contracts import RegistrationError


def _install_modules(monkeypatch, *, usable=True, grid=10):
    """Provide controlled ports; production imports reference REAL FT-05.8/FT-05.7 modules."""
    for prefix in ('scantopath.modules.capture', 'scantopath.modules.capture.application',
                   'scantopath.modules.capture.infrastructure', 'scantopath.modules.geometry',
                   'scantopath.modules.geometry.application'):
        m = ModuleType(prefix); m.__path__ = []
        monkeypatch.setitem(sys.modules, prefix, m)
    def install(name, **attrs):
        m = ModuleType(name)
        for k,v in attrs.items(): setattr(m,k,v)
        monkeypatch.setitem(sys.modules, name, m)
    class FakeDecoded:
        color_rgb = np.zeros((grid,grid,3),dtype=np.uint8)
        depth_u16 = np.ones((grid,grid),dtype=np.uint16)*800
    class FakeDecoder:
        def __init__(self, codec): pass
        def decode(self, packet): return FakeDecoded()
    class FakeCodec: pass
    class FakeGeometry:
        @staticmethod
        def process(**kw):
            uv = np.column_stack((np.tile(np.arange(grid,dtype=np.int32),grid),
                                  np.repeat(np.arange(grid,dtype=np.int32),grid)))
            xyz = np.column_stack((uv[:,0] *.001, uv[:,1]*.001, np.ones(grid*grid)*.8))
            return NS(points_xyz_m=xyz, depth_source_uv=uv,
                      calibration_fingerprint='a'*64)
    install('scantopath.modules.capture.application.decoding',RgbdDecoder=FakeDecoder)
    install('scantopath.modules.capture.infrastructure.jpeg_codec',PillowMjpegDecoder=FakeCodec)
    install('scantopath.modules.geometry.application.service',GeometryService=FakeGeometry)
    class C:
        def __init__(self,*args,**kwargs):
            for k,v in kwargs.items(): setattr(self,k,v)
            if len(args)==2: self.sdk_model,self.k1_k6_p1_p2=args
            if len(args)==6: (self.width,self.height,self.fx,self.fy,self.cx,self.cy)=args
        fingerprint='f'*64
    install('scantopath.modules.capture.application.live_calibration',
            LiveCalibrationSnapshot=C,LiveDistortion=C,LiveIntrinsics=C)
    counter={}
    def detection(*args,**kwargs):
        counter['detect']=counter.get('detect',0)+1
        return np.eye(3), np.array([0.,0.,.8]), 20, 17, .42
    def charuco(*args,depth_roi=None,pose_provider=None,timestamp_us=None,**kwargs):
        counter['mask_called']=counter.get('mask_called',0)+1
        assert depth_roi == (0,0,grid,grid)
        pose_provider(args[0],args[2],None,timestamp_us=timestamp_us)
        mask=np.zeros((grid,grid),dtype=bool)
        mask[0:grid//2,:]=True
        return NS(usable=usable, object_mask=mask if usable else None,
                  status='CHARUCO_OBJECT_FOUND' if usable else 'CHARUCO_DEPTH_PLANE_UNVERIFIED',
                  selected_pixels=grid*grid//2,corner_count=17,reprojection_px=.42,support_fraction=.65)
    install('scantopath.modules.geometry.application.live_charuco_isolation',
            isolate_charuco_object=charuco,detect_charuco_pose=detection)
    def depth(*args,**kwargs):
        counter['depth_called']=True
        mask=np.zeros((grid,grid),dtype=bool);mask[grid//2:,:]=True
        return NS(usable=usable,object_mask=mask if usable else None,
                  status='OBJECT_FOUND' if usable else 'ISOLATION_NO_OBJECT',selected_pixels=grid*grid//2)
    install('scantopath.modules.geometry.application.live_object_isolation',
            isolate_object_depth=depth)
    return counter


def pkt(name='a',grid=10):
    k=NS(width=grid,height=grid,fx=500.,fy=500.,cx=5.,cy=5.)
    d=NS(sdk_model=0,k1_k6_p1_p2=(0,)*8)
    m=NS(capture_id=name,session_id='test',specimen_id='obj',kind='ORBBEC',measured=True,
          color=NS(width=grid,height=grid,frame_index=4,timestamp_us=1234),
          depth=NS(width=grid,height=grid,frame_index=4,timestamp_us=1234),
          depth_intrinsics=k,color_intrinsics=k,depth_distortion=d,color_distortion=d,
          depth_to_color=NS(rotation=tuple(np.eye(3).ravel()),translation_mm=(13.,0.,0.)),
          depth_scale_m_per_unit=.001,device=NS(name='Gemini',pid=1),alignment_mode='disabled',
          timestamp_domain='sdk_reported_unverified')
    return NS(metadata=m,color_mjpeg=b'jpeg',depth_y16_le=b'depth')


def test_charuco_calls_existing_detector_and_filters_in_depth_grid(monkeypatch):
    counter=_install_modules(monkeypatch)
    monkeypatch.setattr(live_pair,'RawRgbdCapture',NS)
    with pytest.raises(RegistrationError,match='fewer than 350'):
        live_pair.cloud_from_live_packet(pkt(),roi=None,min_depth_m=.3,
                                        max_depth_m=1.2,reference_mode='charuco')
    assert counter.get('mask_called')==1 and counter.get('detect')==1


def test_charuco_fails_closed(monkeypatch):
    _install_modules(monkeypatch,usable=False)
    monkeypatch.setattr(live_pair,'RawRgbdCapture',NS)
    with pytest.raises(RegistrationError) as x:
        live_pair.cloud_from_live_packet(pkt(),roi=None,min_depth_m=.3,
                                        max_depth_m=1.2,reference_mode='charuco')
    assert x.value.code == 'CHARUCO_DEPTH_PLANE_UNVERIFIED'


def test_depth_fallback_requires_explicit_reference(monkeypatch):
    counter=_install_modules(monkeypatch)
    monkeypatch.setattr(live_pair,'RawRgbdCapture',NS)
    with pytest.raises(RegistrationError,match='fewer than 350'):
        live_pair.cloud_from_live_packet(pkt(),roi=None,min_depth_m=.3,
                                        max_depth_m=1.2,reference_mode='depth')
    assert counter.get('depth_called') and not counter.get('detect')


def test_board_pose_seed_direction_depth1_to_depth0():
    a,b=pkt('a').metadata,pkt('b').metadata
    t0=np.eye(4); t1=np.eye(4)
    t0[0,3]=.10; t1[0,3]=.05
    v0=NS(board_pose_C_B=t0);v1=NS(board_pose_C_B=t1)
    actual=live_pair._charuco_initial_depth1_to_depth0(a,b,v0,v1)
    np.testing.assert_allclose(actual[:3,3],[.05,0,0],atol=1e-12)
    np.testing.assert_allclose(actual[:3,:3],np.eye(3),atol=1e-12)


def test_measured_object_uv_mask_is_applied_before_icp(monkeypatch):
    _install_modules(monkeypatch,grid=40)
    monkeypatch.setattr(live_pair,'RawRgbdCapture',NS)
    v = live_pair.cloud_from_live_packet(pkt(grid=40),roi=None,min_depth_m=.3,
                                         max_depth_m=1.2,reference_mode='charuco')
    assert v.selected_points == 800
    assert len(v.cloud.xyz_depth_m) == len(v.cloud.depth_source_uv) == 800
    assert np.max(v.cloud.depth_source_uv[:,1]) == 19
    assert v.source_ref['isolation_source'] == 'FT-05.8_CHARUCO'
    assert v.source_ref['depth_enhancement_mode'] == 'off'
    assert v.board_pose_C_B is not None
