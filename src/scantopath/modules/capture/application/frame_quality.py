"""HS-01.2: bounded, non-mutating quality metrics for *preview* RGB-D frames.

The ROI belongs to the native depth grid. Mapping it proportionally to RGB
produces an image-quality proxy ONLY: it is NOT calibrated RGB/depth alignment,
an object mask, tracking or a camera pose. No SDK, Qt, Open3D or storage access.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from math import isfinite
from typing import TYPE_CHECKING

import numpy as np

from scantopath.modules.capture.domain.models import DepthRoi

if TYPE_CHECKING:
    from .live_stream import LiveRgbdFrame


class FrameQualityStatus(str, Enum):
    OK = "ok"
    ROI_REQUIRED = "roi_required"
    INSUFFICIENT_DEPTH = "insufficient_depth"
    LOW_FOCUS = "low_focus"


@dataclass(frozen=True, slots=True)
class FrameQualityConfig:
    min_depth_m: float = 0.18
    max_depth_m: float = 2.5
    min_valid_fraction: float = 0.35
    min_valid_samples: int = 25
    sample_grid: int = 16
    # 0 means disabled: low-texture engineering surfaces are not assumed blurred.
    min_focus_score: float = 0.0

    def __post_init__(self) -> None:
        for name in ("min_depth_m", "max_depth_m", "min_valid_fraction", "min_focus_score"):
            x = getattr(self, name)
            if type(x) not in (float, int) or not isfinite(x):
                raise ValueError(f"invalid {name}")
        if not (0 < self.min_depth_m < self.max_depth_m <= 50):
            raise ValueError("invalid metric depth range")
        if not 0 < self.min_valid_fraction <= 1:
            raise ValueError("invalid valid depth fraction")
        if self.min_focus_score < 0:
            raise ValueError("min_focus_score must be nonnegative")
        if type(self.min_valid_samples) is not int or not 1 <= self.min_valid_samples <= 4096:
            raise ValueError("invalid min_valid_samples")
        if type(self.sample_grid) is not int or not 4 <= self.sample_grid <= 64:
            raise ValueError("invalid sample_grid")
        if self.min_valid_samples > self.sample_grid ** 2:
            raise ValueError("min_valid_samples exceeds sampled pixel budget")


@dataclass(frozen=True, slots=True, eq=False)
class FrameAssessment:
    status: FrameQualityStatus
    frame_index: int
    color_frame_index: int
    timestamp_us: int
    roi: DepthRoi | None
    valid_depth_fraction: float
    valid_depth_samples: int
    focus_score: float
    # Small bounded thumbnails, no full image retained. Never writeable.
    depth_signature_m: np.ndarray = field(repr=False)
    intensity_signature: np.ndarray = field(repr=False)
    valid_signature: np.ndarray = field(repr=False)

    @property
    def usable(self) -> bool:
        return self.status is FrameQualityStatus.OK


def _axis(start: int, count: int, samples: int) -> np.ndarray:
    # Center-of-bin sampling; bounded work regardless of camera resolution.
    return start + np.minimum(count - 1, ((np.arange(samples) + 0.5) * count / samples).astype(np.intp))


def _read_only(a: np.ndarray) -> np.ndarray:
    x = np.array(a, copy=True, order="C")
    x.setflags(write=False)
    return x


class FrameQualityEvaluator:
    """Evaluate one owned live frame using at most sample_grid**2 RGB-D pixels."""

    def __init__(self, config: FrameQualityConfig | None = None):
        if config is not None and not isinstance(config, FrameQualityConfig):
            raise TypeError("config must be FrameQualityConfig")
        self.config = config if config is not None else FrameQualityConfig()

    def evaluate(self, frame: LiveRgbdFrame, roi: DepthRoi | None) -> FrameAssessment:
        # A structural interface permits offline synthetic tests without a camera.
        if not hasattr(frame, "source") or not hasattr(frame, "depth_u16") or not hasattr(frame, "color_rgb"):
            raise TypeError("expected LiveRgbdFrame-like input")
        source, depth, rgb = frame.source, frame.depth_u16, frame.color_rgb
        if (not isinstance(depth, np.ndarray) or depth.dtype != np.uint16 or depth.ndim != 2
                or not isinstance(rgb, np.ndarray) or rgb.dtype != np.uint8
                or rgb.ndim != 3 or rgb.shape[2] != 3
                or depth.size == 0 or rgb.size == 0):
            raise ValueError("invalid RGB-D arrays")
        if (depth.shape != (source.depth_height, source.depth_width)
                or rgb.shape != (source.color_height, source.color_width, 3)):
            raise ValueError("live frame grids mismatch source")
        scale = source.depth_scale_m_per_unit
        if type(scale) not in (int, float) or not isfinite(scale) or scale <= 0:
            raise ValueError("invalid depth scale")
        if roi is not None and (not isinstance(roi, DepthRoi)
                or (roi.frame_width, roi.frame_height) != (depth.shape[1], depth.shape[0])):
            raise ValueError("ROI must match native depth grid")
        grid = self.config.sample_grid
        empty_depth = _read_only(np.zeros((grid, grid), dtype=np.float32))
        empty_color = _read_only(np.zeros((grid, grid), dtype=np.float32))
        empty_mask = _read_only(np.zeros((grid, grid), dtype=np.bool_))
        metadata = dict(frame_index=int(source.depth_frame_index),
                        color_frame_index=int(source.color_frame_index),
                        timestamp_us=int(source.depth_timestamp_us), roi=roi)
        if roi is None:
            return FrameAssessment(FrameQualityStatus.ROI_REQUIRED, **metadata,
                                   valid_depth_fraction=0., valid_depth_samples=0, focus_score=0.,
                                   depth_signature_m=empty_depth, intensity_signature=empty_color,
                                   valid_signature=empty_mask)

        if roi.width < grid or roi.height < grid:
            # Avoid counting repeated sample coordinates as independent pixels.
            return FrameAssessment(FrameQualityStatus.INSUFFICIENT_DEPTH, **metadata,
                                   valid_depth_fraction=0., valid_depth_samples=0,
                                   focus_score=0., depth_signature_m=empty_depth,
                                   intensity_signature=empty_color, valid_signature=empty_mask)

        dy = _axis(roi.y, roi.height, grid)
        dx = _axis(roi.x, roi.width, grid)
        sampled = depth[np.ix_(dy, dx)]
        metric = sampled.astype(np.float32) * float(scale)
        cfg = self.config
        valid = (sampled != 0) & (sampled != 65535) & (metric >= cfg.min_depth_m) & (metric <= cfg.max_depth_m)
        metric = np.where(valid, metric, 0.0)
        n_valid = int(np.count_nonzero(valid))
        valid_fraction = n_valid / sampled.size

        # Approximate RGB crop only for a texture/focus proxy; *no* D2C alignment claim.
        cy = np.minimum(rgb.shape[0] - 1, (dy.astype(np.float64) + 0.5) * rgb.shape[0] / depth.shape[0]).astype(np.intp)
        cx = np.minimum(rgb.shape[1] - 1, (dx.astype(np.float64) + 0.5) * rgb.shape[1] / depth.shape[1]).astype(np.intp)
        rgb_sample = rgb[np.ix_(cy, cx)].astype(np.float32)
        gray = (0.299 * rgb_sample[:, :, 0] + 0.587 * rgb_sample[:, :, 1]
                + 0.114 * rgb_sample[:, :, 2])
        lap = (gray[1:-1, :-2] + gray[1:-1, 2:] + gray[:-2, 1:-1]
               + gray[2:, 1:-1] - 4.0 * gray[1:-1, 1:-1])
        focus = float(np.var(lap))
        status = FrameQualityStatus.OK
        if n_valid < cfg.min_valid_samples or valid_fraction < cfg.min_valid_fraction:
            status = FrameQualityStatus.INSUFFICIENT_DEPTH
        elif cfg.min_focus_score > 0 and focus < cfg.min_focus_score:
            status = FrameQualityStatus.LOW_FOCUS
        return FrameAssessment(status, **metadata, valid_depth_fraction=valid_fraction,
                               valid_depth_samples=n_valid, focus_score=focus,
                               depth_signature_m=_read_only(metric),
                               intensity_signature=_read_only(gray), valid_signature=_read_only(valid))
