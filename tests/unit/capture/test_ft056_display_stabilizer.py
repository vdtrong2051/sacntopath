"""FT-05.6 pure display ROI tests: no hardware, no Qt, no RAW changes."""
from types import SimpleNamespace as NS
from scantopath.modules.capture.application.live_display_stabilizer import DepthDisplayStabilizer
from scantopath.modules.capture.domain.models import DepthRoi, RoiSource


def observation(x=100, y=70, w=150, h=120, usable=True):
    roi = DepthRoi(x,y,w,h,640,480,RoiSource.DEPTH_SUGGESTION)
    return NS(roi=roi,usable=usable)


def test_display_01_jitter_reduced_and_original_result_untouched():
    stabilizer=DepthDisplayStabilizer()
    sequence=[100,105,95,104,96,103,97,101,99]
    snapshots=[]
    for i,x in enumerate(sequence):
        source=observation(x=x,w=150+((-1)**i)*4)
        before=(source.roi.x,source.roi.width)
        output=stabilizer.update(i,source)
        assert (source.roi.x,source.roi.width)==before
        snapshots.append((output.x,output.width))
    assert max(v[0] for v in snapshots) - min(v[0] for v in snapshots) < 10
    assert max(v[1] for v in snapshots) - min(v[1] for v in snapshots) < 8


def test_display_02_holds_for_two_missing_frames_only_then_clears():
    stabilizer=DepthDisplayStabilizer()
    initial=stabilizer.update(1,observation())
    assert stabilizer.update(2,observation(usable=False))==initial
    assert stabilizer.update(3,None)==initial
    assert stabilizer.update(4,None) is None


def test_display_03_idempotent_by_frame_and_reset_on_new_generation():
    stabilizer=DepthDisplayStabilizer()
    first=stabilizer.update(10,observation())
    assert stabilizer.update(10,observation(x=350))==first
    assert stabilizer.update(9,observation(x=350))==first
    stabilizer.reset()
    assert stabilizer.update(1,observation(x=300)).x==300


def test_display_04_real_motion_can_follow_without_forced_camera_recenter():
    stabilizer=DepthDisplayStabilizer()
    last=stabilizer.update(1,observation(x=100))
    for i in range(2,22):
        last=stabilizer.update(i,observation(x=130))
    assert 115<=last.x<=132
    assert last.source is RoiSource.DEPTH_SUGGESTION
