"""HS-01.2 decision contracts. SELECT means *request a fresh RAW capture*, not saved.

No inferred 6DoF pose, no automatic RAW identity, no registration/overlap claim.
"""
from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from math import isfinite

from .frame_quality import FrameAssessment


class KeyframeDecision(str, Enum):
    SELECT = "SELECT"
    WAIT = "WAIT"
    REJECT = "REJECT"


class SelectionReason(str, Enum):
    SELECT_FIRST = "SELECT_FIRST"
    SELECT_NOVEL = "SELECT_NOVEL"
    ROI_REQUIRED = "ROI_REQUIRED"
    INSUFFICIENT_DEPTH = "INSUFFICIENT_DEPTH"
    LOW_FOCUS = "LOW_FOCUS"
    STABILIZING = "STABILIZING"
    MOTION_TOO_HIGH = "MOTION_TOO_HIGH"
    LOW_INTERFRAME_OVERLAP = "LOW_INTERFRAME_OVERLAP"
    LOW_REFERENCE_OVERLAP = "LOW_REFERENCE_OVERLAP"
    DUPLICATE_VIEW_PROXY = "DUPLICATE_VIEW_PROXY"
    COOLDOWN = "COOLDOWN"
    CAPTURE_PENDING = "CAPTURE_PENDING"
    STALE_FRAME = "STALE_FRAME"


@dataclass(frozen=True, slots=True)
class KeyframeSelectionConfig:
    cooldown_us: int = 900_000
    # Median *proxy* of depth difference at fixed sampled image locations.
    max_interframe_depth_change_m: float = 0.07
    min_interframe_overlap_fraction: float = 0.30
    min_reference_overlap_fraction: float = 0.30
    min_novelty_score: float = 0.10
    novelty_depth_normalizer_m: float = 0.20
    # R1 conservative defaults; not calibrated against the operator's RAW set.
    depth_noise_floor_m: float = 0.012
    color_noise_floor_gray: float = 14.0
    near_surface_band_m: float = 0.10
    min_near_surface_samples: int = 12
    max_signature_shift_cells: int = 1
    silhouette_noise_fraction: float = 0.10

    def __post_init__(self) -> None:
        if type(self.cooldown_us) is not int or not 0 <= self.cooldown_us <= 60_000_000:
            raise ValueError("invalid cooldown_us")
        for name in ("max_interframe_depth_change_m", "min_interframe_overlap_fraction",
                     "min_reference_overlap_fraction", "min_novelty_score", "novelty_depth_normalizer_m",
                     "depth_noise_floor_m", "color_noise_floor_gray", "near_surface_band_m",
                     "silhouette_noise_fraction"):
            value = getattr(self, name)
            if type(value) not in (int, float) or not isfinite(value):
                raise ValueError(f"invalid {name}")
        if not (0 < self.max_interframe_depth_change_m <= 2 and
                0 < self.novelty_depth_normalizer_m <= 5):
            raise ValueError("invalid distance threshold")
        if not (0 < self.min_interframe_overlap_fraction <= 1 and
                0 < self.min_reference_overlap_fraction <= 1 and
                0 < self.min_novelty_score <= 1):
            raise ValueError("invalid fraction/novelty threshold")
        if not (0 <= self.depth_noise_floor_m <= 0.10
                and 0 <= self.color_noise_floor_gray <= 64
                and 0 < self.near_surface_band_m <= 1
                and 0 <= self.silhouette_noise_fraction <= 0.5):
            raise ValueError("invalid R1 noise/foreground settings")
        if (type(self.min_near_surface_samples) is not int or
                not 4 <= self.min_near_surface_samples <= 128):
            raise ValueError("invalid min_near_surface_samples")
        if (type(self.max_signature_shift_cells) is not int or
                not 0 <= self.max_signature_shift_cells <= 2):
            raise ValueError("invalid max_signature_shift_cells")


@dataclass(frozen=True, slots=True)
class KeyframeSelectionResult:
    decision: KeyframeDecision
    reason_code: SelectionReason
    frame_index: int
    timestamp_us: int
    assessment: FrameAssessment
    motion_proxy_m: float | None = None
    novelty_score: float | None = None

    @property
    def should_capture(self) -> bool:
        return self.decision is KeyframeDecision.SELECT
