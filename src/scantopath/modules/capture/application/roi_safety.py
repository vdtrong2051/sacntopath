"""HS-01.4: conservative depth-ROI acquisition guard (not object segmentation).

Native depth coordinates and depth scale only. Never opens a device, writes RAW,
calculates a pose, or assumes a rectangle accurately masks the object.
"""
from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from math import isfinite

import numpy as np

from scantopath.modules.capture.domain.models import DepthRoi, RoiSource


class RoiSafetyReason(str, Enum):
    OK_MANUAL = 'ROI_MANUAL_VALID_PROXY'
    OK_SUGGESTED = 'ROI_SUGGESTED_VALID_PROXY'
    ROI_REQUIRED = 'ROI_REQUIRED'
    ROI_GRID_MISMATCH = 'ROI_GRID_MISMATCH'
    ROI_TOO_SMALL = 'ROI_TOO_SMALL'
    ROI_TOO_WIDE = 'ROI_TOO_WIDE'
    ROI_TOO_LARGE = 'ROI_TOO_LARGE'
    ROI_NEAR_BORDER = 'ROI_NEAR_BORDER'
    ROI_DEPTH_INSUFFICIENT = 'ROI_DEPTH_INSUFFICIENT'
    DEPTH_TOO_NEAR = 'DEPTH_TOO_NEAR'
    DEPTH_TOO_FAR = 'DEPTH_TOO_FAR'
    FRAME_INVALID = 'ROI_FRAME_INVALID'


@dataclass(frozen=True, slots=True)
class RoiSafetyConfig:
    # Operator acceptance guard; 0.20 m is NOT a certified SDK performance value.
    min_depth_m: float = 0.20
    max_depth_m: float = 2.50
    min_width_px: int = 20
    min_height_px: int = 20
    max_width_fraction: float = 0.75
    max_height_fraction: float = 0.85
    max_area_fraction: float = 0.48
    border_margin_fraction: float = 0.01
    min_valid_fraction: float = 0.30
    min_valid_samples: int = 32
    sample_grid: int = 16
    # Reject a nearby obstacle occupying a significant part of a ROI.
    near_depth_fraction_limit: float = 0.15

    def __post_init__(self) -> None:
        for name in ('min_depth_m','max_depth_m','max_width_fraction','max_height_fraction',
                     'max_area_fraction','border_margin_fraction','min_valid_fraction',
                     'near_depth_fraction_limit'):
            x = getattr(self, name)
            if type(x) not in (int,float) or not isfinite(x):
                raise ValueError('invalid ' + name)
        if not (0 < self.min_depth_m < self.max_depth_m <= 50):
            raise ValueError('invalid depth limits')
        for name in ('max_width_fraction','max_height_fraction','max_area_fraction','min_valid_fraction'):
            if not 0 < getattr(self, name) <= 1:
                raise ValueError('invalid ' + name)
        if not (0 <= self.border_margin_fraction < .10 and
                0 <= self.near_depth_fraction_limit <= 1):
            raise ValueError('invalid safety fraction')
        for name in ('min_width_px','min_height_px','min_valid_samples','sample_grid'):
            if type(getattr(self, name)) is not int or getattr(self, name) <= 0:
                raise ValueError('invalid ' + name)
        if not (4 <= self.sample_grid <= 64 and self.min_valid_samples <= self.sample_grid**2):
            raise ValueError('invalid sample budget')


@dataclass(frozen=True, slots=True)
class RoiSafetyResult:
    safe_to_propose: bool
    reason: RoiSafetyReason
    source: str
    width_fraction: float = 0.0
    area_fraction: float = 0.0
    valid_fraction: float = 0.0
    median_depth_m: float | None = None
    sampled: int = 0


class RoiSafetyEvaluator:
    """Cheap conservative guard. A PASS is not an object-detection PASS."""

    def __init__(self, config: RoiSafetyConfig | None = None):
        if config is not None and not isinstance(config, RoiSafetyConfig):
            raise TypeError('config must be RoiSafetyConfig')
        self.config = config if config is not None else RoiSafetyConfig()

    def evaluate(self, frame, roi: DepthRoi | None) -> RoiSafetyResult:
        cfg = self.config
        if roi is None:
            return RoiSafetyResult(False, RoiSafetyReason.ROI_REQUIRED, 'none')
        if not isinstance(roi, DepthRoi):
            raise TypeError('roi must be a DepthRoi or None')
        src = 'manual' if roi.source is RoiSource.MANUAL else 'depth_suggestion'
        def ret(reason, *, width=0., area=0., valid=0., median=None, sampled=0):
            return RoiSafetyResult(reason in (RoiSafetyReason.OK_MANUAL,
                                               RoiSafetyReason.OK_SUGGESTED),
                                   reason, src, width, area, valid, median, sampled)
        try:
            depth = frame.depth_u16
            source = frame.source
            scale = source.depth_scale_m_per_unit
            if (not isinstance(depth, np.ndarray) or depth.dtype != np.uint16
                    or depth.ndim != 2 or depth.size == 0
                    or type(scale) not in (int, float) or not isfinite(scale) or scale <= 0):
                return ret(RoiSafetyReason.FRAME_INVALID)
        except (AttributeError, TypeError, ValueError):
            return ret(RoiSafetyReason.FRAME_INVALID)
        h, w = depth.shape
        if ((roi.frame_width, roi.frame_height) != (w, h) or
                (source.depth_width, source.depth_height) != (w, h)):
            return ret(RoiSafetyReason.ROI_GRID_MISMATCH)
        wf, hf = roi.width/w, roi.height/h
        af = wf * hf
        kw = dict(width=wf, area=af)
        if roi.width < cfg.min_width_px or roi.height < cfg.min_height_px:
            return ret(RoiSafetyReason.ROI_TOO_SMALL, **kw)
        if wf > cfg.max_width_fraction:
            return ret(RoiSafetyReason.ROI_TOO_WIDE, **kw)
        if hf > cfg.max_height_fraction or af > cfg.max_area_fraction:
            return ret(RoiSafetyReason.ROI_TOO_LARGE, **kw)
        if (roi.x < max(1, round(w * cfg.border_margin_fraction))
                or roi.y < max(1, round(h * cfg.border_margin_fraction))
                or roi.x + roi.width > w - max(1, round(w * cfg.border_margin_fraction))
                or roi.y + roi.height > h - max(1, round(h * cfg.border_margin_fraction))):
            return ret(RoiSafetyReason.ROI_NEAR_BORDER, **kw)
        g = cfg.sample_grid
        xs = roi.x + np.minimum(roi.width-1, ((np.arange(g)+.5)*roi.width/g).astype(np.intp))
        ys = roi.y + np.minimum(roi.height-1, ((np.arange(g)+.5)*roi.height/g).astype(np.intp))
        raw = depth[np.ix_(ys, xs)]
        nonzero = (raw != 0) & (raw != 65535)
        # No values => no confident claim about being outside range.
        if np.count_nonzero(nonzero) < cfg.min_valid_samples:
            return ret(RoiSafetyReason.ROI_DEPTH_INSUFFICIENT, **kw, sampled=int(np.count_nonzero(nonzero)))
        distances = raw[nonzero].astype(np.float32) * float(scale)
        near_fraction = np.count_nonzero(distances < cfg.min_depth_m) / raw.size
        if near_fraction > cfg.near_depth_fraction_limit:
            return ret(RoiSafetyReason.DEPTH_TOO_NEAR, **kw,
                       sampled=len(distances), median=float(np.median(distances)))
        valid = distances[(distances >= cfg.min_depth_m) & (distances <= cfg.max_depth_m)]
        fraction = float(valid.size / raw.size)
        median = float(np.median(valid)) if valid.size else None
        kwargs = dict(**kw, valid=fraction, median=median, sampled=int(valid.size))
        if valid.size < cfg.min_valid_samples or fraction < cfg.min_valid_fraction:
            if distances.size and np.median(distances) > cfg.max_depth_m:
                return ret(RoiSafetyReason.DEPTH_TOO_FAR, **kwargs)
            return ret(RoiSafetyReason.ROI_DEPTH_INSUFFICIENT, **kwargs)
        return ret(RoiSafetyReason.OK_MANUAL if roi.source is RoiSource.MANUAL
                   else RoiSafetyReason.OK_SUGGESTED, **kwargs)
