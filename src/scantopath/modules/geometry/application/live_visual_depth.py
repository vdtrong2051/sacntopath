"""FT-06.1 R1 — bounded visual-only temporal/spatial Depth enhancement.

Sensor RGB-D / RAW frames remain unchanged. Invalid pixels are estimated only
when local or historical support is sufficient. This is never metric truth.
"""
from __future__ import annotations
from collections import deque
from dataclasses import dataclass

import numpy as np


@dataclass(frozen=True)
class VisualDepthConfig:
    temporal_tolerance_mm: int = 20
    temporal_motion_reset_mm: int = 35
    max_motion_fraction: float = 0.25
    spatial_tolerance_mm: int = 18
    smoothing_limit_mm: int = 9
    hole_passes: int = 3
    max_temporal_frames: int = 3


class VisualDepthEnhancer:
    """Single-worker stateful filter; process only one camera generation at a time."""
    def __init__(self, config: VisualDepthConfig | None = None) -> None:
        self.cfg = config or VisualDepthConfig()
        self._history: deque[np.ndarray] = deque(maxlen=self.cfg.max_temporal_frames)
        self._key: tuple[int, str, tuple[int, int]] | None = None
        self._last_index = -1

    def reset(self) -> None:
        self._history.clear()
        self._key = None
        self._last_index = -1

    def process(self, depth: np.ndarray, *, generation: int, frame_index: int,
                mode: str = 'visual') -> tuple[np.ndarray, np.ndarray, np.ndarray]:
        if (not isinstance(depth, np.ndarray) or depth.dtype != np.uint16 or
                depth.ndim != 2 or depth.size == 0 or depth.size > 32_000_000 or
                type(generation) is not int or generation < 1 or
                type(frame_index) is not int or frame_index < 0 or
                mode not in ('visual', 'off')):
            raise ValueError('VISUAL_DEPTH_INPUT_INVALID')
        key = (generation, mode, depth.shape)
        if (key != self._key or frame_index <= self._last_index or
                frame_index - self._last_index > 15):
            self.reset()
            self._key = key
        self._last_index = frame_index
        original = np.ascontiguousarray(depth)
        empty = np.zeros(depth.shape, dtype=np.bool_)
        if mode == 'off':
            copy = np.array(original, copy=True)
            copy.setflags(write=False)
            return copy, empty, empty.copy()
        valid = (original != 0) & (original != 65535)
        if self._history:
            last = self._history[-1]
            together = valid & (last != 0) & (last != 65535)
            if int(together.sum()) > 200:
                delta = np.abs(original.astype(np.int32)-last.astype(np.int32))
                if np.count_nonzero(together & (delta > self.cfg.temporal_motion_reset_mm)) / int(together.sum()) > self.cfg.max_motion_fraction:
                    self._history.clear()
        result = np.array(original, copy=True)
        # Shallow, bounded temporal smoothing only where both frames measured.
        if self._history:
            prev = self._history[-1]
            common = valid & (prev != 0) & (prev != 65535)
            near = common & (np.abs(result.astype(np.int32) - prev.astype(np.int32)) <= self.cfg.temporal_tolerance_mm)
            result[near] = np.rint((result[near].astype(np.float32) * .7 +
                                    prev[near].astype(np.float32) * .3)).astype(np.uint16)
        if len(self._history) >= 2:
            p, q = self._history[-2], self._history[-1]
            stable = (valid & (p > 0) & (q > 0) & (p != 65535) & (q != 65535) &
                      (np.abs(original.astype(np.int32)-p.astype(np.int32)) <= self.cfg.temporal_tolerance_mm) &
                      (np.abs(original.astype(np.int32)-q.astype(np.int32)) <= self.cfg.temporal_tolerance_mm))
            result[stable] = np.rint((original[stable].astype(np.float32) +
                                      p[stable].astype(np.float32) + q[stable].astype(np.float32))/3.).astype(np.uint16)
        # Median smoothing only when local neighborhood supports a measured point.
        import cv2
        before_spatial = result.copy()
        local = cv2.medianBlur(result, 3)
        count = cv2.boxFilter(valid.astype(np.uint8), -1, (3, 3), normalize=False,
                              borderType=cv2.BORDER_CONSTANT)
        delta = np.abs(local.astype(np.int32) - result.astype(np.int32))
        smooth = valid & (count >= 6) & (local > 0) & (delta <= self.cfg.smoothing_limit_mm)
        result[smooth] = local[smooth]
        # Fill strictly local gaps; neither extrapolate object silhouettes nor fill
        # large unseen patches. Require opposed supporting pixels and local density.
        for _ in range(self.cfg.hole_passes):
            good = (result != 0) & (result != 65535)
            count = cv2.boxFilter(good.astype(np.uint8), -1, (3, 3), normalize=False,
                                  borderType=cv2.BORDER_CONSTANT)
            left = np.pad(result[:, :-1], ((0, 0), (1, 0)), constant_values=0)
            right = np.pad(result[:, 1:], ((0, 0), (0, 1)), constant_values=0)
            above = np.pad(result[:-1, :], ((1, 0), (0, 0)), constant_values=0)
            below = np.pad(result[1:, :], ((0, 1), (0, 0)), constant_values=0)
            hg = ((left > 0) & (right > 0) & (left < 65535) & (right < 65535) &
                  (np.abs(left.astype(np.int32) - right.astype(np.int32)) <= self.cfg.spatial_tolerance_mm))
            vg = ((above > 0) & (below > 0) & (above < 65535) & (below < 65535) &
                  (np.abs(above.astype(np.int32) - below.astype(np.int32)) <= self.cfg.spatial_tolerance_mm))
            holes = (~good) & (count >= 5) & (hg | vg)
            if not np.any(holes):
                break
            h = (left.astype(np.int32) + right.astype(np.int32)) // 2
            v = (above.astype(np.int32) + below.astype(np.int32)) // 2
            fill = np.where(hg, h, v)
            result[holes] = fill[holes].astype(np.uint16)
        # Historical liveness: require two agreeing measured past frames AND
        # current local support. Never add points from history by itself.
        if len(self._history) >= 2:
            p, q = self._history[-2], self._history[-1]
            invalid = (original == 0) | (original == 65535)
            local_median = cv2.medianBlur(result, 3)
            local_valid = ((result > 0) & (result != 65535)).astype(np.uint8)
            count = cv2.boxFilter(local_valid, -1, (3, 3), normalize=False,
                                  borderType=cv2.BORDER_CONSTANT)
            historical = (invalid & (count >= 4) &
                          (p > 0) & (q > 0) & (p < 65535) & (q < 65535) &
                          (local_median > 0) &
                          (np.abs(p.astype(np.int32)-q.astype(np.int32)) <= self.cfg.spatial_tolerance_mm) &
                          (np.abs(local_median.astype(np.int32)-q.astype(np.int32)) <= self.cfg.spatial_tolerance_mm))
            result[historical] = np.rint(.55 * local_median[historical].astype(np.float32) +
                                          .45 * q[historical].astype(np.float32)).astype(np.uint16)
        inferred = ~valid & (result != 0) & (result != 65535)
        modified = valid & (result != original)
        self._history.append(np.array(original, copy=True))
        for a in (result, inferred, modified):
            a.setflags(write=False)
        return result, inferred, modified


class StableDepthScale:
    """Preview-only tone mapping with bounded temporal percentile drift.

    Does not alter source Depth, calibration or geometry. The first image can
    initialize immediately; later color-range transitions are smoothed.
    """
    def __init__(self, alpha: float = .10) -> None:
        if not 0 < alpha <= 1:
            raise ValueError('DEPTH_DISPLAY_ALPHA_INVALID')
        self.alpha = alpha
        self.reset()

    def reset(self) -> None:
        self._lo = self._hi = None
        self._shape = None

    def update(self, depth: np.ndarray) -> np.ndarray:
        if (not isinstance(depth, np.ndarray) or depth.ndim != 2 or
                depth.dtype != np.uint16):
            raise ValueError('DEPTH_DISPLAY_INPUT_INVALID')
        if self._shape != depth.shape:
            self.reset()
            self._shape = depth.shape
        valid = (depth > 0) & (depth != 65535)
        out = np.zeros(depth.shape, dtype=np.uint8)
        sample = depth[::6, ::6]
        vals = sample[(sample > 0) & (sample != 65535)]
        if vals.size < 10:
            return out
        lo, hi = (float(x) for x in np.percentile(vals, (2., 98.)))
        if hi - lo < 1:
            hi = lo + 1
        if self._lo is None:
            self._lo, self._hi = lo, hi
        else:
            self._lo += self.alpha * (lo - self._lo)
            self._hi += self.alpha * (hi - self._hi)
        scaled = 255.0 * (1.0 - np.clip((depth[valid].astype(np.float32) - self._lo) /
                                            max(self._hi - self._lo, 1.), 0., 1.))
        out[valid] = scaled.astype(np.uint8)
        out.setflags(write=False)
        return out
