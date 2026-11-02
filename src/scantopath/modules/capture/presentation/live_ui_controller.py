"""GD2-09.07.2: Qt composition of live acquisition, depth ROI and existing Capture UI.

Live starts only after an explicit button press. Replay is separate, and the
live panel never accesses SDK, SQLite, Project persistence or native pointers.
"""
from __future__ import annotations

from collections.abc import Callable

from PySide6.QtCore import QObject, QThread, QTimer, Signal, Slot
from PySide6.QtWidgets import QWidget

from scantopath.application.contracts import WorkspaceId
from scantopath.modules.capture.domain.models import CameraState
from .depth_analysis_worker import DepthAnalysisThread
from scantopath.modules.capture.application.live_display_stabilizer import DepthDisplayStabilizer
from .live_capture_panel import LiveCapturePanel
from .live_controller import LiveCameraController
from .live_worker import LiveStreamWorker
from scantopath.modules.geometry.presentation.live_geometry_worker import LiveGeometryThread


class LiveCaptureUiController(QObject):
    analysis_ready = Signal(object, object)  # owned frame + tracking result
    geometry_available = Signal()  # wake-up, fetch via take_latest_geometry()
    geometry_failed = Signal(str)  # stable error code, not SDK details
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
        self._geometry: LiveGeometryThread | None = None
        self._geometry_latest = None
        self._geometry_bundle_latest = None
        self._preview_frozen = False
        self._geometry_last_error: str | None = None
        self._generation = 0
        self._closing = False
        self._shutdown_notified = False
        self._last_analyzed_frame: int | None = None
        self._display_stabilizer = DepthDisplayStabilizer()
        self._geometry_scope_mode = "scene"  # FT-05.7 backend compatible; Qt explicitly opts into object
        self._geometry_reference_mode = "depth"  # FT-05.7 backend compatibility
        self._geometry_denoise_mode = "standard"
        self._geometry_enhancement_mode = 'visual'

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
        return (self.camera.safe_to_dispose and self._analysis is None
                and self._geometry is None)

    @property
    def state(self) -> CameraState:
        return self.camera.state

    def _start_analysis_if_needed(self) -> None:
        if self._analysis is not None:
            return
        thread = DepthAnalysisThread()
        self._analysis = thread
        thread.analyzed.connect(self._on_analyzed)
        thread.analysis_available.connect(self._on_analysis_available)
        thread.finished.connect(self._on_analysis_finished)
        thread.start()

    def _start_geometry_if_needed(self) -> None:
        if self._geometry is not None:
            return
        thread = LiveGeometryThread()
        thread.set_scope_mode(self._geometry_scope_mode)
        thread.set_reference_mode(self._geometry_reference_mode)
        thread.set_denoise_mode(self._geometry_denoise_mode)
        thread.set_enhancement_mode(self._geometry_enhancement_mode)
        self._geometry = thread
        thread.result_available.connect(self._on_geometry_available)
        thread.finished.connect(self._on_geometry_finished)
        thread.start()

    def take_latest_geometry(self):
        """Consume at most one current-generation LiveCloudFrame on GUI thread."""
        self._assert_gui()
        cloud = self._geometry_latest
        self._geometry_latest = None
        return cloud if self.camera.state is CameraState.STREAMING else None

    def take_latest_geometry_bundle(self):
        """For FT-06, transfer cloud + original owned same-frame RGB-D atomically."""
        self._assert_gui()
        bundle = self._geometry_bundle_latest
        self._geometry_bundle_latest = None
        self._geometry_latest = None
        return bundle if self.camera.state is CameraState.STREAMING else None

    def set_preview_frozen(self, frozen: bool, *, source_frame=None, depth_mask=None, frozen_roi=None) -> None:
        """Affect only preview. Never pause camera/analysis/RAW."""
        self._assert_gui()
        self._preview_frozen = bool(frozen)
        if frozen:
            if source_frame is None or depth_mask is None:
                raise ValueError('FT06_FREEZE_FRAME_REQUIRED')
            self.panel.show_live_frame(source_frame)
            from scantopath.modules.capture.domain.models import DepthRoi, RoiSource
            frozen_rect = (DepthRoi(*frozen_roi, source_frame.source.depth_width,
                                    source_frame.source.depth_height, RoiSource.DEPTH_SUGGESTION)
                           if frozen_roi is not None else None)
            self.panel.depth_overlay.set_roi(frozen_rect)
            self.panel.depth_overlay.set_sampled_mask(depth_mask)
        else:
            self.panel.depth_overlay.set_sampled_mask(None)

    def set_geometry_denoise_mode(self, mode: str) -> None:
        self._assert_gui()
        if type(mode) is not str or mode not in ("standard", "off"):
            raise ValueError("DENOISE_MODE_INVALID")
        self._geometry_denoise_mode = mode
        if self._geometry is not None:
            self._geometry.set_denoise_mode(mode)

    def set_geometry_enhancement_mode(self, mode: str) -> None:
        self._assert_gui()
        if type(mode) is not str or mode not in ('off', 'visual'):
            raise ValueError('ENHANCEMENT_MODE_INVALID')
        self._geometry_enhancement_mode = mode
        self._geometry_bundle_latest = self._geometry_latest = None
        self._geometry_last_error = None
        if self._geometry is not None:
            self._geometry.set_enhancement_mode(mode)

    def set_geometry_scope_mode(self, mode: str) -> None:
        self._assert_gui()
        if type(mode) is not str or mode not in ("scene", "object"):
            raise ValueError("SCOPE_MODE_INVALID")
        if mode == self._geometry_scope_mode:
            return
        self._geometry_scope_mode = mode
        self._geometry_latest = None
        self._geometry_bundle_latest = None
        self._geometry_last_error = None
        self.panel.depth_overlay.set_sampled_mask(None)
        if self._geometry is not None:
            self._geometry.set_scope_mode(mode)

    def set_geometry_reference_mode(self, mode: str) -> None:
        self._assert_gui()
        if type(mode) is not str or mode not in ("depth", "charuco"):
            raise ValueError("REFERENCE_MODE_INVALID")
        if mode == self._geometry_reference_mode:
            return
        self._geometry_reference_mode = mode
        self._geometry_latest = None
        self._geometry_bundle_latest = None
        self._geometry_last_error = None
        self.panel.depth_overlay.set_sampled_mask(None)
        if self._geometry is not None:
            self._geometry.set_reference_mode(mode)

    def geometry_statistics(self) -> dict:
        self._assert_gui()
        return self._geometry.statistics() if self._geometry is not None else {}

    def _new_generation(self) -> None:
        self._generation += 1
        self._last_analyzed_frame = None
        self._geometry_latest = None
        self._geometry_bundle_latest = None
        self._preview_frozen = False
        self._geometry_last_error = None
        self._display_stabilizer.reset()
        if self._geometry is not None:
            self._geometry.change_generation(self._generation)
        if self._analysis is not None:
            self._analysis.change_generation(self._generation)
        self.panel.clear_live()

    def start(self) -> bool:
        self._assert_gui()
        if self._closing or self.camera.state not in (CameraState.IDLE, CameraState.CLOSED):
            return False
        self._start_analysis_if_needed()
        self._start_geometry_if_needed()
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
        self._start_geometry_if_needed()
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
        if not self._preview_frozen:
            self.panel.show_live_frame(frame)
        if self._analysis is not None:
            self._analysis.submit(self._generation, frame)
        # One controller owns take_latest(); other consumers share owned frame.
        worker = self._geometry
        if worker is not None:
            # FT-06.1: ChArUco has its OWN 3D board footprint and object search.
            # Do not let a broad or lost legacy auto-ROI clip the ChArUco object.
            # An explicitly drawn manual ROI remains an intentional constraint.
            roi = (self.panel.manual_roi if
                   self._geometry_scope_mode == 'object' and
                   self._geometry_reference_mode == 'charuco'
                   else self.panel.displayed_roi)
            rect = None
            if (roi is not None and
                    (roi.frame_width, roi.frame_height) ==
                    (frame.source.depth_width, frame.source.depth_height)):
                rect = (roi.x, roi.y, roi.width, roi.height)
            worker.submit(self._generation, frame, depth_roi=rect)

    @Slot(int, int, object)
    def _on_analyzed(self, generation: int, frame_index: int, result: object) -> None:
        if (self._closing or generation != self._generation or
                self.camera.state is not CameraState.STREAMING):
            return
        if self._last_analyzed_frame is not None and frame_index <= self._last_analyzed_frame:
            return
        self._last_analyzed_frame = frame_index
        stabilized = self._display_stabilizer.update(frame_index, result)
        if not self._preview_frozen:
            self.panel.set_auto_result(result, display_roi=stabilized)

    @Slot()
    def _on_analysis_available(self) -> None:
        worker = self._analysis
        if worker is None:
            return
        packet = worker.take_latest_analysis()
        if packet is None:
            return
        generation, frame_index, frame, result = packet
        if (self._closing or generation != self._generation or
                self.camera.state is not CameraState.STREAMING or
                (self._last_analyzed_frame is not None and
                 frame_index < self._last_analyzed_frame)):
            return
        if self._last_analyzed_frame != frame_index:
            self._last_analyzed_frame = frame_index
            stabilized = self._display_stabilizer.update(frame_index, result)
            if not self._preview_frozen:
                self.panel.set_auto_result(result, display_roi=stabilized)
        self.analysis_ready.emit(frame, result)

    @Slot()
    def _on_geometry_available(self) -> None:
        worker = self._geometry
        if worker is None:
            return
        packet = worker.take_latest_result_bundle()
        if packet is None:
            return
        generation, frame_index, cloud, error, context = packet
        if (self._closing or generation != self._generation or
                self.camera.state is not CameraState.STREAMING):
            return
        if error is not None:
            self._geometry_latest = None
            self._geometry_bundle_latest = None
            if not self._preview_frozen:
                self.panel.depth_overlay.set_sampled_mask(None)
            if error != self._geometry_last_error:
                self._geometry_last_error = error
                self.geometry_failed.emit(error)
            return
        if cloud is None or cloud.depth_frame_index != frame_index:
            return
        self._geometry_last_error = None
        self._geometry_latest = cloud
        if context is not None:
            src_frame, provenance = context
            self._geometry_bundle_latest = (cloud, src_frame, provenance)
        else:
            self._geometry_bundle_latest = None
        # GUI-side object inspection uses the exact selected XYZ lineage.
        # Throttled: 2.5 Hz; the full-depth QPixmap is never repainted at camera FPS.
        if not self._preview_frozen and context is not None:
            from time import monotonic
            now = monotonic()
            if now - getattr(self, '_last_mask_overlay_at', 0.0) >= 0.4:
                self._last_mask_overlay_at = now
                h, w = context[0].depth_u16.shape
                import numpy as np
                sampled = np.zeros((h, w), dtype=np.uint8)
                uv = cloud.depth_source_uv
                sampled[uv[:, 1], uv[:, 0]] = 255
                self.panel.depth_overlay.set_sampled_mask(sampled)
        self.geometry_available.emit()

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
        if self._geometry is not None:
            self._geometry.request_stop()
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

    @Slot()
    def _on_geometry_finished(self) -> None:
        thread = self._geometry
        if thread is None:
            return
        if thread.isRunning() or not thread.wait(0):
            QTimer.singleShot(10, self._on_geometry_finished)
            return
        self._geometry = None
        self._geometry_latest = None
        self._geometry_bundle_latest = None
        thread.deleteLater()
        self._maybe_close()

    def _maybe_close(self) -> None:
        if self._closing and self.safe_to_dispose and not self._shutdown_notified:
            self._shutdown_notified = True
            QTimer.singleShot(0, self.view.close)
