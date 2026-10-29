"""GD2-09.06: Qt-side lifecycle coordinator for the GD2-09.05 LiveStreamWorker.

Does not import camera infrastructure or modify existing workspaces. All public
methods must be called on the QObject's owning (normally GUI) thread.
Close a window only when safe_to_dispose is True; wiring that guard into the
ScanToPath shell is deferred until GD2-09.09.
"""
from __future__ import annotations

from collections.abc import Callable

from PySide6.QtCore import QObject, QThread, QTimer, Signal, Slot

from scantopath.modules.capture.application.lifecycle import CameraLifecycle
from scantopath.modules.capture.domain.models import CameraState
from .live_worker import LiveStreamWorker


class LiveCameraController(QObject):
    state_changed = Signal(object)      # CameraState
    frame_available = Signal()          # wake-up only; frame stays in mailbox
    failure = Signal(str)               # stable error code, never raw SDK text
    settled = Signal(object)            # CLOSED or FAILED, worker fully reaped
    shutdown_ready = Signal()           # safe to destroy controller/host

    def __init__(
        self,
        *,
        worker_factory: Callable[[], LiveStreamWorker],
        opening_timeout_ms: int = 15000,
        stopping_timeout_ms: int = 10000,
        parent: QObject | None = None,
    ) -> None:
        super().__init__(parent)
        if not callable(worker_factory):
            raise TypeError("worker_factory required")
        if type(opening_timeout_ms) is not int or opening_timeout_ms < 1:
            raise ValueError("opening_timeout_ms must be positive")
        if type(stopping_timeout_ms) is not int or stopping_timeout_ms < 1:
            raise ValueError("stopping_timeout_ms must be positive")
        self._worker_factory = worker_factory
        self._machine = CameraLifecycle()
        self._worker: LiveStreamWorker | None = None
        self._shutting_down = False
        self._finished_notified = False
        self._last_failure_sent: str | None = None

        self._opening_timer = QTimer(self)
        self._opening_timer.setSingleShot(True)
        self._opening_timer.setInterval(opening_timeout_ms)
        self._opening_timer.timeout.connect(self._opening_timed_out)

        self._stopping_timer = QTimer(self)
        self._stopping_timer.setSingleShot(True)
        self._stopping_timer.setInterval(stopping_timeout_ms)
        self._stopping_timer.timeout.connect(self._stopping_timed_out)

        self._reap_timer = QTimer(self)
        self._reap_timer.setInterval(10)
        self._reap_timer.timeout.connect(self._try_reap)

    def _assert_thread(self) -> None:
        if QThread.currentThread() != self.thread():
            raise RuntimeError("lifecycle controller API must run on the GUI thread")

    @property
    def state(self) -> CameraState:
        return self._machine.state

    @property
    def error_code(self) -> str | None:
        return self._machine.error_code

    @property
    def safe_to_dispose(self) -> bool:
        return self._worker is None

    @property
    def shutting_down(self) -> bool:
        return self._shutting_down

    def start(self) -> bool:
        """Non-blocking. Refuses duplicate opens and restarts before cleanup."""
        self._assert_thread()
        if self._shutting_down or self._worker is not None:
            return False
        if not self._machine.start():
            return False

        self._finished_notified = False
        self._last_failure_sent = None
        try:
            worker = self._worker_factory()
            if not isinstance(worker, LiveStreamWorker):
                raise TypeError("worker_factory must return LiveStreamWorker")
            if worker.isRunning():
                raise RuntimeError("worker already running")
            # Do not parent the worker to the controller: native release belongs
            # to the worker thread, and Qt must never delete a running QThread.
            self._worker = worker
            worker.camera_opened.connect(self._on_opened)
            worker.frame_available.connect(self._on_frame)
            worker.failed.connect(self._on_failed)
            worker.finished.connect(self._on_finished)
            self._opening_timer.start()
            self.state_changed.emit(self.state)
            worker.start()
        except Exception:
            # If QThread.start itself raises, no running thread may be discarded.
            worker = self._worker
            if worker is not None and worker.isRunning():
                self._record_failure("START_FAILED")
                self.stop()
                return False
            if worker is not None:
                worker.deleteLater()
            self._worker = None
            self._opening_timer.stop()
            self._record_failure("START_FAILED")
            self._settle_without_worker()
            return False
        return True

    def stop(self) -> bool:
        """Request a cooperative stop without blocking the GUI thread."""
        self._assert_thread()
        worker = self._worker
        if worker is None or not self._machine.stop():
            return False
        self._opening_timer.stop()
        self.state_changed.emit(self.state)
        worker.request_stop()
        self._stopping_timer.start()
        return True

    def retry(self) -> bool:
        """Explicit reopen; never retries automatically or while cleanup runs."""
        self._assert_thread()
        if self.state is not CameraState.FAILED:
            return False
        return self.start()

    def request_shutdown(self) -> bool:
        """Async close handshake; caller must wait for shutdown_ready.

        Returns True only when no worker exists. It never uses terminate().
        """
        self._assert_thread()
        self._shutting_down = True
        if self._worker is None:
            self.shutdown_ready.emit()
            return True
        self.stop()
        return False

    def take_latest(self):
        self._assert_thread()
        if (self.state is not CameraState.STREAMING or self._worker is None
                or self.error_code is not None):
            return None
        return self._worker.take_latest()

    def stats(self) -> tuple[int, int]:
        self._assert_thread()
        if self._worker is None:
            return (0, 0)
        return self._worker.stats()

    def _record_failure(self, code: str) -> None:
        self._machine.record_failure(code)
        if self._last_failure_sent != self.error_code:
            self._last_failure_sent = self.error_code
            self.failure.emit(self.error_code)

    @Slot()
    def _on_opened(self) -> None:
        if self.sender() != self._worker or self._worker is None:
            return
        if self._machine.opened():
            self._opening_timer.stop()
            self.state_changed.emit(self.state)

    @Slot()
    def _on_frame(self) -> None:
        if (self.sender() == self._worker and self.state is CameraState.STREAMING
                and self.error_code is None):
            self.frame_available.emit()

    @Slot(str)
    def _on_failed(self, code: str) -> None:
        if self.sender() != self._worker or self._worker is None:
            return
        self._opening_timer.stop()
        self._record_failure(code)
        # Stay in OPENING/STREAMING/STOPPING until worker has actually exited.

    @Slot()
    def _on_finished(self) -> None:
        if self.sender() != self._worker or self._worker is None:
            return
        self._finished_notified = True
        self._opening_timer.stop()
        self._stopping_timer.stop()
        self._try_reap()

    @Slot()
    def _try_reap(self) -> None:
        worker = self._worker
        if worker is None or not self._finished_notified:
            self._reap_timer.stop()
            return
        if worker.isRunning() or not worker.wait(0):
            if not self._reap_timer.isActive():
                self._reap_timer.start()
            return
        self._reap_timer.stop()
        self._opening_timer.stop()
        self._stopping_timer.stop()
        self._worker = None
        worker.deleteLater()
        self._settle_without_worker()

    def _settle_without_worker(self) -> None:
        new_state = self._machine.finished()
        if new_state is CameraState.FAILED and self._last_failure_sent != self.error_code:
            self._last_failure_sent = self.error_code
            self.failure.emit(self.error_code)
        self.state_changed.emit(new_state)
        self.settled.emit(new_state)
        if self._shutting_down:
            self.shutdown_ready.emit()

    @Slot()
    def _opening_timed_out(self) -> None:
        if self.state is not CameraState.OPENING or self._worker is None:
            return
        self._record_failure("OPEN_TIMEOUT")
        self.stop()  # stays STOPPING until native open/read/close has returned

    @Slot()
    def _stopping_timed_out(self) -> None:
        if self.state is not CameraState.STOPPING or self._worker is None:
            return
        self._record_failure("STOP_TIMEOUT")
        # Never claim CLOSED or destroy a still-running worker.
