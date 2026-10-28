"""Deterministic, unit-unknown synthetic geometry; never a measured specimen."""
from __future__ import annotations
from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class FixtureCloud:
    points: tuple[tuple[float, float, float], ...]
    source: str = "synthetic_08_02"
    coordinate_frame: str = "fixture_local"
    units: str | None = None

    @property
    def point_count(self) -> int:
        return len(self.points)


FIVE_POINT_FIXTURE = FixtureCloud((
    (0.0, 0.0, 0.0), (0.25, 0.0, 0.0), (0.0, 0.25, 0.0),
    (0.0, 0.0, 0.25), (0.25, 0.25, 0.25),
))
