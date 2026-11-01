"""HS-01.4: deterministic guard tests, no camera or SQLite."""
from __future__ import annotations

import numpy as np
import pytest

from scantopath.modules.capture.application.roi_safety import (
    RoiSafetyConfig, RoiSafetyEvaluator, RoiSafetyReason,
)
from scantopath.modules.capture.domain.models import DepthRoi, RoiSource
from tests.unit.capture.test_hs_01_2_frame_quality import frame


def box(f, *, x=10, y=8, width=42, height=30, src=RoiSource.MANUAL):
    return DepthRoi(x,y,width,height,f.source.depth_width,f.source.depth_height,src)


def test_missing_roi_fails_closed():
    r=RoiSafetyEvaluator().evaluate(frame(),None)
    assert not r.safe_to_propose and r.reason is RoiSafetyReason.ROI_REQUIRED


def test_manual_narrow_roi_allows_and_is_only_proxy():
    f=frame()
    before=f.depth_u16.copy()
    result=RoiSafetyEvaluator().evaluate(f,box(f))
    assert result.safe_to_propose and result.reason is RoiSafetyReason.OK_MANUAL
    assert result.source=='manual' and result.valid_fraction==1
    assert result.median_depth_m==pytest.approx(1.0)
    assert np.array_equal(before,f.depth_u16)


def test_suggested_reason_not_object_mask():
    f=frame()
    result=RoiSafetyEvaluator().evaluate(f,box(f,src=RoiSource.DEPTH_SUGGESTION))
    assert result.safe_to_propose and result.reason is RoiSafetyReason.OK_SUGGESTED


def test_auto_bbox_84_percent_width_is_blocked():
    # Mimics the field observation (201,582,1079,214) in 1280x800.
    f=frame(size=(800,1280))
    r=DepthRoi(201,582,1079,214,1280,800,RoiSource.DEPTH_SUGGESTION)
    out=RoiSafetyEvaluator().evaluate(f,r)
    assert not out.safe_to_propose
    assert out.reason is RoiSafetyReason.ROI_TOO_WIDE
    assert out.width_fraction==pytest.approx(1079/1280)


def test_large_full_frame_manual_roi_blocked():
    f=frame()
    out=RoiSafetyEvaluator().evaluate(f,DepthRoi(0,0,64,48,64,48))
    assert not out.safe_to_propose and out.reason is RoiSafetyReason.ROI_TOO_WIDE


def test_small_roi_blocked():
    f=frame()
    out=RoiSafetyEvaluator().evaluate(f,box(f,width=10,height=8))
    assert out.reason is RoiSafetyReason.ROI_TOO_SMALL


def test_depth_grid_mismatch_blocked():
    f=frame()
    r=DepthRoi(10,10,20,20,1280,800)
    assert RoiSafetyEvaluator().evaluate(f,r).reason is RoiSafetyReason.ROI_GRID_MISMATCH


def test_border_contact_blocked():
    f=frame()
    assert RoiSafetyEvaluator().evaluate(f,box(f,x=0,width=36)).reason is RoiSafetyReason.ROI_NEAR_BORDER


def test_invalid_depth_missing_rejected():
    f=frame(depth_value=0)
    assert RoiSafetyEvaluator().evaluate(f,box(f)).reason is RoiSafetyReason.ROI_DEPTH_INSUFFICIENT


def test_15cm_distance_refused():
    f=frame(depth_value=150)
    assert RoiSafetyEvaluator().evaluate(f,box(f)).reason is RoiSafetyReason.DEPTH_TOO_NEAR


def test_exact_20cm_is_allowed_when_valid():
    f=frame(depth_value=200)
    assert RoiSafetyEvaluator().evaluate(f,box(f)).safe_to_propose


def test_far_out_of_range_blocked():
    f=frame(depth_value=4000)
    assert RoiSafetyEvaluator().evaluate(f,box(f)).reason is RoiSafetyReason.DEPTH_TOO_FAR


def test_sparse_depth_insufficient():
    f=frame()
    f.depth_u16[8:38,10:52]=0
    f.depth_u16[9,11]=1000
    assert RoiSafetyEvaluator().evaluate(f,box(f)).reason is RoiSafetyReason.ROI_DEPTH_INSUFFICIENT


def test_foreground_too_near_blocks_even_if_background_present():
    f=frame()
    f.depth_u16[8:23,10:52]=150
    assert RoiSafetyEvaluator().evaluate(f,box(f)).reason is RoiSafetyReason.DEPTH_TOO_NEAR


def test_config_validation_and_nonfinite_depth_scale():
    for kw in ({'max_width_fraction':1.1},{'min_depth_m':-1},
               {'sample_grid':2},{'max_area_fraction':float('nan')},
               {'min_valid_samples':1000}):
        with pytest.raises(ValueError):
            RoiSafetyConfig(**kw)
    f=frame();f.source.depth_scale_m_per_unit=float('nan')
    assert RoiSafetyEvaluator().evaluate(f,box(f)).reason is RoiSafetyReason.FRAME_INVALID


def test_guard_state_blocks_proposal_without_fake_failure():
    from scantopath.modules.capture.application.auto_capture_session import AutoCaptureSession
    from scantopath.modules.capture.application.contracts import CaptureContext
    s=AutoCaptureSession();s.start(CaptureContext('store','project','specimen','session'))
    s.reject_roi_guard('ROI_TOO_WIDE')
    snapshot=s.snapshot()
    assert snapshot.evaluated==1 and snapshot.proposals==0
    assert snapshot.failures==0 and snapshot.saved==0
    assert snapshot.last_reason=='ROI_TOO_WIDE'
    assert not snapshot.pending and s.can_accept_frames
