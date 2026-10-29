"""GD2-09.07.2: Qt composition of live acquisition, depth ROI and existing Capture UI.

Live starts only after an explicit button press. Replay is separate, and the
live panel never accesses SDK, SQLite, Project persistence or native pointers.
"""
from __future__ import annotations

from collections.abc import Callable

from PySide6.QtCore import QObject, QThread, QTimer, Slot
from PySide6.QtWidgets import QWidget

from scantopath.application.contracts import WorkspaceId
from scantopath.modules.capture.domain.models import CameraState
from .depth_analysis_worker import DepthAnalysisThread
from .live_capture_panel import LiveCapturePanel
from .live_controller import LiveCameraController
from .live_worker import LiveStreamWorker


class LiveCaptureUiController(QObject):
    """GUI-thread owner of live panel, camera lifecycle and depth analysis thread."""

    def __init__(self, view, *, worker_factory: Callable[[], LiveStreamWorker]) -> None:
        super().__init__(view)
        self.view = view
        host = view.page_for(WorkspaceId.CAPTURE).findChild(QWidget, "workspaceScrollContent")
        if host is None or host.layout() is None:
            raise RuntimeError("Capture workspace host missing")
        replay_panel = view.capture_preview.panel
        if host.layout().indexOf(replay_panel) < 0:
            raise RuntimeError("RAW replay panel is not attached")
        self.panel = LiveCapturePanel(host)
        host.layout().insertWidget(host.layout().indexOf(replay_panel), self.panel)

        self.camera = LiveCameraController(worker_factory=worker_factory, parent=self)
        self._analysis: DepthAnalysisThread | None = None
        self._generation = 0
        self._closing = False
        self._shutdown_notified = False
        self._last_analyzed_frame: int | None = None

        self._preview_timer = QTimer(self)
        self._preview_timer.setInterval(100)  # 10 Hz, UI never follows native FPS
        self._preview_timer.timeout.connect(self._pump_preview)
        self.panel.start_button.clicked.connect(self.start)
        self.panel.stop_button.clicked.connect(self.stop)
        self.panel.retry_button.clicked.connect(self.retry)
        self.camera.state_changed.connect(self._on_state)
        self.camera.failure.connect(self._on_failure)
        self.camera.shutdown_ready.connect(self._on_camera_shutdown_ready)

    def _assert_gui(self):
        if QThread.currentThread() != self.thread():
            raise RuntimeError("LiveCaptureUiController must run on GUI thread")

    @property
    def safe_to_dispose(self) -> bool:
        return (self.camera.safe_to_dispose and self._analysis is None)

    @property
    def state(self) -> CameraState:
        return self.camera.state

    def _start_analysis_if_needed(self) -> None:
        if self._analysis is not None:
            return
        thread = DepthAnalysisThread()
        self._analysis = thread
        thread.analyzed.connect(self._on_analyzed)
        thread.finished.connect(self._on_analysis_finished)
        thread.start()

    def _new_generation(self) -> None:
        self._generation += 1
        self._last_analyzed_frame = None
        if self._analysis is not None:
            self._analysis.change_generation(self._generation)
        self.panel.clear_live()

    def start(self) -> bool:
        self._assert_gui()
        if self._closing or self.camera.state not in (CameraState.IDLE, CameraState.CLOSED):
            return False
        self._start_analysis_if_needed()
        self._new_generation()
        return self.camera.start()

    def stop(self) -> bool:
        self._assert_gui()
        return self.camera.stop()

    def retry(self) -> bool:
        self._assert_gui()
        if self._closing or self.camera.state is not CameraState.FAILED:
            return False
        self._start_analysis_if_needed()
        self._new_generation()
        return self.camera.retry()

    @Slot(object)
    def _on_state(self, state: CameraState) -> None:
        if state is CameraState.STREAMING and not self._closing:
            self._preview_timer.start()
        else:
            self._preview_timer.stop()
            if state in (CameraState.STOPPING, CameraState.CLOSED, CameraState.FAILED):
                self._new_generation()
        self.panel.set_state(state, self.camera.error_code)

    @Slot(str)
    def _on_failure(self, code: str) -> None:
        # Stable code only. State remains pending until native camera is closed.
        self.panel.set_state(self.camera.state, code)

    @Slot()
    def _pump_preview(self) -> None:
        if self._closing or self.camera.state is not CameraState.STREAMING:
            return
        frame = self.camera.take_latest()
        if frame is None:
            return
        self.panel.show_live_frame(frame)
        if self._analysis is not None:
            self._analysis.submit(self._generation, frame)

    @Slot(int, int, object)
    def _on_analyzed(self, generation: int, frame_index: int, result: object) -> None:
        if (self._closing or generation != self._generation or
                self.camera.state is not CameraState.STREAMING):
            return
        if self._last_analyzed_frame is not None and frame_index <= self._last_analyzed_frame:
            return
        self._last_analyzed_frame = frame_index
        self.panel.set_auto_result(result)

    def begin_navigation_away(self) -> None:
        """Leaving Capture requests stop; worker remains owned until reaped."""
        self._assert_gui()
        self.stop()
        self._preview_timer.stop()
        self._new_generation()
        self.panel.set_state(self.camera.state, self.camera.error_code)

    def begin_shutdown(self) -> bool:
        """Non-blocking; caller must not close MainWindow until both threads exit."""
        self._assert_gui()
        self._closing = True
        self._preview_timer.stop()
        self._new_generation()
        if self._analysis is not None:
            self._analysis.request_stop()
        self.camera.request_shutdown()
        return self.safe_to_dispose

    @Slot()
    def _on_camera_shutdown_ready(self) -> None:
        self._maybe_close()

    @Slot()
    def _on_analysis_finished(self) -> None:
        thread = self._analysis
        if thread is None:
            return
        # Qt queued finished might be observed just before QThread reports stopped.
        if thread.isRunning() or not thread.wait(0):
            QTimer.singleShot(10, self._on_analysis_finished)
            return
        self._analysis = None
        thread.deleteLater()
        self._maybe_close()

    def _maybe_close(self) -> None:
        if self._closing and self.safe_to_dispose and not self._shutdown_notified:
            self._shutdown_notified = True
            QTimer.singleShot(0, self.view.close)
