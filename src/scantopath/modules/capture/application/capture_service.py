"""GD2-09.08.2: persist an already acquired RAW v2 keyframe via a port.

No camera, Qt, SQLite or filesystem dependencies belong in this service.
"""
from __future__ import annotations

from scantopath.acquisition.raw_rgbd import RawRgbdCapture
from .contracts import CaptureContext
from .ports import CapturePersistencePort


class CaptureCommitError(RuntimeError):
    """Stable, presentation-safe failure code (not an SDK/OS exception string)."""

    def __init__(self, code: str) -> None:
        self.code = code
        super().__init__(code)


class CaptureCommitService:
    """Capture -> persistence boundary. Capture acquisition happens at 09.08.1."""

    def __init__(self, persistence: CapturePersistencePort) -> None:
        self._persistence = persistence

    def commit(self, context: CaptureContext, raw: RawRgbdCapture) -> str:
        if not isinstance(context, CaptureContext):
            raise TypeError("context must be CaptureContext")
        if not isinstance(raw, RawRgbdCapture):
            raise TypeError("raw must be RawRgbdCapture")
        meta = raw.metadata
        if (meta.schema_version != 2
                or meta.session_id != context.session_id
                or meta.specimen_id != context.specimen_id
                or (context.capture_id is not None and context.capture_id != meta.capture_id)):
            raise CaptureCommitError("CAPTURE_CONTEXT_MISMATCH")
        try:
            result = self._persistence.commit(context, raw)
        except CaptureCommitError:
            raise
        except Exception as exc:
            raise CaptureCommitError("CAPTURE_PERSISTENCE_FAILED") from exc
        if type(result) is not str or result != meta.capture_id:
            raise CaptureCommitError("INVALID_PERSISTENCE_RESULT")
        return result
