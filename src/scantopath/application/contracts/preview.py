"""UXH-01.1: renderer/Qt-free preview transport contract.

A PreviewReceipt denotes a temporary display transport, never an artifact or a
certification of measurement accuracy. Keep the GD2-10 exception codes stable.
"""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path


class GeometryPreviewError(ValueError):
    def __init__(self, code: str):
        self.code = code
        super().__init__(code)


@dataclass(frozen=True, slots=True)
class PreviewReceipt:
    path: Path
    capture_id: str
    xyz_points: int
    colored_points: int
    ply_sha256: str
    frame: str = "depth_optical"
    units: str = "m"
    status: str = "PROVISIONAL_NOT_METRIC_VALIDATED"
