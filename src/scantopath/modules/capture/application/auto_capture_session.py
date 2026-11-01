"""HS-01.3: opt-in automatic keyframe capture lifecycle; no SDK, Qt or I/O.

A preview SELECT is *advisory*. Only the caller's verified RAW-v2 persistence
receipt may acknowledge success. A manual capture is never counted here.
"""
from __future__ import annotations

from dataclasses import dataclass
from enum import Enum

from scantopath.modules.capture.application.contracts import CaptureContext
from scantopath.modules.capture.application.keyframe_selector import KeyframeSelector
from scantopath.modules.capture.domain.models import DepthRoi
from scantopath.modules.capture.application.keyframe_selection_models import (
    KeyframeSelectionResult, KeyframeDecision,
)


class AutoCaptureState(str, Enum):
    IDLE = "IDLE"
    SCANNING = "SCANNING"
    CAPTURING = "CAPTURING"
    STOPPING = "STOPPING"
    STOPPED = "STOPPED"


@dataclass(frozen=True, slots=True)
class AutoCaptureSnapshot:
    state: AutoCaptureState
    evaluated: int
    proposals: int
    saved: int
    failures: int
    last_reason: str
    pending: bool
    capture_ids: tuple[str, ...]


class AutoCaptureSession:
    """Single-owner state machine. Serialize callbacks on the GUI thread.

    Changing the ROI *source* invalidates novelty history. Moving coordinates
    within one tracked ROI are handled inside the HS-01.2 selector itself.
    """

    def __init__(self, selector: KeyframeSelector | None = None) -> None:
        if selector is not None and not isinstance(selector, KeyframeSelector):
            raise TypeError("selector must be KeyframeSelector")
        self.selector = selector if selector is not None else KeyframeSelector()
        self.context: CaptureContext | None = None
        self.state = AutoCaptureState.IDLE
        self.evaluated = 0
        self.proposals = 0
        self.failures = 0
        self._ids: list[str] = []
        self._last_reason = "IDLE"
        self._roi_source: str | None = None
        self._reset_after_receipt = False

    @property
    def pending(self) -> bool:
        return self.selector.capture_pending

    @property
    def can_accept_frames(self) -> bool:
        return self.state is AutoCaptureState.SCANNING and not self.pending

    def start(self, context: CaptureContext) -> None:
        if not isinstance(context, CaptureContext) or context.capture_id is not None:
            raise ValueError("explicit open Scan Session context required")
        if self.state not in (AutoCaptureState.IDLE, AutoCaptureState.STOPPED) or self.pending:
            raise RuntimeError("AUTO_CAPTURE_SESSION_BUSY")
        self.context = context
        self.selector.reset()
        self.state = AutoCaptureState.SCANNING
        self.evaluated = self.proposals = self.failures = 0
        self._ids.clear()
        self._last_reason = "SCANNING"
        self._roi_source = None
        self._reset_after_receipt = False

    def stop(self, reason: str = "STOP_REQUESTED") -> None:
        if self.state in (AutoCaptureState.IDLE, AutoCaptureState.STOPPED):
            return
        self.state = AutoCaptureState.STOPPING if self.pending else AutoCaptureState.STOPPED
        self._last_reason = reason

    def observe(self, frame, roi: DepthRoi | None) -> KeyframeSelectionResult | None:
        if not self.can_accept_frames:
            return None
        source = str(roi.source.value) if roi is not None else None
        if self._roi_source is not None and source is not None and source != self._roi_source:
            self.selector.reset()
        if source is not None:
            self._roi_source = source
        outcome = self.selector.evaluate(frame, roi)
        self.evaluated += 1
        self._last_reason = outcome.reason_code.value
        if outcome.decision is KeyframeDecision.SELECT:
            self.proposals += 1
            self.state = AutoCaptureState.CAPTURING
        return outcome

    def reject_roi_guard(self, reason: str) -> None:
        """Record an evaluated preview rejected by ROI safety, without capture."""
        if not self.can_accept_frames:
            return
        if not isinstance(reason, str) or not reason.isascii() or not reason:
            raise ValueError("stable ROI safety reason required")
        self.evaluated += 1
        self._last_reason = reason
        # A stale reference from a formerly safe ROI must not be reused after
        # the operator adjusts the ROI or moves back into range.
        self.invalidate_view_reference()

    def mark_saved(self, capture_id: str) -> None:
        if not self.pending or self.state not in (AutoCaptureState.CAPTURING, AutoCaptureState.STOPPING):
            raise RuntimeError("NO_PENDING_AUTO_CAPTURE")
        if not isinstance(capture_id, str) or not capture_id or capture_id in self._ids:
            raise ValueError("capture_id must be unique and nonempty")
        self.selector.capture_completed(True)
        self._ids.append(capture_id)
        self.state = (AutoCaptureState.STOPPED if self.state is AutoCaptureState.STOPPING
                      else AutoCaptureState.SCANNING)
        self._last_reason = "RAW_VERIFIED_AND_SAVED"
        if self._reset_after_receipt:
            self.selector.reset()
            self._reset_after_receipt = False

    def mark_failed(self, reason: str) -> None:
        if not isinstance(reason, str) or not reason or not reason.isascii():
            raise ValueError("stable ASCII failure reason required")
        if not self.pending or self.state not in (AutoCaptureState.CAPTURING, AutoCaptureState.STOPPING):
            raise RuntimeError("NO_PENDING_AUTO_CAPTURE")
        self.selector.capture_completed(False)
        self.failures += 1
        self.state = (AutoCaptureState.STOPPED if self.state is AutoCaptureState.STOPPING
                      else AutoCaptureState.SCANNING)
        self._last_reason = reason
        if self._reset_after_receipt:
            self.selector.reset()
            self._reset_after_receipt = False

    def invalidate_view_reference(self) -> None:
        if self.pending:
            self._reset_after_receipt = True
        else:
            self.selector.reset()
        self._roi_source = None

    def snapshot(self) -> AutoCaptureSnapshot:
        return AutoCaptureSnapshot(self.state, self.evaluated, self.proposals,
                                   len(self._ids), self.failures, self._last_reason,
                                   self.pending, tuple(self._ids))
