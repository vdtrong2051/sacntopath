"""Small testable ports for later 09.02/09.05/09.08 implementation.

These definitions MUST NOT open camera, import Qt or touch a database. A native
packet is deliberately opaque until the 09.05 adapter validates its contract.
"""
from __future__ import annotations
from typing import Protocol, TYPE_CHECKING

from .contracts import CaptureContext

if TYPE_CHECKING:
    from scantopath.acquisition.raw_rgbd import RawRgbdCapture


class RawReplayPort(Protocol):
    def load(self, context: CaptureContext) -> "RawRgbdCapture": ...


class NativeCameraPort(Protocol):
    def open(self) -> None: ...
    def read_next(self, *, per_attempt_timeout_ms: int, max_attempts: int) -> object: ...
    def close(self) -> None: ...


class CapturePersistencePort(Protocol):
    def commit(self, context: CaptureContext, raw: "RawRgbdCapture") -> str: ...
