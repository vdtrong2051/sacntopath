"""GD2-09.07.1: conservative, NumPy-only foreground depth ROI suggestions.

This is not semantic object recognition, a pixel mask or a camera pose.
Input depths remain in their native, unaligned depth grid (Y16, meters/unit).
The optional near-surface heuristic can reject clutter/flat scenes; operators
must use manual ROI in such cases (the manual UI belongs to GD2-09.07.2).
"""
from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from math import isfinite

import numpy as np

from scantopath.modules.capture.domain.models import DepthRoi, RoiSource


class DetectionStatus(str, Enum):
    OK = "ok"
    NO_VALID_DEPTH = "no_valid_depth"
    LOW_CONTRAST = "low_contrast"
    NO_CANDIDATE = "no_candidate"
    AMBIGUOUS = "ambiguous"
    LOW_CONFIDENCE = "low_confidence"


@dataclass(frozen=True, slots=True)
class DepthBboxConfig:
    """Heuristic parameters, not calibrated object-confidence probabilities."""

    min_depth_m: float = 0.18
    max_depth_m: float = 2.5
    foreground_quantile: float = 2.0
    background_quantile: float = 80.0
    foreground_band_m: float = 0.16
    min_contrast_m: float = 0.10
    sample_step: int = 4
    min_valid_samples: int = 64
    min_component_samples: int = 20
    max_component_coverage: float = 0.60
    ambiguity_ratio: float = 0.80
    min_confidence: float = 0.55
    max_candidates: int = 5

    def __post_init__(self) -> None:
        positives = (
            "min_depth_m", "max_depth_m", "foreground_band_m",
            "min_contrast_m",
        )
        for name in positives:
            value = getattr(self, name)
            if type(value) not in (int, float) or not isfinite(value) or value <= 0:
                raise ValueError(f"invalid {name}")
        if self.max_depth_m <= self.min_depth_m:
            raise ValueError("max_depth_m must exceed min_depth_m")
        lo, hi = self.foreground_quantile, self.background_quantile
        if (type(lo) not in (float, int) or type(hi) not in (float, int)
                or not isfinite(lo) or not isfinite(hi)
                or not 0.0 < lo < hi < 100.0):
            raise ValueError("invalid depth quantiles")
        for name in ("sample_step", "min_valid_samples", "min_component_samples", "max_candidates"):
            value = getattr(self, name)
            if type(value) is not int or value < 1:
                raise ValueError(f"invalid {name}")
        if self.sample_step > 16 or self.max_candidates > 64:
            raise ValueError("sampling/candidate limit exceeded")
        for name in ("max_component_coverage", "ambiguity_ratio", "min_confidence"):
            value = getattr(self, name)
            if (type(value) not in (float, int) or not isfinite(value)
                    or not 0.0 < value <= 1.0):
                raise ValueError(f"invalid {name}")


@dataclass(frozen=True, slots=True)
class DepthCandidate:
    roi: DepthRoi
    sampled_area: int
    sampled_fraction: float


@dataclass(frozen=True, slots=True)
class DepthDetection:
    status: DetectionStatus
    roi: DepthRoi | None
    confidence: float
    candidates: tuple[DepthCandidate, ...]
    valid_samples: int

    @property
    def usable(self) -> bool:
        return self.status is DetectionStatus.OK and self.roi is not None


def _connected_boxes(mask: np.ndarray, step: int, height: int, width: int):
    """Run-length 4-connected components, no scipy/cv2 dependency.

    Every sample represents a step-sized cell in the original depth grid.
    Component area is in *sampled cells*, not falsely precise pixel counts.
    """
    parents: list[int] = []
    ranks: list[int] = []
    runs: list[tuple[int, int, int, int]] = []  # y, start, stop-excl, label
    previous: list[tuple[int, int, int]] = []

    def root(label: int) -> int:
        while parents[label] != label:
            parents[label] = parents[parents[label]]
            label = parents[label]
        return label

    def union(a: int, b: int) -> None:
        a, b = root(a), root(b)
        if a == b:
            return
        if ranks[a] < ranks[b]:
            a, b = b, a
        parents[b] = a
        if ranks[a] == ranks[b]:
            ranks[a] += 1

    for y, row in enumerate(mask):
        padded = np.empty(row.size + 2, dtype=np.bool_)
        padded[0] = False
        padded[-1] = False
        padded[1:-1] = row
        starts = np.flatnonzero(~padded[:-1] & padded[1:])
        stops = np.flatnonzero(padded[:-1] & ~padded[1:])
        current: list[tuple[int, int, int]] = []
        j = 0
        for start_np, stop_np in zip(starts, stops):
            start, stop = int(start_np), int(stop_np)
            label = len(parents)
            parents.append(label)
            ranks.append(0)
            while j < len(previous) and previous[j][1] <= start:
                j += 1
            k = j
            while k < len(previous) and previous[k][0] < stop:
                union(label, previous[k][2])
                k += 1
            current.append((start, stop, label))
            runs.append((y, start, stop, label))
        previous = current

    components: dict[int, list[int]] = {}
    for y, start, stop, label in runs:
        group = components.setdefault(root(label), [0, start, y, stop, y + 1])
        group[0] += stop - start
        group[1] = min(group[1], start)
        group[2] = min(group[2], y)
        group[3] = max(group[3], stop)
        group[4] = max(group[4], y + 1)

    for cells, x0, y0, x1, y1 in components.values():
        left, top = x0 * step, y0 * step
        right, bottom = min(width, x1 * step), min(height, y1 * step)
        yield cells, DepthRoi(
            left, top, right - left, bottom - top,
            width, height, RoiSource.DEPTH_SUGGESTION,
        )


class DepthBboxDetector:
    def __init__(self, config: DepthBboxConfig | None = None) -> None:
        if config is not None and not isinstance(config, DepthBboxConfig):
            raise TypeError("config must be DepthBboxConfig")
        self.config = config if config is not None else DepthBboxConfig()

    def detect(self, depth_u16: np.ndarray, depth_scale_m_per_unit: float) -> DepthDetection:
        if (not isinstance(depth_u16, np.ndarray)
                or depth_u16.ndim != 2 or depth_u16.dtype != np.uint16
                or not all(dim > 0 for dim in depth_u16.shape)
                or depth_u16.size > 32_000_000):
            raise ValueError("depth must be nonempty uint16 HxW")
        if (type(depth_scale_m_per_unit) not in (float, int)
                or not isfinite(depth_scale_m_per_unit)
                or depth_scale_m_per_unit <= 0):
            raise ValueError("invalid depth scale")

        cfg = self.config
        height, width = depth_u16.shape
        sampled = depth_u16[::cfg.sample_step, ::cfg.sample_step]
        metric = sampled.astype(np.float32) * float(depth_scale_m_per_unit)
        valid = ((sampled != 0) & (sampled != 65535)
                 & (metric >= cfg.min_depth_m) & (metric <= cfg.max_depth_m))
        valid_count = int(valid.sum())
        if valid_count < cfg.min_valid_samples:
            return DepthDetection(DetectionStatus.NO_VALID_DEPTH, None, 0.0, (), valid_count)

        values = metric[valid]
        near = float(np.percentile(values, cfg.foreground_quantile))
        far = float(np.percentile(values, cfg.background_quantile))
        contrast = far - near
        if contrast < cfg.min_contrast_m:
            return DepthDetection(DetectionStatus.LOW_CONTRAST, None, 0.0, (), valid_count)

        foreground = valid & (metric <= near + cfg.foreground_band_m)
        all_cells = sampled.size
        boxes = []
        for cells, roi in _connected_boxes(foreground, cfg.sample_step, height, width):
            fraction = cells / all_cells
            if (cells >= cfg.min_component_samples
                    and fraction <= cfg.max_component_coverage):
                boxes.append(DepthCandidate(roi, cells, fraction))
        boxes.sort(key=lambda candidate: (-candidate.sampled_area,
                                          candidate.roi.y, candidate.roi.x))
        candidates = tuple(boxes[:cfg.max_candidates])
        if not candidates:
            return DepthDetection(DetectionStatus.NO_CANDIDATE, None, 0.0, (), valid_count)
        if len(boxes) > 1 and boxes[1].sampled_area >= boxes[0].sampled_area * cfg.ambiguity_ratio:
            return DepthDetection(DetectionStatus.AMBIGUOUS, None, 0.0, candidates, valid_count)

        dominant = boxes[0]
        # Engineering heuristic, NOT a statistical probability or semantic confidence.
        size_term = min(1.0, dominant.sampled_area / (cfg.min_component_samples * 4))
        separation = min(1.0, contrast / (cfg.min_contrast_m * 3))
        dominance = (1.0 if len(boxes) == 1 else
                     min(1.0, (dominant.sampled_area - boxes[1].sampled_area)
                         / dominant.sampled_area))
        confidence = round(min(0.95, 0.38 + 0.25 * size_term + 0.2 * separation
                               + 0.1 * dominance), 3)
        if confidence < cfg.min_confidence:
            return DepthDetection(DetectionStatus.LOW_CONFIDENCE, None, confidence,
                                  candidates, valid_count)
        return DepthDetection(DetectionStatus.OK, dominant.roi, confidence,
                              candidates, valid_count)
