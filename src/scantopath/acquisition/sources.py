"""Capture adapters; SyntheticSource never represents a physical measurement."""
from dataclasses import dataclass
from typing import Protocol
import numpy as np
from scantopath.domain.models import Intrinsics, CaptureKind


@dataclass(frozen=True)
class FrameBundle:
    rgb: np.ndarray  # uint8 HxWx3
    depth: np.ndarray  # uint16 HxW
    intrinsics: Intrinsics
    scale_m_per_unit: float
    kind: CaptureKind
    camera_model: str


class CaptureSource(Protocol):
    def capture(self) -> FrameBundle: ...


class SyntheticSource:
    """Deterministic fixture for pipeline/storage tests, not real depth data."""
    def capture(self) -> FrameBundle:
        h, w = 48, 64
        y, x = np.indices((h, w))
        mask = ((x-w//2)**2 / 21**2 + (y-h//2)**2 / 15**2) <= 1
        depth = np.where(mask, 1000 + ((x-w//2)**2 // 40), 0).astype(np.uint16)
        rgb = np.zeros((h, w, 3), dtype=np.uint8)
        rgb[mask] = [80, 160, 230]
        return FrameBundle(
            rgb=rgb, depth=depth,
            intrinsics=Intrinsics(fx=55.0, fy=55.0, cx=31.5, cy=23.5, width=w, height=h),
            scale_m_per_unit=0.001, kind=CaptureKind.SYNTHETIC,
            camera_model="SYNTHETIC_FIXTURE_NOT_A_SENSOR",
        )


class OrbbecSDKv2Source:
    """Integration boundary: intentionally not a pretend working Gemini 2 driver."""
    def capture(self) -> FrameBundle:
        raise NotImplementedError(
            "Requires a tested OrbbecSDK v2 C++ native adapter, firmware check, "
            "stream alignment, intrinsics and depth-scale validation on Gemini 2."
        )
