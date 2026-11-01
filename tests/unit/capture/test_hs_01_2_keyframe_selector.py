"""HS-01.2 state-machine tests: synthetic live frames, no RAW/Qt/OrbbecSDK."""
from dataclasses import replace

import pytest

from scantopath.modules.capture.application.keyframe_selector import KeyframeSelector
from scantopath.modules.capture.application.keyframe_selection_models import (
    KeyframeDecision, KeyframeSelectionConfig, SelectionReason,
)
from tests.unit.capture.test_hs_01_2_frame_quality import frame, roi


def evaluate(s, idx, depth=1000, target=None):
    f = frame(idx=idx, depth_value=depth)
    return s.evaluate(f, roi(f) if target is None else target)


def initial(s):
    assert evaluate(s, 1).reason_code == SelectionReason.STABILIZING
    r = evaluate(s, 2)
    assert r.decision is KeyframeDecision.SELECT
    assert r.reason_code is SelectionReason.SELECT_FIRST
    assert s.capture_pending
    return r


def test_select_first_only_after_stabilizing_and_latch_pending():
    s = KeyframeSelector()
    r = initial(s)
    assert r.should_capture
    p = evaluate(s, 3)
    assert p.decision is KeyframeDecision.WAIT
    assert p.reason_code is SelectionReason.CAPTURE_PENDING
    s.capture_completed(True)
    assert not s.capture_pending


def test_saved_ack_is_required_for_duplicate_suppression():
    s = KeyframeSelector(config=KeyframeSelectionConfig(cooldown_us=0))
    initial(s)
    s.capture_completed(True)
    r = evaluate(s, 3)
    assert r.decision is KeyframeDecision.WAIT
    assert r.reason_code is SelectionReason.DUPLICATE_VIEW_PROXY
    assert r.novelty_score == 0


def test_select_novel_after_cooldown_and_stable_motion():
    s = KeyframeSelector()
    initial(s)
    s.capture_completed(True)
    c = evaluate(s, 3)
    assert c.reason_code is SelectionReason.COOLDOWN
    # 10 * 100 ms elapsed since accepted frame; 4cm change is slow enough.
    d = evaluate(s, 12, 1040)
    assert d.decision is KeyframeDecision.SELECT
    assert d.reason_code is SelectionReason.SELECT_NOVEL
    assert d.novelty_score is not None and d.novelty_score >= .1


def test_reject_high_frame_to_frame_motion():
    s = KeyframeSelector()
    evaluate(s, 1, 1000)
    bad = evaluate(s, 2, 1250)
    assert bad.decision is KeyframeDecision.WAIT
    assert bad.reason_code is SelectionReason.MOTION_TOO_HIGH
    assert not s.capture_pending


def test_capture_failure_does_not_commit_reference():
    s = KeyframeSelector()
    initial(s)
    s.capture_completed(False)
    r = evaluate(s, 3)
    assert r.decision is KeyframeDecision.SELECT
    assert r.reason_code is SelectionReason.SELECT_FIRST


def test_unexpected_ack_is_rejected_and_bad_bool_type_is_rejected():
    s = KeyframeSelector()
    with pytest.raises(RuntimeError, match="no pending"):
        s.capture_completed(True)
    with pytest.raises(TypeError):
        s.capture_completed(1)


def test_reject_stale_indices_and_timestamp_without_mutating_state():
    s = KeyframeSelector()
    evaluate(s, 2)
    r = evaluate(s, 2)
    assert r.decision is KeyframeDecision.REJECT
    assert r.reason_code is SelectionReason.STALE_FRAME
    fresh = evaluate(s, 3)
    assert fresh.decision is KeyframeDecision.SELECT


def test_reset_on_reopen_resets_cooldown_and_drops_pending():
    s = KeyframeSelector()
    initial(s)
    s.reset()
    assert not s.capture_pending
    assert evaluate(s, 1).reason_code is SelectionReason.STABILIZING
    assert evaluate(s, 2).decision is KeyframeDecision.SELECT


def test_missing_roi_waits_and_does_not_choose_background():
    s = KeyframeSelector()
    f = frame(idx=1)
    r = s.evaluate(f, None)
    assert r.decision is KeyframeDecision.WAIT
    assert r.reason_code is SelectionReason.ROI_REQUIRED


def test_invalid_depth_rejects_and_requires_re_stabilization():
    s = KeyframeSelector()
    f = frame(idx=1, depth_value=0)
    r = s.evaluate(f, roi(f))
    assert r.decision is KeyframeDecision.REJECT
    assert r.reason_code is SelectionReason.INSUFFICIENT_DEPTH
    assert evaluate(s, 2).reason_code is SelectionReason.STABILIZING


def test_config_guardrails():
    with pytest.raises(ValueError):
        KeyframeSelectionConfig(cooldown_us=-1)
    with pytest.raises(ValueError):
        KeyframeSelectionConfig(min_novelty_score=0)


def test_provisional_reference_is_not_camera_pose_or_raw_capture():
    s = KeyframeSelector()
    r = initial(s)
    assert not hasattr(r, "capture_id")
    assert not hasattr(r, "camera_pose")
    assert not hasattr(r, "registration_fitness")
