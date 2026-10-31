"""UXH-01.1: production wiring for a single temporary XYZRGB Preview."""
from __future__ import annotations

from scantopath.application.geometry_preview import PreviewGeometryUseCase
from scantopath.modules.capture.application.decoding import RgbdDecoder
from scantopath.modules.capture.application.replay import RawReplayService
from scantopath.modules.capture.infrastructure.jpeg_codec import PillowMjpegDecoder
from scantopath.modules.capture.infrastructure.raw_reader import RawReaderAdapter
from scantopath.modules.capture.infrastructure.raw_snapshot import snapshot_capture
from scantopath.modules.geometry.application.replay_geometry import ReplayGeometryService
from scantopath.modules.geometry.infrastructure.preview_ply_writer import (
    MAX_PREVIEW_BYTES, MAX_PREVIEW_VERTICES, write_preview_ply,
)


def build_preview_use_case() -> PreviewGeometryUseCase:
    """One production composition seam; no camera, Qt or VTK runtime opened."""
    return PreviewGeometryUseCase(
        snapshot_capture,
        ReplayGeometryService(
            RawReplayService(RawReaderAdapter()),
            RgbdDecoder(PillowMjpegDecoder()),
        ),
        write_preview_ply,
    )
