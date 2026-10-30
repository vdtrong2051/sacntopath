"""GD2-09.08.3: compose one live keyframe acquisition and registered RAW-v2 write.

Application layer only: no Qt, SDK, filesystem, or database import.
The caller owns camera.open()/close() and prevents overlapping camera owners.
"""
from __future__ import annotations

from dataclasses import dataclass
import hashlib
from typing import Protocol

from scantopath.acquisition.raw_rgbd import RawRgbdCapture
from scantopath.modules.capture.application.capture_service import (
    CaptureCommitError, CaptureCommitService,
)
from scantopath.modules.capture.application.contracts import CaptureContext
from scantopath.modules.capture.application.live_stream import LiveCameraError


class CapturePipelineError(RuntimeError):
    """Stable failure code. The original exception remains in __cause__."""

    def __init__(self, code: str) -> None:
        self.code = code
        super().__init__(code)


class KeyframeAcquisitionPort(Protocol):
    def capture_next_raw(self, *, session_id: str, specimen_id: str) -> RawRgbdCapture: ...


class CaptureContextPreflightPort(Protocol):
    def validate_context(self, context: CaptureContext) -> None: ...


@dataclass(frozen=True, slots=True)
class CaptureReceipt:
    capture_id: str
    color_frame_index: int
    depth_frame_index: int
    color_sha256: str
    depth_sha256: str
    color_timestamp_us: int
    depth_timestamp_us: int


class CapturePipelineService:
    """Acquire a fresh owned RAW frameset, then commit through the 09.08.2 port.

    Context is checked BEFORE a camera read. Prior acquired indices are
    remembered even if persistence later fails, preventing a stale retry from
    silently becoming a second keyframe. One instance represents one open
    camera session; create a new instance after a physical camera reopen.
    """

    def __init__(
        self,
        camera: KeyframeAcquisitionPort,
        persistence: CaptureCommitService,
        preflight: CaptureContextPreflightPort,
    ) -> None:
        self._camera = camera
        self._persistence = persistence
        self._preflight = preflight
        self._last_indices: tuple[int, int] | None = None
        self._seen_capture_ids: set[str] = set()

    def capture_and_commit(self, context: CaptureContext) -> CaptureReceipt:
        if not isinstance(context, CaptureContext):
            raise TypeError("context must be CaptureContext")
        if context.capture_id is not None:
            raise CapturePipelineError("NEW_CAPTURE_CONTEXT_REQUIRED")

        try:
            self._preflight.validate_context(context)
        except CaptureCommitError as exc:
            raise CapturePipelineError(exc.code) from exc
        except Exception as exc:
            raise CapturePipelineError("CAPTURE_PREFLIGHT_FAILED") from exc

        try:
            raw = self._camera.capture_next_raw(
                session_id=context.session_id,
                specimen_id=context.specimen_id,
            )
        except LiveCameraError as exc:
            raise CapturePipelineError(exc.code) from exc
        except TimeoutError as exc:
            raise CapturePipelineError("CAPTURE_TIMEOUT") from exc
        except Exception as exc:
            raise CapturePipelineError("KEYFRAME_ACQUISITION_FAILED") from exc

        if not isinstance(raw, RawRgbdCapture):
            raise CapturePipelineError("INVALID_KEYFRAME")
        meta = raw.metadata
        if (meta.schema_version != 2
                or meta.session_id != context.session_id
                or meta.specimen_id != context.specimen_id
                or meta.camera_pose is not None
                or meta.alignment_mode != "disabled"):
            raise CapturePipelineError("INVALID_KEYFRAME")

        indices = (meta.color.frame_index, meta.depth.frame_index)
        if (self._last_indices is not None
                and (indices[0] <= self._last_indices[0]
                     or indices[1] <= self._last_indices[1])):
            raise CapturePipelineError("STALE_KEYFRAME")
        if meta.capture_id in self._seen_capture_ids:
            raise CapturePipelineError("DUPLICATE_KEYFRAME_ID")
        self._last_indices = indices
        self._seen_capture_ids.add(meta.capture_id)

        try:
            committed_id = self._persistence.commit(context, raw)
        except CaptureCommitError as exc:
            # Storage may already contain a reservation OR a committed capture.
            # Never claim success and never implicitly retry the same Capture ID.
            raise CapturePipelineError(exc.code) from exc
        except Exception as exc:
            raise CapturePipelineError("CAPTURE_PERSISTENCE_FAILED") from exc
        if committed_id != meta.capture_id:
            raise CapturePipelineError("INVALID_PERSISTENCE_RESULT")

        return CaptureReceipt(
            capture_id=committed_id,
            color_frame_index=indices[0],
            depth_frame_index=indices[1],
            color_sha256=hashlib.sha256(raw.color_mjpeg).hexdigest(),
            depth_sha256=hashlib.sha256(raw.depth_y16_le).hexdigest(),
            color_timestamp_us=meta.color.timestamp_us,
            depth_timestamp_us=meta.depth.timestamp_us,
        )
