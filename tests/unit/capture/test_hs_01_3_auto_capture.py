"""HS-01.3 pure state-machine tests; no camera, Qt or SQLite."""
from __future__ import annotations

from dataclasses import replace

import pytest

from scantopath.modules.capture.application.auto_capture_session import (
    AutoCaptureSession, AutoCaptureState,
)
from scantopath.modules.capture.application.contracts import CaptureContext
from scantopath.modules.capture.domain.models import DepthRoi, RoiSource
from scantopath.modules.capture.application.keyframe_selection_models import (
    KeyframeDecision, SelectionReason,
)
from tests.unit.capture.test_hs_01_2_frame_quality import frame, roi


CTX = CaptureContext("/isolated-test-store", "project_a", "specimen_a", "session_a")


def assess(s, idx: int, depth: int = 1000, target=None):
    f = frame(idx, depth)
    return s.observe(f, roi(f) if target is None else target)


def select_first(s):
    assert assess(s, 1).reason_code is SelectionReason.STABILIZING
    decision = assess(s, 2)
    assert decision.decision is KeyframeDecision.SELECT
    return decision


def test_start_requires_captureless_context_and_resets_state():
    s = AutoCaptureSession()
    assert s.snapshot().state is AutoCaptureState.IDLE
    with pytest.raises(ValueError):
        s.start(replace(CTX, capture_id="capture_x"))
    s.start(CTX)
    assert s.state is AutoCaptureState.SCANNING
    with pytest.raises(RuntimeError, match="BUSY"):
        s.start(CTX)
    s.stop()
    s.start(replace(CTX, session_id="session_b"))
    assert s.context.session_id == "session_b"
    assert s.snapshot().evaluated == 0


def test_first_proposal_not_a_saved_capture():
    s = AutoCaptureSession()
    s.start(CTX)
    select_first(s)
    snap = s.snapshot()
    assert snap.proposals == 1 and snap.saved == 0
    assert snap.pending and snap.state is AutoCaptureState.CAPTURING
    assert s.observe(frame(3), roi(frame(3))) is None


def test_success_requires_verified_receipt_and_suppresses_duplicates():
    s = AutoCaptureSession()
    s.start(CTX)
    select_first(s)
    s.mark_saved("capture_1")
    assert s.snapshot().capture_ids == ("capture_1",)
    assert s.state is AutoCaptureState.SCANNING
    assert assess(s, 3).reason_code is SelectionReason.COOLDOWN
    assert assess(s, 15).reason_code is SelectionReason.DUPLICATE_VIEW_PROXY
    assert s.snapshot().saved == 1


def test_novel_view_accept_and_unique_ids():
    s = AutoCaptureSession()
    s.start(CTX)
    select_first(s)
    s.mark_saved("capture_1")
    assert assess(s, 12, 1040).decision is KeyframeDecision.SELECT
    with pytest.raises(ValueError, match="unique"):
        s.mark_saved("capture_1")
    assert s.pending
    s.mark_saved("capture_2")
    snap = s.snapshot()
    assert snap.saved == 2 and snap.capture_ids == ("capture_1", "capture_2")


def test_failed_commit_is_not_success_and_keeps_reference():
    s = AutoCaptureSession()
    s.start(CTX)
    select_first(s)
    s.mark_failed("RAW_WRITE_FAILED")
    assert s.snapshot().failures == 1
    assert s.snapshot().saved == 0
    assert s.state is AutoCaptureState.SCANNING
    assert assess(s, 3).decision is KeyframeDecision.SELECT
    s.mark_saved("capture_real")
    assert s.snapshot().saved == 1


def test_stop_before_capture_is_terminal_and_no_auto_capture():
    s = AutoCaptureSession()
    s.start(CTX)
    s.stop()
    assert s.state is AutoCaptureState.STOPPED
    assert s.observe(frame(1), roi(frame(1))) is None
    s.stop()  # idempotent


def test_stop_during_capture_waits_for_verified_commit():
    s = AutoCaptureSession()
    s.start(CTX)
    select_first(s)
    s.stop("OPERATOR_STOP")
    assert s.state is AutoCaptureState.STOPPING
    assert not s.can_accept_frames
    s.mark_saved("capture_saved_before_stop")
    assert s.state is AutoCaptureState.STOPPED
    assert s.snapshot().saved == 1
    assert s.observe(frame(3), roi(frame(3))) is None


def test_stop_during_capture_then_failure_is_not_saved():
    s = AutoCaptureSession()
    s.start(CTX)
    select_first(s)
    s.stop("CAMERA_STOPPED")
    s.mark_failed("DEVICE_PROCESS_CRASH")
    assert s.state is AutoCaptureState.STOPPED
    assert s.snapshot().failures == 1
    assert s.snapshot().saved == 0


def test_roi_source_switch_resets_novelty_reference_without_touching_raw():
    s = AutoCaptureSession()
    s.start(CTX)
    first = frame(1)
    second = frame(2)
    suggestion = replace(roi(first), source=RoiSource.DEPTH_SUGGESTION)
    assert s.observe(first, suggestion).reason_code is SelectionReason.STABILIZING
    assert s.observe(second, suggestion).should_capture
    s.mark_saved("raw_1")
    f = frame(12, depth_value=1040)
    manual = replace(roi(f), source=RoiSource.MANUAL)
    assert s.observe(f, manual).reason_code is SelectionReason.STABILIZING
    assert assess(s, 13, 1040, manual).decision is KeyframeDecision.SELECT
    assert s.snapshot().saved == 1


def test_roi_reference_reset_deferred_while_capture_pending():
    s = AutoCaptureSession()
    s.start(CTX)
    select_first(s)
    s.invalidate_view_reference()
    assert s.pending
    s.mark_saved("raw_1")
    assert assess(s, 3).reason_code is SelectionReason.STABILIZING


def test_missing_roi_never_proposes_capture():
    s = AutoCaptureSession()
    s.start(CTX)
    x = s.observe(frame(1), None)
    assert x.decision is KeyframeDecision.WAIT
    assert x.reason_code is SelectionReason.ROI_REQUIRED
    assert s.snapshot().proposals == 0


def test_empty_or_invalid_failure_and_unexpected_receipts_are_rejected():
    s = AutoCaptureSession()
    s.start(CTX)
    with pytest.raises(RuntimeError):
        s.mark_saved("capture")
    with pytest.raises(RuntimeError):
        s.mark_failed("READ_FAILED")
    select_first(s)
    with pytest.raises(ValueError):
        s.mark_failed("đang lỗi")
    assert s.pending
    s.mark_failed("CAPTURE_TIMEOUT")
    assert not s.pending


def test_stale_preview_rejected_and_does_not_increase_proposals():
    s = AutoCaptureSession()
    s.start(CTX)
    assess(s, 1)
    result = assess(s, 1)
    assert result.reason_code is SelectionReason.STALE_FRAME
    assert s.snapshot().proposals == 0


def test_session_reopen_discards_old_reference_and_counters():
    s = AutoCaptureSession()
    s.start(CTX)
    select_first(s)
    s.mark_saved("old_capture")
    s.stop()
    s.start(CTX)
    assert s.snapshot().capture_ids == ()
    assert assess(s, 1).reason_code is SelectionReason.STABILIZING


def test_same_source_moving_roi_does_not_force_full_reset():
    s = AutoCaptureSession()
    s.start(CTX)
    first = frame(1)
    assert s.observe(first, replace(roi(first), source=RoiSource.DEPTH_SUGGESTION))
    f = frame(2)
    shifted = DepthRoi(2, 0, 62, 48, 64, 48, RoiSource.MANUAL)
    assert s.observe(f, shifted).decision is KeyframeDecision.WAIT  # new source -> stabilize
    next_frame = frame(3)
    assert s.observe(next_frame, shifted).decision is KeyframeDecision.SELECT
    s.mark_failed("CAPTURE_TIMEOUT")
    shifted_again = DepthRoi(3, 0, 61, 48, 64, 48, RoiSource.MANUAL)
    assert s.observe(frame(4), shifted_again).decision is KeyframeDecision.SELECT
