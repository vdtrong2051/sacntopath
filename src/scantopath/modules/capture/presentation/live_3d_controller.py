"""FT-05 Qt shell adapter; VTK IPC lives only in a separate Python thread."""
from __future__ import annotations

from PySide6.QtCore import QObject, QTimer, Slot

from scantopath.modules.capture.domain.models import CameraState
from scantopath.modules.viewer3d.application.live_3d_runtime import Live3DRenderWorker


class Live3DController(QObject):
    """GUI-only pump of fully-owned RGB snapshots; never waits on renderer."""

    def __init__(self, view, *, worker_factory=None) -> None:
        super().__init__(view)
        self._view = view
        self._live = view.capture_live
        self._panel = self._live.panel.cloud_view
        self._worker_factory = worker_factory
        self._worker: Live3DRenderWorker | None = None  # Lazy until actual STREAMING.
        self._closing = False
        self._seen_error = None
        self._allow_rgb = False  # No stale image after mask failure or mode change.
        self._timer = QTimer(self)
        self._timer.setInterval(33)  # Render snapshots capped by GUI pump (~30 Hz).
        self._timer.timeout.connect(self._pump)
        self._timer.start()
        self._live.camera.state_changed.connect(self._on_camera_state)
        self._live.geometry_available.connect(self._on_geometry_available)
        self._live.geometry_failed.connect(self._on_geometry_failed)
        self._panel.camera_intent.connect(self._on_camera_intent)
        self._panel.denoise_mode_changed.connect(self._on_denoise_mode)
        self._panel.scope_mode_changed.connect(self._on_scope_mode)
        self._panel.reference_mode_changed.connect(self._on_reference_mode)
        self._live.set_geometry_scope_mode(str(self._panel.scope_mode.currentData()))
        self._live.set_geometry_reference_mode(str(self._panel.reference_mode.currentData()))

    @property
    def safe_to_dispose(self) -> bool:
        return self._worker is None or self._worker.stopped

    def begin_shutdown(self) -> bool:
        if not self._closing:
            self._closing = True
            self._timer.stop()
            if self._worker is not None:
                self._worker.request_stop()
            self._panel.clear('Đã dừng')
            if not self.safe_to_dispose:
                QTimer.singleShot(120, self._request_close_when_safe)
        return self.safe_to_dispose

    @Slot()
    def _request_close_when_safe(self) -> None:
        if self._closing and not self.safe_to_dispose:
            QTimer.singleShot(120, self._request_close_when_safe)
        elif self._closing:
            # Other shutdown participants still control whether the window may close.
            QTimer.singleShot(0, self._view.close)

    @Slot(object)
    def _on_camera_state(self, state: CameraState) -> None:
        if self._closing:
            return
        if state is CameraState.STREAMING:
            generation = self._live.geometry_statistics().get('camera_generation', 0)
            if type(generation) is int and generation > 0:
                if self._worker is None:
                    self._worker = Live3DRenderWorker(session_factory=self._worker_factory)
                    self._worker.start()
                self._allow_rgb = False
                self._worker.change_generation(generation)
                self._panel.status.setText('Viewer: đang khởi tạo 3D…')
        elif state in (CameraState.IDLE, CameraState.OPENING, CameraState.STOPPING,
                       CameraState.CLOSED, CameraState.FAILED):
            if self._worker is not None:
                self._worker.change_generation(0)
            self._allow_rgb = False
            self._panel.clear('Dừng / chưa có camera')

    @Slot()
    def _on_geometry_available(self) -> None:
        if self._closing or self._live.camera.state is not CameraState.STREAMING:
            return
        cloud = self._live.take_latest_geometry()
        if cloud is not None and self._worker is not None:
            self._allow_rgb = True
            self._worker.submit_cloud(cloud)

    @Slot(str)
    def _on_geometry_failed(self, code: str) -> None:
        if not self._closing:
            self._allow_rgb = False
            self._panel.clear('Không tách được vật thể: ' + code if code.startswith(("ISOLATION_", "CHARUCO_"))
                              else 'Geometry: ' + code)
            if self._worker is not None:
                self._worker.invalidate_scene()

    @Slot(str)
    def _on_scope_mode(self, mode: str) -> None:
        if self._closing:
            return
        self._allow_rgb = False
        self._panel.clear("Đang đổi phạm vi quan sát…")
        self._live.set_geometry_scope_mode(mode)
        if self._worker is not None:
            self._worker.invalidate_scene()

    @Slot(str)
    def _on_reference_mode(self, mode: str) -> None:
        if self._closing:
            return
        self._allow_rgb = False
        self._panel.clear("Đang chuyển nguồn tham chiếu…")
        self._live.set_geometry_reference_mode(mode)
        if self._worker is not None:
            self._worker.invalidate_scene()

    @Slot(str)
    def _on_denoise_mode(self, mode: str) -> None:
        if not self._closing:
            self._live.set_geometry_denoise_mode(mode)

    @Slot(str, float, float)
    def _on_camera_intent(self, action: str, dx: float, dy: float) -> None:
        if not self._closing and self._worker is not None:
            self._worker.submit_camera(action, dx, dy)

    @Slot()
    def _pump(self) -> None:
        if self._closing or self._live.camera.state is not CameraState.STREAMING or self._worker is None:
            return
        stats = self._worker.statistics()
        error = stats['last_error_code']
        if error and error != self._seen_error:
            self._seen_error = error
            self._panel.clear('3D tạm ngừng (' + error + ') — Camera/RAW không bị ảnh hưởng')
        roi = self._live.panel.displayed_roi
        if roi is None:
            self._panel.scope.setText('ROI: Toàn ảnh Depth · Chế độ: ' +
                                      self._panel.scope_mode.currentText())
        else:
            self._panel.scope.setText(
                f'ROI: ({roi.x}, {roi.y}, {roi.width}, {roi.height}) · Chế độ: '
                + self._panel.scope_mode.currentText()
            )
        # Small, status-only diagnostic; never transfer pixels through Qt status.
        detail = self._live.geometry_statistics()
        if self._panel.scope_mode.currentData() == "object":
            ref = self._panel.reference_mode.currentText()
            corners = detail.get("board_corners", 0)
            reproj = detail.get("board_reprojection_px")
            suffix = ((f" · {corners} góc" +
                      (f" · RMSE {reproj:.2f}px" if type(reproj) in (int, float) else ""))
                      if self._panel.reference_mode.currentData() == "charuco" else "")
            self._panel.scope.setText(self._panel.scope.text() + " · " + ref + suffix)
        item = self._worker.take_latest_rgb()
        if not self._allow_rgb:
            return
        if item is None:
            return
        generation, frame = item
        actual = self._live.geometry_statistics().get('camera_generation', 0)
        if generation != actual:
            return
        try:
            self._panel.show_frame(frame.rgb, frame.width, frame.height)
            self._seen_error = None
        except (ValueError, RuntimeError):
            self._panel.clear('Ảnh render không hợp lệ')
