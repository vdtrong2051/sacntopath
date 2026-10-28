"""Minimal fixture-render scene protocol; no VTK or Qt imports."""
from __future__ import annotations
from typing import Protocol


class FixtureScenePort(Protocol):
    @property
    def point_count(self) -> int: ...

    @property
    def renderer(self) -> object: ...

    def dispose(self) -> None: ...
