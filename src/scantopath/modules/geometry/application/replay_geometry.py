"""GD2-10.07.1: compose verified RAW replay, RGB-D decode and geometry.

This is a pure application seam: no SQLite, filesystem, Qt, VTK, camera,
or alternate RAW reader. The injected replay reader owns integrity checks;
Geometry does NOT authenticate caller-provided SHA-256 values.
"""
from __future__ import annotations

from hashlib import sha256
from typing import Protocol

import numpy as np

from scantopath.acquisition.raw_rgbd import RawRgbdCapture
from scantopath.domain.raw_rgbd import RawRgbdCaptureMetadataV2
from scantopath.modules.capture.application.contracts import CaptureContext
from scantopath.modules.capture.application.ports import RawReplayPort

from .service import GeometryService, SingleViewXYZRGB


class ReplayGeometryError(ValueError):
    """Boundary-only errors; existing Replay/Decode/Geometry errors propagate."""

    def __init__(self, code: str, message: str) -> None:
        self.code = code
        super().__init__(message)


class DecodedFramePort(Protocol):
    color_rgb: np.ndarray
    depth_u16: np.ndarray
    metadata: RawRgbdCaptureMetadataV2


class RgbdDecodePort(Protocol):
    def decode(self, packet: RawRgbdCapture) -> DecodedFramePort: ...


class ReplayGeometryService:
    """One explicit Capture -> one immutable single-view XYZRGB result.

    Wire real RawReplayService(RawReaderAdapter()) and
    RgbdDecoder(PillowMjpegDecoder()) at the composition boundary.
    """

    def __init__(self, replay: RawReplayPort, decoder: RgbdDecodePort) -> None:
        if not callable(getattr(replay, "load", None)) or not callable(
            getattr(decoder, "decode", None)
        ):
            raise TypeError("Expected replay.load and decoder.decode ports")
        self._replay = replay
        self._decoder = decoder

    def process(self, context: CaptureContext) -> SingleViewXYZRGB:
        if not isinstance(context, CaptureContext):
            raise ReplayGeometryError(
                "CAPTURE_CONTEXT_INVALID", "Expected CaptureContext"
            )
        if context.capture_id is None:
            raise ReplayGeometryError(
                "CAPTURE_ID_REQUIRED", "Explicit replay Capture ID required"
            )

        # The injected RAW reader owns manifest and payload verification.
        # Preserve its error code rather than relabeling it as geometry failure.
        packet = self._replay.load(context)
        if not isinstance(packet, RawRgbdCapture):
            raise ReplayGeometryError(
                "RAW_REPLAY_RESULT_INVALID", "Replay did not return RAW v2"
            )
        metadata = packet.metadata
        if (
            metadata.schema_version != 2
            or metadata.capture_id != context.capture_id
            or metadata.session_id != context.session_id
            or metadata.specimen_id != context.specimen_id
        ):
            raise ReplayGeometryError(
                "CAPTURE_CONTEXT_MISMATCH", "RAW lineage differs from selection"
            )

        # Do not assume the decoded RGB/depth grids are aligned.
        decoded = self._decoder.decode(packet)
        if (
            not isinstance(
                getattr(decoded, "metadata", None), RawRgbdCaptureMetadataV2
            )
            or decoded.metadata != metadata
            or not isinstance(getattr(decoded, "depth_u16", None), np.ndarray)
            or not isinstance(getattr(decoded, "color_rgb", None), np.ndarray)
        ):
            raise ReplayGeometryError(
                "DECODE_RESULT_INVALID", "Decoded frame or metadata mismatch"
            )

        depth = decoded.depth_u16
        color = decoded.color_rgb
        if (
            depth.dtype != np.uint16
            or depth.shape != (metadata.depth.height, metadata.depth.width)
            or not depth.flags.c_contiguous
            or color.dtype != np.uint8
            or color.shape != (metadata.color.height, metadata.color.width, 3)
            or not color.flags.c_contiguous
        ):
            raise ReplayGeometryError(
                "DECODE_RESULT_INVALID", "Decoded native grids are invalid"
            )

        # Provenance hashes computed from the packet delivered by replay.
        # They are not a substitute for the reader's manifest verification.
        source_hashes = {
            "color.mjpg": sha256(packet.color_mjpeg).hexdigest(),
            "depth.y16": sha256(packet.depth_y16_le).hexdigest(),
        }

        return GeometryService.process(
            depth_u16=depth,
            color_rgb=color,
            metadata=metadata,
            capture_id=context.capture_id,
            source_raw_sha256=source_hashes,
        )
