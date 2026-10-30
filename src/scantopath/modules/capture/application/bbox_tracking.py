"""GD2-09.07.1: conservative frame-to-frame depth bbox tracking.

No Qt, native SDK, camera pose, persistence, or manual ROI manipulation.
Call reset() at every camera stop/reopen or source switch (GD2-09.07.2).
"""
from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from math import hypot, isfinite

import numpy as np

from scantopath.modules.capture.domain.models import DepthRoi, RoiSource
from .depth_bbox import DepthBboxDetector, DepthDetection, DetectionStatus


class TrackingStatus(str, Enum):
    TRACKING = "tracking"
    ACQUIRING = "acquiring"
    HOLDING = "holding"
    NO_TARGET = "no_target"
    AMBIGUOUS = "ambiguous"
    JUMP_REJECTED = "jump_rejected"


@dataclass(frozen=True, slots=True)
class TrackingConfig:
    confirmation_frames: int = 2
    max_missing_frames: int = 2
    smoothing_alpha: float = 0.45
    max_center_shift_fraction: float = 0.18

    def __post_init__(self) -> None:
        for name in ("confirmation_frames", "max_missing_frames"):
            value = getattr(self, name)
            if type(value) is not int or value < (1 if name == "confirmation_frames" else 0):
                raise ValueError(f"invalid {name}")
        for name in ("smoothing_alpha", "max_center_shift_fraction"):
            value = getattr(self, name)
            if (type(value) not in (int, float) or not isfinite(value)
                    or not 0 < value <= 1):
                raise ValueError(f"invalid {name}")


@dataclass(frozen=True, slots=True)
class TrackingResult:
    status: TrackingStatus
    roi: DepthRoi | None
    confidence: float
    detection: DepthDetection

    @property
    def usable(self) -> bool:
        return self.status is TrackingStatus.TRACKING and self.roi is not None


def _close_enough(a: DepthRoi, b: DepthRoi, fraction: float) -> bool:
    if (a.frame_width, a.frame_height) != (b.frame_width, b.frame_height):
        return False
    acx, acy = a.x + a.width / 2, a.y + a.height / 2
    bcx, bcy = b.x + b.width / 2, b.y + b.height / 2
    if hypot(acx - bcx, acy - bcy) > fraction * hypot(a.frame_width, a.frame_height):
        return False
    # Guard against switching from a small object to a huge foreground region.
    if (max(a.width / b.width, b.width / a.width,
            a.height / b.height, b.height / a.height) > 3.0):
        return False
    return True


def _blend(previous: DepthRoi, current: DepthRoi, alpha: float) -> DepthRoi:
    fw, fh = current.frame_width, current.frame_height
    x0 = round((1 - alpha) * previous.x + alpha * current.x)
    y0 = round((1 - alpha) * previous.y + alpha * current.y)
    x1 = round((1 - alpha) * (previous.x + previous.width)
               + alpha * (current.x + current.width))
    y1 = round((1 - alpha) * (previous.y + previous.height)
               + alpha * (current.y + current.height))
    x0 = max(0, min(fw - 1, x0))
    y0 = max(0, min(fh - 1, y0))
    x1 = max(x0 + 1, min(fw, x1))
    y1 = max(y0 + 1, min(fh, y1))
    return DepthRoi(x0, y0, x1 - x0, y1 - y0, fw, fh,
                    RoiSource.DEPTH_SUGGESTION)


class DepthBboxTracker:
    def __init__(self, detector: DepthBboxDetector | None = None,
                 config: TrackingConfig | None = None) -> None:
        if detector is not None and not isinstance(detector, DepthBboxDetector):
            raise TypeError("detector must be DepthBboxDetector")
        if config is not None and not isinstance(config, TrackingConfig):
            raise TypeError("config must be TrackingConfig")
        self.detector = detector if detector is not None else DepthBboxDetector()
        self.config = config if config is not None else TrackingConfig()
        self.reset()

    def reset(self) -> None:
        """Required at camera lifecycle changes: never reuse a stale ROI."""
        self._last: DepthRoi | None = None
        self._pending: DepthRoi | None = None
        self._confirmations = 0
        self._missing = 0

    def _lost(self, detection: DepthDetection, status: TrackingStatus) -> TrackingResult:
        if self._last is not None:
            self._missing += 1
            if self._missing <= self.config.max_missing_frames:
                # Internal-only hold; never emit an old ROI as a new detection.
                return TrackingResult(
                    status if status in (TrackingStatus.AMBIGUOUS, TrackingStatus.JUMP_REJECTED)
                    else TrackingStatus.HOLDING,
                    None, 0.0, detection,
                )
        self.reset()
        return TrackingResult(status, None, 0.0, detection)

    def update(self, depth_u16: np.ndarray,
               depth_scale_m_per_unit: float) -> TrackingResult:
        detection = self.detector.detect(depth_u16, depth_scale_m_per_unit)
        roi = detection.roi
        if not detection.usable or roi is None:
            status = (TrackingStatus.AMBIGUOUS if detection.status is DetectionStatus.AMBIGUOUS
                      else TrackingStatus.NO_TARGET)
            return self._lost(detection, status)

        if self._last is not None:
            if not _close_enough(self._last, roi, self.config.max_center_shift_fraction):
                result = self._lost(detection, TrackingStatus.JUMP_REJECTED)
                # Large jumps do not create a new accepted ROI until reacquired.
                return result
            self._missing = 0
            self._last = _blend(self._last, roi, self.config.smoothing_alpha)
            return TrackingResult(TrackingStatus.TRACKING, self._last,
                                  detection.confidence, detection)

        if self._pending is None or not _close_enough(
            self._pending, roi, self.config.max_center_shift_fraction
        ):
            self._pending = roi
            self._confirmations = 1
        else:
            self._pending = roi
            self._confirmations += 1

        if self._confirmations < self.config.confirmation_frames:
            return TrackingResult(TrackingStatus.ACQUIRING, None, 0.0, detection)

        self._last = roi
        self._missing = 0
        self._pending = None
        return TrackingResult(TrackingStatus.TRACKING, roi,
                              detection.confidence, detection)
