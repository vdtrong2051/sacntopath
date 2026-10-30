"""GD2-09.06: pure camera lifecycle state machine, no Qt or SDK.

A failure is terminal only after the worker has exited and native cleanup
has had a chance to finish. CAPTURING is an exclusive in-memory RAW acquisition.
"""
from __future__ import annotations

from scantopath.modules.capture.domain.models import CameraState


class CameraLifecycle:
    """Single-session state machine, owned by one presentation controller."""

    def __init__(self) -> None:
        self._state = CameraState.IDLE
        self._error_code: str | None = None

    @property
    def state(self) -> CameraState:
        return self._state

    @property
    def error_code(self) -> str | None:
        return self._error_code

    def start(self) -> bool:
        """Reserve the single camera slot; caller then creates its worker."""
        if self._state not in (CameraState.IDLE, CameraState.CLOSED, CameraState.FAILED):
            return False
        self._error_code = None
        self._state = CameraState.OPENING
        return True

    def opened(self) -> bool:
        if self._state is not CameraState.OPENING:
            return False
        self._state = CameraState.STREAMING
        return True

    def begin_capture(self) -> bool:
        if self._state is not CameraState.STREAMING or self._error_code is not None:
            return False
        self._state = CameraState.CAPTURING
        return True

    def capture_finished(self) -> bool:
        if self._state is not CameraState.CAPTURING or self._error_code is not None:
            return False
        self._state = CameraState.STREAMING
        return True

    def stop(self) -> bool:
        if self._state not in (CameraState.OPENING, CameraState.STREAMING, CameraState.CAPTURING):
            return False
        self._state = CameraState.STOPPING
        return True

    def record_failure(self, code: str) -> None:
        if not isinstance(code, str) or not code or not code.isascii() or not all(
            c.isupper() or c.isdigit() or c == "_" for c in code
        ):
            raise ValueError("failure must be an uppercase ASCII error code")
        if self._state not in (
            CameraState.OPENING, CameraState.STREAMING, CameraState.CAPTURING, CameraState.STOPPING
        ):
            raise RuntimeError("cannot fail without an active camera session")
        # First failure is authoritative: later cleanup warnings do not overwrite it.
        if self._error_code is None:
            self._error_code = code

    def finished(self) -> CameraState:
        """Only call AFTER QThread is no longer running and wait(0) succeeds."""
        old = self._state
        if old not in (CameraState.OPENING, CameraState.STREAMING, CameraState.CAPTURING, CameraState.STOPPING):
            raise RuntimeError("no active worker to finalize")
        if self._error_code is None and old is not CameraState.STOPPING:
            self._error_code = "WORKER_UNEXPECTED_EXIT"
        self._state = (
            CameraState.FAILED if self._error_code is not None else CameraState.CLOSED
        )
        return self._state
