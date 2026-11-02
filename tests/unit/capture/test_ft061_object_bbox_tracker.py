from __future__ import annotations
import numpy as np
import pytest
from scantopath.modules.capture.application.live_object_bbox_tracker import LiveObjectBoundingTracker


def uv(*points):
    return np.asarray(points, dtype=np.int32)


def test_bbox_derived_from_measured_uv_and_compact_not_full_auto_roi():
    t=LiveObjectBoundingTracker()
    x=t.observe(generation=1, frame_index=100, uv=uv((586,458),(735,590),(610,530)),
                depth_width=1280, depth_height=800, corner_count=23, now=10.)
    assert x.status=='TRACKING' and x.observed
    assert x.rect_xywh[0]>500 and x.rect_xywh[1]>400
    assert x.rect_xywh[2]<230 and x.rect_xywh[3]<220


def test_low_corner_valid_observation_is_degraded_not_untrusted_fabrication():
    t=LiveObjectBoundingTracker()
    a=t.observe(generation=1,frame_index=1,uv=uv((10,10),(40,50)),
        depth_width=1280,depth_height=800,corner_count=7,now=20)
    assert a.status=='DEGRADED' and a.observed
    b=t.current(now=20.8)
    assert b.status=='TEMPORARILY_LOST' and not b.observed
    assert b.rect_xywh is not None
    assert t.current(now=22).rect_xywh is None


def test_new_generation_disposes_history_and_prevents_stale_rect():
    t=LiveObjectBoundingTracker()
    t.observe(generation=1,frame_index=7,uv=uv((50,50),(60,60)),
              depth_width=200,depth_height=100,now=1)
    b=t.observe(generation=2,frame_index=1,uv=uv((100,50),(110,60)),
              depth_width=200,depth_height=100,now=2)
    assert b.rect_xywh[0]>=90
    with pytest.raises(ValueError,match='STALE_FRAME'):
        t.observe(generation=2,frame_index=1,uv=uv((100,50)),depth_width=200,
                  depth_height=100,now=3)


def test_no_mask_invention_or_tracking_from_empty_invalid_uv():
    t=LiveObjectBoundingTracker()
    with pytest.raises(ValueError,match='FRAME_INVALID'):
        t.observe(generation=1,frame_index=1,uv=np.zeros((0,2),dtype=np.int32),
                  depth_width=1280,depth_height=800)
    with pytest.raises(ValueError,match='UV_INVALID'):
        t.observe(generation=1,frame_index=2,uv=uv((1281,0)),
                  depth_width=1280,depth_height=800)
    assert t.current().rect_xywh is None


def test_lost_then_reacquire_at_new_location_not_hold_as_new_observation():
    t=LiveObjectBoundingTracker(max_jump_fraction=.15)
    t.observe(generation=1,frame_index=1,uv=uv((10,10),(20,20)),
              depth_width=200,depth_height=100,now=10)
    old=t.missed(now=10.2)
    assert not old.observed and old.status=='TEMPORARILY_LOST'
    new=t.observe(generation=1,frame_index=2,uv=uv((150,60),(160,70)),
                  depth_width=200,depth_height=100,now=10.3)
    assert new.status=='REACQUIRING' and new.observed
