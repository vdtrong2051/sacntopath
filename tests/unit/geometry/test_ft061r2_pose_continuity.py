"""FT-06.1 R2: synthetic feature-following PnP. Never requires real camera."""
from types import SimpleNamespace as NS
import cv2
import numpy as np
from scantopath.modules.geometry.application import live_charuco_pose_tracker as m
from scantopath.modules.geometry.application.live_charuco_isolation import CharucoIsolationResult


def fixture():
    h, w = 600, 800
    gray = np.full((h, w), 32, np.uint8)
    obj = np.array([(x * .045, y * .045, 0.) for y in range(5) for x in range(5)], np.float32)
    intr = NS(fx=820., fy=820., cx=400., cy=300., width=w, height=h)
    calib = NS(color_intrinsics=intr,
               color_distortion=NS(sdk_model=0, k1_k6_p1_p2=(0.,)*8),
               fingerprint='synthetic-calibration')
    k = np.array([[820.,0.,400.],[0.,820.,300.],[0.,0.,1.]],np.float64)
    R = np.eye(3)
    t = np.array([-.09,-.09,.9])
    uv,_=cv2.projectPoints(obj, np.zeros(3), t, k, np.zeros(8))
    uv=uv.reshape(-1,2).astype(np.float32)
    # Make textured, locatable corners; no need to emulate the full marker board.
    rng=np.random.default_rng(42)
    for x,y in uv:
        xx,yy=round(float(x)),round(float(y))
        patch=rng.integers(20,230,(13,13),dtype=np.uint8)
        gray[yy-6:yy+7,xx-6:xx+7]=patch
    return np.stack([gray]*3,axis=-1),uv,obj,R,t,calib


def test_short_optical_flow_bridge_is_recomputed_not_reused(monkeypatch):
    rgb,uv,obj,R,t,calib=fixture()
    calls=[0]
    def detector(color, calibration, cfg, *, feature_sink=None):
        calls[0]+=1
        if calls[0]==1:
            feature_sink['image_points']=uv.reshape(-1,1,2)
            feature_sink['object_points']=obj
            return R,t,18,len(obj),.3
        return CharucoIsolationResult('CHARUCO_INSUFFICIENT_CORNERS',None,0,0,None,0.,0,'lost')
    monkeypatch.setattr(m,'detect_charuco_pose', detector)
    track=m.TemporalCharucoPoseTracker()
    direct, source, age=track.estimate(rgb,calib,None,timestamp_us=100000)
    assert source=='detected' and age==0
    warp=cv2.warpAffine(rgb,np.float32([[1,0,3],[0,1,2]]),(800,600),borderValue=(32,32,32))
    follow,source,age=track.estimate(warp,calib,None,timestamp_us=200000)
    assert source=='optical_flow_estimate' and age==1
    assert isinstance(follow,tuple) and len(follow)==5 and follow[3]>=7
    assert np.linalg.norm(follow[1]-t)>.00001  # new pose from optical movement
    assert follow[-1] < 2.0


def test_gap_limit_drops_old_pose(monkeypatch):
    rgb,uv,obj,R,t,calib=fixture()
    calls=[0]
    def detector(color, calibration, cfg, *, feature_sink=None):
        calls[0]+=1
        if calls[0]==1:
            feature_sink.update(image_points=uv.reshape(-1,1,2),object_points=obj)
            return R,t,18,len(obj),.3
        return CharucoIsolationResult('CHARUCO_INSUFFICIENT_CORNERS',None,0,0,None,0.,0,'lost')
    monkeypatch.setattr(m,'detect_charuco_pose', detector)
    track=m.TemporalCharucoPoseTracker()
    track.estimate(rgb,calib,None,timestamp_us=100000)
    res,method,age=track.estimate(rgb,calib,None,timestamp_us=900001)
    assert method=='none' and age==0 and isinstance(res,CharucoIsolationResult)


def test_calibration_change_disallows_reuse(monkeypatch):
    rgb,uv,obj,R,t,calib=fixture()
    calls=[0]
    def detector(color, calibration, cfg, *, feature_sink=None):
        calls[0]+=1
        if calls[0]==1:
            feature_sink.update(image_points=uv.reshape(-1,1,2),object_points=obj)
            return R,t,18,len(obj),.3
        return CharucoIsolationResult('CHARUCO_POSE_FAILED',None,0,0,None,0.,0,'lost')
    monkeypatch.setattr(m,'detect_charuco_pose', detector)
    track=m.TemporalCharucoPoseTracker()
    track.estimate(rgb,calib,None,timestamp_us=100000)
    calib.fingerprint='different calibration'
    _,method,_=track.estimate(rgb,calib,None,timestamp_us=150000)
    assert method=='none'


def test_repeated_failure_expires_within_five_frames(monkeypatch):
    rgb,uv,obj,R,t,calib=fixture()
    calls=[0]
    def detector(color,calibration,cfg,*,feature_sink=None):
        calls[0]+=1
        if calls[0]==1:
            feature_sink.update(image_points=uv.reshape(-1,1,2),object_points=obj)
            return R,t,18,len(obj),.3
        return CharucoIsolationResult('CHARUCO_POSE_FAILED',None,0,0,None,0.,0,'lost')
    monkeypatch.setattr(m,'detect_charuco_pose', detector)
    track=m.TemporalCharucoPoseTracker()
    track.estimate(rgb,calib,None,timestamp_us=100000)
    sources=[]
    for i in range(1,7):
        _,source,_=track.estimate(rgb,calib,None,timestamp_us=100000+int(i*60000))
        sources.append(source)
    assert sources[-1]=='none'


def test_no_unanchored_flow_when_image_is_blank(monkeypatch):
    rgb,uv,obj,R,t,calib=fixture()
    calls=[0]
    def detector(color, calibration, cfg, *, feature_sink=None):
        calls[0]+=1
        if calls[0]==1:
            feature_sink.update(image_points=uv.reshape(-1,1,2), object_points=obj)
            return R,t,18,len(obj),.3
        return CharucoIsolationResult('CHARUCO_INSUFFICIENT_CORNERS',None,0,0,None,0.,0,'lost')
    monkeypatch.setattr(m,'detect_charuco_pose', detector)
    track=m.TemporalCharucoPoseTracker()
    track.estimate(rgb,calib,None,timestamp_us=100000)
    blank=np.zeros_like(rgb)
    _,source,_=track.estimate(blank,calib,None,timestamp_us=150000)
    assert source=='none'  # black image must NOT authorize stale geometry


def test_time_limit_measured_from_last_confirmed_board_detection(monkeypatch):
    rgb,uv,obj,R,t,calib=fixture()
    calls=[0]
    def detector(color,calibration,cfg,*,feature_sink=None):
        calls[0]+=1
        if calls[0]==1:
            feature_sink.update(image_points=uv.reshape(-1,1,2),object_points=obj)
            return R,t,18,len(obj),.3
        return CharucoIsolationResult('CHARUCO_INSUFFICIENT_CORNERS',None,0,0,None,0.,0,'lost')
    monkeypatch.setattr(m,'detect_charuco_pose', detector)
    track=m.TemporalCharucoPoseTracker(m.ContinuityPolicy(max_bridged_frames=20))
    track.estimate(rgb,calib,None,timestamp_us=100000)
    _,source,_=track.estimate(rgb,calib,None,timestamp_us=450000)
    assert source=='optical_flow_estimate'
    # Both adjacent samples are <600 ms apart, but real detection is >600ms old.
    _,source,_=track.estimate(rgb,calib,None,timestamp_us=710000)
    assert source=='none'
