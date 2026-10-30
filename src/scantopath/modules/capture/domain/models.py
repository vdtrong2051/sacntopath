"""GĐ2-09.01 foundational domain DTOs. No sensor, Qt or persistence dependency.

A 2D depth ROI is NOT object segmentation or a camera pose.
"""
from __future__ import annotations
from dataclasses import dataclass
from enum import Enum


class CameraState(str, Enum):
    IDLE = "idle"
    OPENING = "opening"
    STREAMING = "streaming"
    CAPTURING = "capturing"
    STOPPING = "stopping"
    CLOSED = "closed"
    FAILED = "failed"


class RoiSource(str, Enum):
    MANUAL = "manual"
    DEPTH_SUGGESTION = "depth_suggestion"


@dataclass(frozen=True, slots=True)
class DepthRoi:
    """ROI in the native DEPTH pixel grid, not registered to color pixels."""

    x: int
    y: int
    width: int
    height: int
    frame_width: int
    frame_height: int
    source: RoiSource = RoiSource.MANUAL

    def __post_init__(self) -> None:
        values = (self.x, self.y, self.width, self.height, self.frame_width, self.frame_height)
        if any(type(v) is not int for v in values):
            raise TypeError("ROI coordinates and sizes must be integers")
        if self.x < 0 or self.y < 0 or min(self.width, self.height, self.frame_width, self.frame_height) <= 0:
            raise ValueError("ROI bounds must be nonnegative with positive size")
        if self.x + self.width > self.frame_width or self.y + self.height > self.frame_height:
            raise ValueError("ROI must be inside the depth frame")
        object.__setattr__(self, "source", RoiSource(self.source))
