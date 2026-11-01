"""FT-05.6: display-only Depth ROI stabilization; never authorizes Auto Keyframe.

The original TrackingResult is retained for ROI safety and automatic Capture.
No sensor, Qt, RAW, or persistence dependencies.
"""
from __future__ import annotations
from dataclasses import dataclass
from math import hypot

from scantopath.modules.capture.domain.models import DepthRoi, RoiSource
from scantopath.modules.capture.application.bbox_tracking import TrackingResult


@dataclass(frozen=True, slots=True)
class DisplayStabilizationConfig:
    alpha: float = 0.22
    deadband_px: float = 3.0
    max_step_fraction: float = 0.12
    max_hold_frames: int = 2


class DepthDisplayStabilizer:
    """Reduce UI jitter; NONE of its output is a keyframe safety certificate."""

    def __init__(self, config: DisplayStabilizationConfig | None = None) -> None:
        self.config = config or DisplayStabilizationConfig()
        if not (0 < self.config.alpha <= 1 and self.config.deadband_px >= 0 and
                0 < self.config.max_step_fraction <= 1 and
                type(self.config.max_hold_frames) is int and self.config.max_hold_frames >= 0):
            raise ValueError('INVALID_DISPLAY_STABILIZER_CONFIG')
        self.reset()

    def reset(self) -> None:
        self._display: DepthRoi | None = None
        self._last_frame_index: int | None = None
        self._missing = 0

    @property
    def current(self) -> DepthRoi | None:
        return self._display

    def update(self, frame_index: int, tracking: TrackingResult | None) -> DepthRoi | None:
        if type(frame_index) is not int or frame_index < 0:
            raise ValueError('INVALID_DISPLAY_FRAME_INDEX')
        if self._last_frame_index is not None and frame_index <= self._last_frame_index:
            return self._display  # idempotent double UI notification, ignore out-of-order
        self._last_frame_index = frame_index
        incoming = tracking.roi if tracking is not None and tracking.usable else None
        if incoming is None:
            self._missing += 1
            if self._missing > self.config.max_hold_frames:
                self._display = None
            return self._display
        self._missing = 0
        prev = self._display
        if prev is None or (prev.frame_width, prev.frame_height) != (incoming.frame_width, incoming.frame_height):
            self._display = incoming
            return incoming
        max_x = self.config.max_step_fraction * incoming.frame_width
        max_y = self.config.max_step_fraction * incoming.frame_height
        def blend(a: float, b: float, cap: float) -> float:
            delta = b-a
            if abs(delta) <= self.config.deadband_px:
                return a
            delta = max(-cap, min(cap, delta))
            return a+self.config.alpha*delta
        x0 = blend(prev.x, incoming.x, max_x)
        y0 = blend(prev.y, incoming.y, max_y)
        x1 = blend(prev.x+prev.width, incoming.x+incoming.width, max_x)
        y1 = blend(prev.y+prev.height, incoming.y+incoming.height, max_y)
        w,h = incoming.frame_width,incoming.frame_height
        x0 = max(0, min(w-1, round(x0)))
        y0 = max(0, min(h-1, round(y0)))
        x1 = max(x0+1,min(w,round(x1)))
        y1 = max(y0+1,min(h,round(y1)))
        self._display = DepthRoi(x0,y0,x1-x0,y1-y0,w,h,RoiSource.DEPTH_SUGGESTION)
        return self._display
