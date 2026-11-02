"""FT-06.1: display-only measured-object bounding box, NOT RAW authorization.

Observations are computed from exactly the cloud's owned Depth UV lineage. When
an observation is absent, the old rectangle can be shown briefly with a LOST
label; it NEVER produces a new mask/cloud or authorizes a snapshot.
"""
from __future__ import annotations

from dataclasses import dataclass
from math import hypot, isfinite
from time import monotonic

import numpy as np


@dataclass(frozen=True, slots=True)
class ObjectBounding:
    rect_xywh: tuple[int, int, int, int] | None
    status: str
    observed: bool
    age_s: float
    frame_index: int | None


class LiveObjectBoundingTracker:
    def __init__(self, *, hold_seconds: float = 0.65, lost_seconds: float = 1.6,
                 padding_fraction: float = 0.08, max_jump_fraction: float = 0.30):
        vals = (hold_seconds, lost_seconds, padding_fraction, max_jump_fraction)
        if (not all(type(v) in (int, float) and isfinite(v) for v in vals)
                or not 0 < hold_seconds < lost_seconds <= 10
                or not 0 < padding_fraction <= 0.25
                or not 0 < max_jump_fraction <= 1.0):
            raise ValueError('FT061_TRACKER_CONFIG_INVALID')
        self.hold_seconds = float(hold_seconds)
        self.lost_seconds = float(lost_seconds)
        self.padding_fraction = float(padding_fraction)
        self.max_jump_fraction = float(max_jump_fraction)
        self.reset()

    def reset(self) -> None:
        self._rect: tuple[int, int, int, int] | None = None
        self._size: tuple[int, int] | None = None
        self._frame_index: int | None = None
        self._generation: int | None = None
        self._last_seen: float | None = None
        self._consecutive = 0
        self._status = 'LOST'
        self._explicit_miss = False

    def observe(self, *, generation: int, frame_index: int, uv: np.ndarray,
                depth_width: int, depth_height: int,
                corner_count: int = 0, reprojection_px: float | None = None,
                now: float | None = None) -> ObjectBounding:
        if (type(generation) is not int or generation <= 0
                or type(frame_index) is not int or frame_index < 0
                or type(depth_width) is not int or type(depth_height) is not int
                or depth_width <= 0 or depth_height <= 0
                or not isinstance(uv, np.ndarray) or uv.dtype != np.int32
                or uv.ndim != 2 or uv.shape[1] != 2 or uv.shape[0] == 0):
            raise ValueError('FT061_TRACKER_FRAME_INVALID')
        clock = monotonic() if now is None else float(now)
        if not isfinite(clock):
            raise ValueError('FT061_TRACKER_TIME_INVALID')
        if (np.any(uv[:, 0] < 0) or np.any(uv[:, 1] < 0)
                or np.any(uv[:, 0] >= depth_width) or np.any(uv[:, 1] >= depth_height)):
            raise ValueError('FT061_TRACKER_UV_INVALID')
        if self._generation != generation or self._size != (depth_width, depth_height):
            self.reset()
            self._generation = generation
            self._size = (depth_width, depth_height)
        if self._frame_index is not None and frame_index <= self._frame_index:
            raise ValueError('FT061_TRACKER_STALE_FRAME')
        minx, miny = np.min(uv, axis=0).tolist()
        maxx, maxy = np.max(uv, axis=0).tolist()
        dx, dy = maxx - minx + 1, maxy - miny + 1
        padx = max(6, min(32, round(dx * self.padding_fraction)))
        pady = max(6, min(32, round(dy * self.padding_fraction)))
        x0, y0 = max(0, minx - padx), max(0, miny - pady)
        x1, y1 = min(depth_width, maxx + padx + 1), min(depth_height, maxy + pady + 1)
        rect = (x0, y0, x1 - x0, y1 - y0)
        jumped = False
        if self._rect is not None:
            old = self._rect
            old_c = (old[0] + old[2]/2, old[1] + old[3]/2)
            new_c = (rect[0] + rect[2]/2, rect[1] + rect[3]/2)
            moved = hypot(old_c[0] - new_c[0], old_c[1] - new_c[1])
            jumped = moved > self.max_jump_fraction * hypot(depth_width, depth_height)
        self._consecutive = 1 if jumped or self._last_seen is None or (
            clock - self._last_seen > self.hold_seconds) else self._consecutive + 1
        self._rect = rect
        self._explicit_miss = False
        self._last_seen = clock
        self._frame_index = frame_index
        degraded = (corner_count > 0 and corner_count < 10) or (
            reprojection_px is not None and reprojection_px > 1.5)
        self._status = ('REACQUIRING' if self._consecutive == 1 and jumped else
                        'DEGRADED' if degraded else 'TRACKING')
        return ObjectBounding(rect, self._status, True, 0.0, frame_index)

    def missed(self, *, now: float | None = None) -> ObjectBounding:
        self._explicit_miss = True
        return self.current(now=now, missed=True)

    def current(self, *, now: float | None = None, missed: bool = False) -> ObjectBounding:
        clock = monotonic() if now is None else float(now)
        if not isfinite(clock):
            raise ValueError('FT061_TRACKER_TIME_INVALID')
        if self._rect is None or self._last_seen is None:
            return ObjectBounding(None, 'LOST', False, 0.0, None)
        age = max(0.0, clock - self._last_seen)
        if age >= self.lost_seconds:
            return ObjectBounding(None, 'LOST', False, age, self._frame_index)
        if missed or self._explicit_miss or age >= self.hold_seconds:
            # Last-known box is a VISUAL hint only, never a valid observation.
            return ObjectBounding(self._rect, 'TEMPORARILY_LOST', False,
                                  age, self._frame_index)
        return ObjectBounding(self._rect, self._status, False, age, self._frame_index)
