"""HS-01.3: opt-in GUI adapter for HS-01.2 selector -> existing RAW-v2 workflow.

No native camera/SQLite access. All callbacks run on the Qt GUI thread. The
existing CaptureActionCoordinator is the sole camera/persistence owner.
"""
from __future__ import annotations

from PySide6.QtCore import QObject, Slot

from scantopath.modules.capture.application.auto_capture_session import (
    AutoCaptureSession, AutoCaptureState,
)
from scantopath.modules.capture.domain.models import CameraState
from scantopath.modules.capture.application.keyframe_selection_models import KeyframeDecision
from scantopath.modules.capture.application.roi_safety import RoiSafetyEvaluator


STORAGE_TERMINAL_ERRORS = frozenset({
    "RAW_WRITE_FAILED", "RAW_INTEGRITY_FAILED", "CAPTURE_REGISTRATION_FAILED",
    "CAPTURE_RECOVERY_REQUIRED", "CAPTURE_PERSISTENCE_FAILED",
    "REPLAY_VERIFICATION_FAILED", "SESSION_NOT_OPEN", "STORE_NOT_OPEN",
    "NUMBERED_SCHEMA_REQUIRED", "CAPTURE_CONTEXT_MISMATCH",
    "CAPTURE_STORE_FAILED", "CAPTURE_RESERVE_REJECTED", "CAPTURE_RESERVE_FAILED",
})


class AutoCaptureController(QObject):
    def __init__(self, view) -> None:
        super().__init__(view)
        self.view = view
        self.live = view.capture_live
        self.action = view.capture_action
        self.panel = self.live.panel
        self.session = AutoCaptureSession()
        self.roi_safety = RoiSafetyEvaluator()
        self._last_context = None
        self.panel.auto_capture_button.toggled.connect(self._on_toggled)
        self.live.analysis_ready.connect(self._on_analysis)
        self.action.finished.connect(self._on_saved)
        self.action.failed.connect(self._on_failed)
        self.action.phase_changed.connect(self._on_phase)
        self.live.camera.state_changed.connect(self._on_camera_state)
        view.project_explorer.selection_changed.connect(self._on_selection_changed)
        view.project_loader.busy_changed.connect(self._refresh)
        view.project_writer.busy_changed.connect(self._refresh)
        self._refresh()

    def _selected_context(self):
        return self.action._selected_context()

    def _log(self, message: str) -> None:
        self.view.task_event_panel.add_ui_event(message)

    def _stop(self, reason: str) -> None:
        self.session.stop(reason)
        self.panel.auto_capture_button.blockSignals(True)
        self.panel.auto_capture_button.setChecked(False)
        self.panel.auto_capture_button.blockSignals(False)
        self.action._refresh()  # re-enable manual fallback when auto turns OFF
        self._show_roi_safety(None)
        self._refresh()

    @Slot(bool)
    def _on_toggled(self, enabled: bool) -> None:
        if not enabled:
            self._stop("OPERATOR_STOP")
            return
        context = self._selected_context()
        if (context is None or self.live.camera.state is not CameraState.STREAMING or
                self.action.busy or self.view.project_loader.busy or
                self.view.project_writer.busy):
            self._stop("NO_OPEN_SCAN_SESSION")
            return
        try:
            self.session.start(context)
        except (ValueError, RuntimeError):
            self._stop("AUTO_SESSION_BUSY")
            return
        self._last_context = context
        self._show_roi_safety(None)
        self._log("Auto Keyframe: bắt đầu trong Scan Session " + context.session_id)
        self._refresh()

    def _show_roi_safety(self, result) -> None:
        label = getattr(self.panel, "roi_safety_status", None)
        if label is None:
            return  # Legacy Qt fixtures do not have the post-01.4 label.
        if result is None:
            label.setText("ROI Safety: WAITING | chưa đánh giá Depth")
            return
        status = "READY_PROXY" if result.safe_to_propose else "BLOCKED"
        distance = ("--" if result.median_depth_m is None
                    else f"{result.median_depth_m:.2f} m")
        label.setText(
            f"ROI Safety: {status} | {result.reason.value} | "
            f"source={result.source} | width={result.width_fraction:.0%} "
            f"area={result.area_fraction:.0%} | depth={distance} "
            f"valid={result.valid_fraction:.0%}"
            + (" | ROI tay chỉ cố định theo ảnh, không bám vật thể"
               if result.source == "manual" else "")
        )

    @Slot(object, object)
    def _on_analysis(self, frame, tracking) -> None:
        if not self.session.can_accept_frames:
            return
        if self.live.camera.state is not CameraState.STREAMING:
            return
        # Selection change must NOT send a RAW to a different Session.
        if self._selected_context() != self.session.context:
            if not self.view.project_loader.busy and not self.view.project_writer.busy:
                self._stop("CAPTURE_CONTEXT_CHANGED")
            return
        if (self.action.busy or self.view.project_loader.busy or
                self.view.project_writer.busy):
            return
        manual = self.panel.manual_roi
        roi = manual if manual is not None else (
            tracking.roi if tracking is not None and tracking.usable else None
        )
        # This *guard* checks geometry/metric depth plausibility, not whether
        # the rectangle contains the requested object. Fail closed for auto.
        try:
            safety = self.roi_safety.evaluate(frame, roi)
        except (TypeError, ValueError):
            self.session.reject_roi_guard("ROI_FRAME_INVALID")
            self._show_roi_safety(None)
            self._refresh()
            return
        self._show_roi_safety(safety)
        if not safety.safe_to_propose:
            self.session.reject_roi_guard(safety.reason.value)
            self._refresh()
            return
        try:
            outcome = self.session.observe(frame, roi)
        except (TypeError, ValueError, RuntimeError):
            self.session.invalidate_view_reference()
            self._refresh()
            return
        if outcome is None:
            return
        if outcome.decision is KeyframeDecision.SELECT:
            ctx = self.session.context
            success = self.action.capture_auto(
                ctx,
                color_frame_index=frame.source.color_frame_index,
                depth_frame_index=frame.source.depth_frame_index,
            )
            if not success:
                self.session.mark_failed("AUTO_CAPTURE_REQUEST_REJECTED")
        self._refresh()

    @Slot(str)
    def _on_saved(self, capture_id: str) -> None:
        if self.session.pending:
            try:
                self.session.mark_saved(capture_id)
            except (ValueError, RuntimeError):
                self.session.mark_failed("INVALID_AUTO_RECEIPT")
                self._stop("INVALID_AUTO_RECEIPT")
            self._refresh()

    @Slot(str)
    def _on_failed(self, code: str) -> None:
        if self.session.pending:
            self.session.mark_failed(code)
            if code in STORAGE_TERMINAL_ERRORS:
                self._stop("STORE_ERROR_REQUIRES_REVIEW")
            self._refresh()

    @Slot(str, str)
    def _on_phase(self, state: str, description: str) -> None:
        if self.session.pending:
            self._refresh()

    @Slot(object)
    def _on_camera_state(self, state) -> None:
        if state in (CameraState.STOPPING, CameraState.CLOSED, CameraState.FAILED):
            self._stop("CAMERA_STOPPED")
        else:
            self._refresh()

    @Slot()
    def _on_selection_changed(self, *_args) -> None:
        if (self.session.state in (AutoCaptureState.SCANNING, AutoCaptureState.CAPTURING)
                and not self.action.busy and not self.view.project_loader.busy
                and not self.view.project_writer.busy
                and self._selected_context() != self.session.context):
            self._stop("CAPTURE_CONTEXT_CHANGED")
        else:
            self._refresh()

    @Slot()
    def _refresh(self, *_args) -> None:
        state = self.session.state
        active = state in (AutoCaptureState.SCANNING, AutoCaptureState.CAPTURING,
                           AutoCaptureState.STOPPING)
        ready = (self.live.camera.state is CameraState.STREAMING and
                 self._selected_context() is not None and not self.action.busy and
                 not self.view.project_loader.busy and not self.view.project_writer.busy)
        # Do not disable the operator's OFF switch during capture/commit.
        self.panel.auto_capture_button.setEnabled(active or ready)
        snap = self.session.snapshot()
        self.panel.auto_capture_status.setText(
            f"Auto Keyframe: {snap.state.value} | evaluated={snap.evaluated} "
            f"selected={snap.proposals} saved={snap.saved} failed={snap.failures} "
            f"| {snap.last_reason}"
        )
