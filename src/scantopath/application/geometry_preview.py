"""UXH-01.1: Qt/VTK/SQLite-free application use case for one RAW Preview.

This orchestrator invokes injected ports; it does not open resources itself.
Do not use the PreviewReceipt as a certified persistent ProcessingRun artifact.
"""
from __future__ import annotations

from pathlib import Path
from typing import Callable, Protocol

from scantopath.application.contracts.preview import PreviewReceipt
from scantopath.modules.capture.application.contracts import CaptureContext
from scantopath.modules.geometry.application.service import SingleViewXYZRGB


class ReplayGeometryPort(Protocol):
    def process(self, context: CaptureContext) -> SingleViewXYZRGB: ...


class PreviewGeometryUseCase:
    def __init__(
        self,
        snapshot: Callable[[CaptureContext, Path], CaptureContext],
        replay_geometry: ReplayGeometryPort,
        write_ply: Callable[[SingleViewXYZRGB, Path], PreviewReceipt],
    ) -> None:
        if not all(callable(v) for v in (snapshot, write_ply)) or not callable(
            getattr(replay_geometry, "process", None)
        ):
            raise TypeError("Expected snapshot, replay_geometry and PLY writer ports")
        self._snapshot = snapshot
        self._replay_geometry = replay_geometry
        self._write_ply = write_ply

    def process(
        self, context: CaptureContext, scratch_root: Path
    ) -> tuple[PreviewReceipt, SingleViewXYZRGB]:
        if not isinstance(context, CaptureContext):
            raise TypeError("Expected CaptureContext")
        capture_id = context.require_replay_capture_id()
        root = Path(scratch_root)
        snapshot_context = self._snapshot(context, root / "snapshot")
        geometry = self._replay_geometry.process(snapshot_context)
        receipt = self._write_ply(geometry, root / f"capture_{capture_id}_preview.ply")
        return receipt, geometry
