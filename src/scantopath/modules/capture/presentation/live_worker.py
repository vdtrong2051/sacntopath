
"""GD2-09.05: Qt live acquisition QThread with a one-frame mailbox.

This is NOT the 09.06 UI lifecycle controller. Call stop() before teardown.
"""
from __future__ import annotations

from collections.abc import Callable
from threading import Event, Lock
from re import fullmatch

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
    keyframe_ready = Signal(object)  # RawRgbdCapture v2, owned bytes
    keyframe_failed = Signal(str)

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
        self._capture_request: tuple[str, str] | None = None
        self._capture_in_flight = False

    def request_stop(self) -> None:
        """Thread-safe; native close happens only in run()'s finally block."""
        self._stop_event.set()

    def request_keyframe(self, *, session_id: str, specimen_id: str) -> bool:
        """Queue ONE capture for the owner worker, never use the preview mailbox."""
        if any(not isinstance(v, str) or fullmatch(r"[A-Za-z0-9_-]+", v) is None
               for v in (session_id, specimen_id)):
            return False
        with self._lock:
            if (self._stop_event.is_set() or not self.isRunning() or
                    self._capture_request is not None or self._capture_in_flight):
                return False
            self._capture_request = (session_id, specimen_id)
            return True

    def _take_capture_request(self) -> tuple[str, str] | None:
        with self._lock:
            request = self._capture_request
            self._capture_request = None
            self._capture_in_flight = request is not None
            return request

    def _complete_capture_request(self) -> None:
        with self._lock:
            self._capture_in_flight = False

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
                request = self._take_capture_request()
                if request is not None:
                    try:
                        if self._stop_event.is_set():
                            break
                        packet = service.capture_keyframe(
                            session_id=request[0], specimen_id=request[1]
                        )
                        if not self._stop_event.is_set():
                            self.keyframe_ready.emit(packet)
                    except TimeoutError:
                        if not self._stop_event.is_set():
                            self.keyframe_failed.emit("CAPTURE_TIMEOUT")
                    except LiveCameraError as exc:
                        if exc.code in ("DEVICE_PROCESS_CRASH", "DEVICE_PROCESS_TIMEOUT",
                                        "READ_FAILED", "NOT_OPEN"):
                            raise
                        if not self._stop_event.is_set():
                            self.keyframe_failed.emit(exc.code)
                    except Exception:
                        if not self._stop_event.is_set():
                            self.keyframe_failed.emit("CAPTURE_FAILED")
                    finally:
                        self._complete_capture_request()
                    continue
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
            with self._lock:
                self._capture_request = None
                self._capture_in_flight = False
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
