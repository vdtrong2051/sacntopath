"""HS-01.2 preview-only, bounded keyframe selection state machine.

SELECT is advisory and latches a pending request. Call capture_completed(True)
ONLY after HS-01.3 has verified/persisted a fresh RAW frameset. On failure,
call capture_completed(False), retaining the previously accepted reference.
Call reset() on camera reopen, session/ROI source switch and replay restart.
Neither novelty nor motion proxies measure pose, geometric overlap or registration.
"""
from __future__ import annotations

import numpy as np

from scantopath.modules.capture.domain.models import DepthRoi
from .frame_quality import FrameAssessment, FrameQualityEvaluator, FrameQualityStatus
from .keyframe_selection_models import (
    KeyframeDecision, KeyframeSelectionConfig, KeyframeSelectionResult, SelectionReason,
)


def _overlap(a: FrameAssessment, b: FrameAssessment) -> float:
    pair = a.valid_signature & b.valid_signature
    union = a.valid_signature | b.valid_signature
    return float(np.count_nonzero(pair) / max(1, np.count_nonzero(union)))


def _depth_delta(a: FrameAssessment, b: FrameAssessment) -> float:
    both = a.valid_signature & b.valid_signature
    if not np.any(both):
        return float("inf")
    return float(np.median(np.abs(a.depth_signature_m[both] - b.depth_signature_m[both])))


def _roi_intersection_fraction(a: DepthRoi | None, b: DepthRoi | None) -> float:
    if a is None or b is None or (a.frame_width, a.frame_height) != (b.frame_width, b.frame_height):
        return 0.0
    x0, y0 = max(a.x, b.x), max(a.y, b.y)
    x1, y1 = min(a.x + a.width, b.x + b.width), min(a.y + a.height, b.y + b.height)
    inter = max(0, x1 - x0) * max(0, y1 - y0)
    return inter / max(1, (a.width * a.height + b.width * b.height - inter))


class KeyframeSelector:
    """Single-thread-owned selector: callers serialize evaluate/capture_completed."""

    def __init__(self, *, evaluator: FrameQualityEvaluator | None = None,
                 config: KeyframeSelectionConfig | None = None):
        if evaluator is not None and not isinstance(evaluator, FrameQualityEvaluator):
            raise TypeError("evaluator must be FrameQualityEvaluator")
        if config is not None and not isinstance(config, KeyframeSelectionConfig):
            raise TypeError("config must be KeyframeSelectionConfig")
        self.evaluator = evaluator if evaluator is not None else FrameQualityEvaluator()
        self.config = config if config is not None else KeyframeSelectionConfig()
        self.reset()

    def reset(self) -> None:
        self._previous: FrameAssessment | None = None
        self._accepted: FrameAssessment | None = None
        self._pending: FrameAssessment | None = None
        self._last_seen_indices: tuple[int, int] | None = None
        self._last_seen_us: int | None = None

    @property
    def capture_pending(self) -> bool:
        return self._pending is not None

    def capture_completed(self, saved_and_verified: bool) -> None:
        if type(saved_and_verified) is not bool:
            raise TypeError("saved_and_verified must be bool")
        if self._pending is None:
            raise RuntimeError("no pending keyframe proposal")
        if saved_and_verified:
            # Preview trigger reference, NOT identity/pose of subsequent RAW packet.
            self._accepted = self._pending
        self._pending = None

    def evaluate(self, frame, roi: DepthRoi | None) -> KeyframeSelectionResult:
        a = self.evaluator.evaluate(frame, roi)

        def result(decision: KeyframeDecision, why: SelectionReason,
                   motion: float | None = None, novelty: float | None = None):
            return KeyframeSelectionResult(decision, why, a.frame_index, a.timestamp_us,
                                           a, motion_proxy_m=motion, novelty_score=novelty)

        indices = (a.color_frame_index, a.frame_index)
        if (self._last_seen_indices is not None
                and (indices[0] <= self._last_seen_indices[0]
                     or indices[1] <= self._last_seen_indices[1]
                     or a.timestamp_us <= self._last_seen_us)):
            return result(KeyframeDecision.REJECT, SelectionReason.STALE_FRAME)
        self._last_seen_indices = indices
        self._last_seen_us = a.timestamp_us
        if self._pending is not None:
            return result(KeyframeDecision.WAIT, SelectionReason.CAPTURE_PENDING)
        if a.status is FrameQualityStatus.ROI_REQUIRED:
            self._previous = None
            return result(KeyframeDecision.WAIT, SelectionReason.ROI_REQUIRED)
        if a.status is FrameQualityStatus.INSUFFICIENT_DEPTH:
            self._previous = None
            return result(KeyframeDecision.REJECT, SelectionReason.INSUFFICIENT_DEPTH)
        if a.status is FrameQualityStatus.LOW_FOCUS:
            self._previous = None
            return result(KeyframeDecision.REJECT, SelectionReason.LOW_FOCUS)

        previous = self._previous
        self._previous = a
        if previous is None or _roi_intersection_fraction(a.roi, previous.roi) < 0.70:
            return result(KeyframeDecision.WAIT, SelectionReason.STABILIZING)
        if _overlap(a, previous) < self.config.min_interframe_overlap_fraction:
            return result(KeyframeDecision.WAIT, SelectionReason.LOW_INTERFRAME_OVERLAP)
        motion = _depth_delta(a, previous)
        if motion > self.config.max_interframe_depth_change_m:
            return result(KeyframeDecision.WAIT, SelectionReason.MOTION_TOO_HIGH, motion)
        if self._accepted is not None and a.timestamp_us - self._accepted.timestamp_us < self.config.cooldown_us:
            return result(KeyframeDecision.WAIT, SelectionReason.COOLDOWN, motion)
        if self._accepted is None:
            self._pending = a
            return result(KeyframeDecision.SELECT, SelectionReason.SELECT_FIRST, motion)
        if _overlap(a, self._accepted) < self.config.min_reference_overlap_fraction:
            return result(KeyframeDecision.WAIT, SelectionReason.LOW_REFERENCE_OVERLAP, motion)
        depth_component = _depth_delta(a, self._accepted) / self.config.novelty_depth_normalizer_m
        color_component = float(np.mean(np.abs(
            a.intensity_signature - self._accepted.intensity_signature)) / 255.0)
        novelty = float(min(1.0, max(depth_component, color_component)))
        if novelty < self.config.min_novelty_score:
            return result(KeyframeDecision.WAIT, SelectionReason.DUPLICATE_VIEW_PROXY,
                          motion, novelty)
        self._pending = a
        return result(KeyframeDecision.SELECT, SelectionReason.SELECT_NOVEL, motion, novelty)
