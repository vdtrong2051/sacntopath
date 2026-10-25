"""08.04 immutable, renderer-agnostic camera intent; no Qt, VTK or sensor pose.

Angles are degrees; pan uses fractions of the viewport; zoom is a display-only
multiplier. Neither the camera view nor axes is a metric/world transform.
"""
from __future__ import annotations

from dataclasses import dataclass, replace
import json
import math


@dataclass(frozen=True, slots=True)
class CameraView:
    azimuth: float = 0.0
    elevation: float = 0.0
    pan_x: float = 0.0
    pan_y: float = 0.0
    zoom: float = 1.0
    axes: bool = False

    def __post_init__(self) -> None:
        for name, cap in (("azimuth", 360.0), ("elevation", 80.0),
                          ("pan_x", 2.0), ("pan_y", 2.0)):
            value = getattr(self, name)
            if isinstance(value, bool) or not isinstance(value, (float, int)) or not math.isfinite(value) or abs(value) > cap:
                raise ValueError(f"Invalid camera {name}")
        if isinstance(self.zoom, bool) or not isinstance(self.zoom, (float, int)) or not math.isfinite(self.zoom) or not 0.15 <= self.zoom <= 30.0:
            raise ValueError("Invalid camera zoom")
        if type(self.axes) is not bool:
            raise ValueError("Invalid camera axes")

    def update(self, action: str, dx: float = 0.0, dy: float = 0.0) -> "CameraView":
        if type(action) is not str or action not in {"orbit", "pan", "zoom", "reset", "axes"}:
            raise ValueError("Unsupported camera action")
        for value in (dx, dy):
            if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value) or abs(value) > 10000:
                raise ValueError("Invalid camera delta")
        if action == "orbit":
            return replace(self, azimuth=(self.azimuth + float(dx)) % 360.0,
                           elevation=max(-80.0, min(80.0, self.elevation + float(dy))))
        if action == "pan":
            return replace(self, pan_x=max(-2.0, min(2.0, self.pan_x + float(dx) / 600.0)),
                           pan_y=max(-2.0, min(2.0, self.pan_y + float(dy) / 600.0)))
        if action == "zoom":
            return replace(self, zoom=max(0.15, min(30.0, self.zoom * 1.25 ** max(-32.0, min(32.0, float(dx))))))
        if action == "reset":
            return CameraView(axes=self.axes)
        return replace(self, axes=not self.axes)

    def to_json(self) -> str:
        from dataclasses import asdict
        return json.dumps(asdict(self), separators=(",", ":"), allow_nan=False)

    @classmethod
    def from_json(cls, raw: str) -> "CameraView":
        if not isinstance(raw, str) or len(raw) > 1024:
            raise ValueError("Invalid camera payload size")
        data = json.loads(raw)
        if not isinstance(data, dict) or set(data) != set(cls.__dataclass_fields__):
            raise ValueError("Invalid camera payload fields")
        return cls(**data)
