
"""GD2-09.05: Qt live acquisition QThread with a one-frame mailbox.

This is NOT the 09.06 UI lifecycle controller. Call stop() before teardown.
"""
from __future__ import annotations

from collections.abc import Callable
from threading import Event, Lock

from PySide6.QtCore import QThread, Signal

from scantopath.modules.capture.application.live_stream import (
    LiveCameraError,
    LiveCaptureService,
    LiveRgbdFrame,
)


class LiveStreamWorker(QThread):
    camera_opened = Signal()

    # Wake-up only. Frame is NOT queued in Qt signals.
    frame_available = Signal()

    # Stable code, no raw SDK paths/details.
    failed = Signal(str)

    MAX_TIMEOUTS = 8

    def __init__(
        self,
        *,
        service_factory: Callable[[], LiveCaptureService],
        parent=None,
    ) -> None:
        super().__init__(parent)

        if not callable(service_factory):
            raise TypeError("service_factory required")

        self._service_factory = service_factory
        self._stop_event = Event()
        self._lock = Lock()

        self._latest: LiveRgbdFrame | None = None
        self._notice_pending = False

        self._published = 0
        self._dropped = 0

    def request_stop(self) -> None:
        """Thread-safe; native close happens only in run()'s finally block."""
        self._stop_event.set()

    def take_latest(self) -> LiveRgbdFrame | None:
        """Transfer the current newest frame only."""
        with self._lock:
            frame = self._latest
            self._latest = None
            self._notice_pending = False
            return frame

    def stats(self) -> tuple[int, int]:
        """(frames published, frames overwritten before consumption)."""
        with self._lock:
            return self._published, self._dropped

    def _publish(self, frame: LiveRgbdFrame) -> None:
        notify = False

        with self._lock:
            if self._latest is not None:
                self._dropped += 1

            self._latest = frame
            self._published += 1

            if not self._notice_pending:
                self._notice_pending = True
                notify = True

        if notify:
            self.frame_available.emit()

    def run(self) -> None:
        service: LiveCaptureService | None = None
        error: str | None = None

        try:
            if self._stop_event.is_set():
                return

            # Factory is called INSIDE worker thread.
            # Presentation has no Infrastructure imports.
            service = self._service_factory()

            if not isinstance(service, LiveCaptureService):
                raise LiveCameraError("INVALID_SERVICE")

            service.open()

            if not self._stop_event.is_set():
                self.camera_opened.emit()

            consecutive_timeouts = 0

            while not self._stop_event.is_set():
                try:
                    frame = service.read_next(
                        per_attempt_timeout_ms=300
                    )

                except TimeoutError:
                    consecutive_timeouts += 1

                    if consecutive_timeouts >= self.MAX_TIMEOUTS:
                        raise LiveCameraError(
                            "READ_TIMEOUT"
                        ) from None

                    continue

                consecutive_timeouts = 0

                if self._stop_event.is_set():
                    break

                self._publish(frame)

        except LiveCameraError as exc:
            if not self._stop_event.is_set():
                error = exc.code

        except Exception:
            if not self._stop_event.is_set():
                error = "LIVE_UNEXPECTED_ERROR"

        finally:
            if service is not None:
                try:
                    service.close()
                except LiveCameraError as exc:
                    if error is None or exc.code == "DEVICE_PROCESS_CRASH":
                        error = exc.code
                except Exception:
                    if error is None:
                        error = "CLOSE_FAILED"

            if error is not None:
                self.failed.emit(error)
