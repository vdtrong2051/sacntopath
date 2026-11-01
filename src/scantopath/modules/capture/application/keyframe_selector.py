"""HS-01.3-R1: conservative, ROI-local, preview-only keyframe novelty.

One camera/session owns this selector.  A SELECT is NOT a saved keyframe:
only a successful verified RAW-v2 commit may call capture_completed(True).
The accepted proxy is the PREVIEW that triggered that verified commit, not
pixels reconstructed from RAW, and it is not a camera pose / segmentation.

R1 reduces static false positives from depth speckle, global illumination
changes and small ROI shifts. The depth 'near surface' is only a *proxy*;
this algorithm cannot prove which pixels belong to the real object.
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
    intersection = max(0, x1 - x0) * max(0, y1 - y0)
    return intersection / max(1, a.width * a.height + b.width * b.height - intersection)


def _foreground_proxy(a: FrameAssessment, config: KeyframeSelectionConfig) -> np.ndarray:
    """Closest valid part of the ROI; neither a segmentation nor an object mask."""
    valid = a.valid_signature
    if int(np.count_nonzero(valid)) < config.min_near_surface_samples:
        return valid
    near_limit = float(np.percentile(a.depth_signature_m[valid], 25)) + config.near_surface_band_m
    foreground = valid & (a.depth_signature_m <= near_limit)
    # An edge-only candidate is less trustworthy than the complete valid ROI.
    if int(np.count_nonzero(foreground)) < config.min_near_surface_samples:
        return valid
    return foreground


def _aligned_slices(shape: tuple[int, int], dy: int, dx: int):
    height, width = shape
    ay0, ay1 = max(0, dy), min(height, height + dy)
    ax0, ax1 = max(0, dx), min(width, width + dx)
    by0, by1 = max(0, -dy), min(height, height - dy)
    bx0, bx1 = max(0, -dx), min(width, width - dx)
    return (slice(ay0, ay1), slice(ax0, ax1)), (slice(by0, by1), slice(bx0, bx1))


def _robust_novelty(a: FrameAssessment, reference: FrameAssessment,
                    cfg: KeyframeSelectionConfig) -> float | None:
    """Find least-change ±1-cell proxy registration, then score ROI near surface.

    The alignment is intentionally small. Large translations and viewpoint
    registration remain the responsibility of HS-02, not this selector.
    """
    if (a.depth_signature_m.shape != reference.depth_signature_m.shape or
            a.intensity_signature.shape != reference.intensity_signature.shape):
        return None
    foreground_a = _foreground_proxy(a, cfg)
    foreground_b = _foreground_proxy(reference, cfg)
    best = None
    grid_shape = a.depth_signature_m.shape
    for dy in range(-cfg.max_signature_shift_cells, cfg.max_signature_shift_cells + 1):
        for dx in range(-cfg.max_signature_shift_cells, cfg.max_signature_shift_cells + 1):
            sa, sb = _aligned_slices(grid_shape, dy, dx)
            va, vb = a.valid_signature[sa], reference.valid_signature[sb]
            paired = va & vb
            fg_a, fg_b = foreground_a[sa], foreground_b[sb]
            selected = paired & (fg_a | fg_b)
            n_selected = int(np.count_nonzero(selected))
            if n_selected < cfg.min_near_surface_samples:
                continue
            # Never claim a good match if barely any of the two near surfaces overlaps.
            fg_union = fg_a | fg_b
            valid_overlap = float(np.count_nonzero(selected) / max(1, np.count_nonzero(fg_union)))
            if valid_overlap < cfg.min_reference_overlap_fraction:
                continue

            depth_difference = np.abs(a.depth_signature_m[sa] - reference.depth_signature_m[sb])
            # Mean is vulnerable to a small bad patch; median is robust but
            # will still detect a coherent new surface over many ROI samples.
            depth_m = float(np.median(depth_difference[selected]))
            depth_score = min(1.0, max(0.0, depth_m - cfg.depth_noise_floor_m)
                              / cfg.novelty_depth_normalizer_m)

            delta_gray = a.intensity_signature[sa] - reference.intensity_signature[sb]
            # Global brightness/exposure change is not viewpoint novelty.
            exposure_shift = float(np.median(delta_gray[selected]))
            residual = np.abs(delta_gray - exposure_shift)
            color_score = min(1.0, float(np.median(np.maximum(
                residual[selected] - cfg.color_noise_floor_gray, 0.0))) / 255.0)

            # Do not overfit isolated depth holes / 1-2 near-surface pixels.
            silhouette = float(np.count_nonzero(fg_a ^ fg_b) / max(1, np.count_nonzero(fg_union)))
            silhouette_score = min(1.0, max(0.0, silhouette - cfg.silhouette_noise_fraction))
            score = max(depth_score, color_score, silhouette_score)
            if best is None or score < best:
                best = score
    return best


class KeyframeSelector:
    """Single-thread-owned selector: serialize evaluate/capture_completed/reset."""

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
            self._accepted = self._pending
        self._pending = None

    def evaluate(self, frame, roi: DepthRoi | None) -> KeyframeSelectionResult:
        current = self.evaluator.evaluate(frame, roi)

        def result(decision: KeyframeDecision, why: SelectionReason,
                   motion: float | None = None, novelty: float | None = None):
            return KeyframeSelectionResult(decision, why, current.frame_index,
                                           current.timestamp_us, current,
                                           motion_proxy_m=motion, novelty_score=novelty)

        indices = (current.color_frame_index, current.frame_index)
        if (self._last_seen_indices is not None
                and (indices[0] <= self._last_seen_indices[0]
                     or indices[1] <= self._last_seen_indices[1]
                     or current.timestamp_us <= self._last_seen_us)):
            return result(KeyframeDecision.REJECT, SelectionReason.STALE_FRAME)
        self._last_seen_indices = indices
        self._last_seen_us = current.timestamp_us
        if self._pending is not None:
            return result(KeyframeDecision.WAIT, SelectionReason.CAPTURE_PENDING)
        if current.status is FrameQualityStatus.ROI_REQUIRED:
            self._previous = None
            return result(KeyframeDecision.WAIT, SelectionReason.ROI_REQUIRED)
        if current.status is FrameQualityStatus.INSUFFICIENT_DEPTH:
            self._previous = None
            return result(KeyframeDecision.REJECT, SelectionReason.INSUFFICIENT_DEPTH)
        if current.status is FrameQualityStatus.LOW_FOCUS:
            self._previous = None
            return result(KeyframeDecision.REJECT, SelectionReason.LOW_FOCUS)

        previous = self._previous
        self._previous = current
        if previous is None or _roi_intersection_fraction(current.roi, previous.roi) < 0.70:
            return result(KeyframeDecision.WAIT, SelectionReason.STABILIZING)
        if _overlap(current, previous) < self.config.min_interframe_overlap_fraction:
            return result(KeyframeDecision.WAIT, SelectionReason.LOW_INTERFRAME_OVERLAP)
        motion = _depth_delta(current, previous)
        if motion > self.config.max_interframe_depth_change_m:
            return result(KeyframeDecision.WAIT, SelectionReason.MOTION_TOO_HIGH, motion)
        if self._accepted is not None and current.timestamp_us - self._accepted.timestamp_us < self.config.cooldown_us:
            return result(KeyframeDecision.WAIT, SelectionReason.COOLDOWN, motion)
        if self._accepted is None:
            self._pending = current
            return result(KeyframeDecision.SELECT, SelectionReason.SELECT_FIRST, motion)
        if _roi_intersection_fraction(current.roi, self._accepted.roi) < 0.55:
            return result(KeyframeDecision.WAIT, SelectionReason.LOW_REFERENCE_OVERLAP, motion)
        if _overlap(current, self._accepted) < self.config.min_reference_overlap_fraction:
            return result(KeyframeDecision.WAIT, SelectionReason.LOW_REFERENCE_OVERLAP, motion)
        novelty = _robust_novelty(current, self._accepted, self.config)
        if novelty is None:
            return result(KeyframeDecision.WAIT, SelectionReason.LOW_REFERENCE_OVERLAP, motion)
        if novelty < self.config.min_novelty_score:
            return result(KeyframeDecision.WAIT, SelectionReason.DUPLICATE_VIEW_PROXY, motion, novelty)
        self._pending = current
        return result(KeyframeDecision.SELECT, SelectionReason.SELECT_NOVEL, motion, novelty)
