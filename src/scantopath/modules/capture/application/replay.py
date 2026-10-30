"""09.02: read-only RAW-v2 replay orchestration, independent of SQLite/Qt."""
from __future__ import annotations

from scantopath.acquisition.raw_rgbd import RawRgbdCapture

from .contracts import CaptureContext
from .ports import RawReplayPort


class RawReplayError(RuntimeError):
    """Stable, non-sensitive failure suitable for presentation at 09.04."""

    def __init__(self, code: str, message: str) -> None:
        self.code = code
        super().__init__(message)


class RawReplayService:
    def __init__(self, reader: RawReplayPort) -> None:
        self._reader = reader

    def load(self, context: CaptureContext) -> RawRgbdCapture:
        if not isinstance(context, CaptureContext):
            raise TypeError("context must be CaptureContext")
        try:
            capture_id = context.require_replay_capture_id()
        except ValueError as exc:
            raise RawReplayError("CAPTURE_ID_REQUIRED", "Chưa chọn bản thu để phát lại.") from exc

        packet = self._reader.load(context)
        if not isinstance(packet, RawRgbdCapture):
            raise RawReplayError("INVALID_REPLAY_RESULT", "Nguồn phát lại không trả RAW v2 hợp lệ.")
        metadata = packet.metadata
        if (metadata.schema_version != 2 or metadata.capture_id != capture_id
                or metadata.session_id != context.session_id
                or metadata.specimen_id != context.specimen_id):
            raise RawReplayError("CAPTURE_CONTEXT_MISMATCH", "RAW không thuộc phiên quét đã chọn.")
        return packet
