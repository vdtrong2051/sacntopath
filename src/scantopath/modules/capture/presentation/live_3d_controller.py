"""FT-05 Qt shell adapter; VTK IPC lives only in a separate Python thread."""
from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import QObject, QThread, QTimer, Slot, Signal
from PySide6.QtWidgets import QFileDialog

from scantopath.modules.capture.application.live_snapshot import (
    SnapshotError, freeze_geometry, bounds_xyz_mm, save_snapshot,
)


class _SnapshotSaveThread(QThread):
    saved = Signal(str)
    failed = Signal(str)

    def __init__(self, frozen, parent_dir: str, parent=None):
        super().__init__(parent)
        self._frozen = frozen
        self._parent_dir = parent_dir

    def run(self):
        try:
            result = save_snapshot(self._frozen, self._parent_dir)
            self.saved.emit(str(result))
        except SnapshotError as exc:
            self.failed.emit(exc.code)
        except Exception:
            self.failed.emit('SNAPSHOT_IO_FAILED')



from scantopath.modules.capture.domain.models import CameraState
from scantopath.modules.capture.application.live_object_bbox_tracker import (
    LiveObjectBoundingTracker,
)
from scantopath.modules.viewer3d.application.live_3d_runtime import Live3DRenderWorker


class Live3DController(QObject):
    """GUI-only pump of fully-owned RGB snapshots; never waits on renderer."""

    snapshot_saved = Signal(str)  # emitted only after atomic snapshot save completes

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
        self._latest_bundle = None
        self._frozen = None
        self._object_tracker = LiveObjectBoundingTracker()
        self._last_tracking_ui = None
        self._save_thread: _SnapshotSaveThread | None = None
        self._save_result = None
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
        self._panel.enhancement_mode_changed.connect(self._on_enhancement_mode)
        self._panel.freeze_requested.connect(self._freeze)
        self._panel.resume_requested.connect(self._resume)
        self._panel.snapshot_requested.connect(self._save)
        self._live.set_geometry_scope_mode(str(self._panel.scope_mode.currentData()))
        self._live.set_geometry_reference_mode(str(self._panel.reference_mode.currentData()))

    @property
    def safe_to_dispose(self) -> bool:
        renderer_done = self._worker is None or self._worker.stopped
        save_done = self._save_thread is None or not self._save_thread.isRunning()
        return renderer_done and save_done

    def begin_shutdown(self) -> bool:
        if not self._closing:
            self._closing = True
            self._timer.stop()
            self._latest_bundle = self._frozen = None
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
            self._reset_tracking()
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
            self._latest_bundle = self._frozen = None
            self._reset_tracking()
            self._panel.clear('Dừng / chưa có camera')

    @Slot()
    def _on_geometry_available(self) -> None:
        if self._closing or self._live.camera.state is not CameraState.STREAMING:
            return
        bundle = self._live.take_latest_geometry_bundle()
        if bundle is None:
            return
        if self._frozen is not None:  # keep consuming, but never overwrite frozen frame
            return
        cloud, source_frame, context = bundle
        if cloud is not None and self._worker is not None:
            self._latest_bundle = bundle
            # True selected-Depth pixel bounding; independent of legacy auto ROI.
            if self._panel.scope_mode.currentData() == 'object':
                src = source_frame.source
                obs = self._object_tracker.observe(
                    generation=cloud.camera_generation,
                    frame_index=cloud.depth_frame_index,
                    uv=cloud.depth_source_uv,
                    depth_width=src.depth_width,
                    depth_height=src.depth_height,
                    corner_count=int(context.get('board_corners') or 0),
                    reprojection_px=context.get('board_reprojection_px'))
                self._update_tracking_ui(obs)
            minimum, maximum = (cloud.points_xyz_m.min(axis=0)*1000,
                                cloud.points_xyz_m.max(axis=0)*1000)
            dims = maximum - minimum
            inferred = getattr(cloud, 'inferred_depth_mask', None)
            inferred_count = int(inferred.sum()) if inferred is not None else 0
            self._panel.geometry_info.setText(
                f'{cloud.points_xyz_m.shape[0]:,} điểm · +{inferred_count:,} nội suy · Bao XYZ: '
                + ' × '.join(f'{value:.1f}' for value in dims) + ' mm · LIVE')
            self._panel.set_snapshot_state('live')
            self._allow_rgb = True
            self._worker.submit_cloud(cloud)

    @Slot(str)
    def _on_geometry_failed(self, code: str) -> None:
        if not self._closing and self._frozen is None:
            self._latest_bundle = None
            if self._panel.scope_mode.currentData() == 'object':
                self._update_tracking_ui(self._object_tracker.missed())
            self._allow_rgb = False
            self._panel.clear('Không tách được vật thể: ' + code if code.startswith(("ISOLATION_", "CHARUCO_"))
                              else 'Geometry: ' + code)
            if self._worker is not None:
                self._worker.invalidate_scene()

    @Slot(str)
    def _on_scope_mode(self, mode: str) -> None:
        if self._closing:
            return
        self._discard_freeze()
        self._reset_tracking()
        self._allow_rgb = False
        self._panel.clear("Đang đổi phạm vi quan sát…")
        self._live.set_geometry_scope_mode(mode)
        if self._worker is not None:
            self._worker.invalidate_scene()

    @Slot(str)
    def _on_reference_mode(self, mode: str) -> None:
        if self._closing:
            return
        self._discard_freeze()
        self._reset_tracking()
        self._allow_rgb = False
        self._panel.clear("Đang chuyển nguồn tham chiếu…")
        self._live.set_geometry_reference_mode(mode)
        if self._worker is not None:
            self._worker.invalidate_scene()

    @Slot(str)
    def _on_denoise_mode(self, mode: str) -> None:
        if not self._closing:
            self._discard_freeze()
            self._reset_tracking()
            self._allow_rgb = False
            self._panel.clear('Đang thay đổi bộ lọc…')
            self._live.set_geometry_denoise_mode(mode)
            # Geometry worker needs a fresh frame with new processing parameters.
            if self._worker is not None:
                self._worker.invalidate_scene()

    def _discard_freeze(self):
        self._frozen = None
        self._latest_bundle = None
        if self._live.camera.state is CameraState.STREAMING:
            self._live.set_preview_frozen(False)

    @Slot()
    def _freeze(self) -> None:
        if (self._closing or self._frozen is not None or self._latest_bundle is None
                or self._live.camera.state is not CameraState.STREAMING
                or self._save_thread is not None):
            return
        cloud, frame, context = self._latest_bundle
        try:
            frozen = freeze_geometry(cloud, frame, **context)
        except (SnapshotError, ValueError) as exc:
            self._panel.status.setText('Không đóng băng được: dữ liệu không đồng bộ')
            return
        self._frozen = frozen
        self._latest_bundle = None
        self._live.set_preview_frozen(True, source_frame=frame,
                                      depth_mask=frozen.depth_mask, frozen_roi=frozen.roi)
        self._panel.geometry_info.setText(
            f'{cloud.points_xyz_m.shape[0]:,} điểm · Bao XYZ: '
            + ' × '.join(f'{b-a:.1f}' for a,b in zip(*bounds_xyz_mm(frozen)))
            + ' mm · ĐÃ ĐÓNG BĂNG')
        self._panel.set_snapshot_state('frozen')
        self._allow_rgb = False
        if self._worker is not None:
            # Restart render session to ensure old queued RGB cannot represent
            # a different point cloud. VTK still owns all blocking operations.
            self._worker.invalidate_scene()
            self._worker.submit_cloud(cloud)
            self._allow_rgb = True

    @Slot()
    def _resume(self) -> None:
        if self._closing or self._frozen is None or self._save_thread is not None:
            return
        self._discard_freeze()
        self._panel.set_snapshot_state('idle')
        self._allow_rgb = False
        if self._worker is not None:
            self._worker.invalidate_scene()

    @Slot()
    def _save(self) -> None:
        if (self._closing or self._frozen is None or self._save_thread is not None or
                self._live.camera.state is not CameraState.STREAMING):
            return
        parent = QFileDialog.getExistingDirectory(
            self._panel, 'Chọn thư mục lưu Snapshot', str(Path.home()))
        if not parent:
            return
        job = _SnapshotSaveThread(self._frozen, parent, self)
        self._save_thread = job
        self._panel.set_snapshot_state('saving')
        job.saved.connect(self._on_saved)
        job.failed.connect(self._on_save_failed)
        job.finished.connect(self._on_save_finished)
        job.start()

    @Slot(str)
    def _on_saved(self, folder: str) -> None:
        self._save_result = folder
        self.snapshot_saved.emit(folder)
        self._panel.status.setText('Snapshot đã lưu: ' + Path(folder).name)
        self._panel.status.setToolTip(folder)

    @Slot(str)
    def _on_save_failed(self, code: str) -> None:
        self._panel.status.setText('Không lưu Snapshot: ' + code)

    @Slot()
    def _on_save_finished(self) -> None:
        job = self._save_thread
        if job is None:
            return
        if job.isRunning() or not job.wait(0):
            QTimer.singleShot(15, self._on_save_finished)
            return
        self._save_thread = None
        job.deleteLater()
        if not self._closing:
            self._panel.set_snapshot_state('frozen' if self._frozen is not None else 'idle')

    @Slot(str)
    def _on_enhancement_mode(self, mode: str) -> None:
        if self._closing:
            return
        self._discard_freeze()
        self._reset_tracking()
        self._allow_rgb = False
        self._panel.clear('Đang đổi chế độ làm đẹp Depth…')
        self._live.set_geometry_enhancement_mode(mode)
        if self._worker is not None:
            self._worker.invalidate_scene()

    @Slot(str, float, float)
    def _on_camera_intent(self, action: str, dx: float, dy: float) -> None:
        if not self._closing and self._worker is not None:
            self._worker.submit_camera(action, dx, dy)

    def _reset_tracking(self) -> None:
        self._object_tracker.reset()
        self._last_tracking_ui = None
        self._live.panel.depth_overlay.set_object_bbox(None, 'LOST')
        self._panel.tracking_info.setText('Vật thể: chưa theo dõi')

    def _update_tracking_ui(self, observation) -> None:
        key = (observation.rect_xywh, observation.status)
        if key == self._last_tracking_ui:
            return
        self._last_tracking_ui = key
        if (observation.rect_xywh is None or
                self._live.panel.depth_overlay.image_size is not None):
            self._live.panel.depth_overlay.set_object_bbox(
                observation.rect_xywh, observation.status)
        roi = observation.rect_xywh
        detail = (f' · Khung {roi[2]}×{roi[3]} px' if roi is not None else '')
        labels = {'TRACKING': 'Đang bám', 'DEGRADED': 'Chất lượng giảm',
                  'REACQUIRING': 'Đang bắt lại',
                  'TEMPORARILY_LOST': 'Tạm mất bám (khung cũ)',
                  'LOST': 'Mất vật thể / tham chiếu'}
        self._panel.tracking_info.setText('Vật thể: '+labels[observation.status]+detail)

    @Slot()
    def _pump(self) -> None:
        if self._closing or self._live.camera.state is not CameraState.STREAMING or self._worker is None:
            return
        if self._frozen is None and self._panel.scope_mode.currentData() == 'object':
            self._update_tracking_ui(self._object_tracker.current())
        stats = self._worker.statistics()
        error = stats['last_error_code']
        if error and error != self._seen_error:
            self._seen_error = error
            if self._frozen is None:
                self._panel.clear('3D tạm ngừng (' + error + ') — Camera/RAW không bị ảnh hưởng')
            else:
                self._panel.status.setText('Renderer lỗi: ' + error + ' · Snapshot đóng băng vẫn có thể lưu')
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
        if (self._panel.scope_mode.currentData() == 'object' and
                self._panel.reference_mode.currentData() == 'charuco'):
            pose_mode = detail.get('board_pose_source')
            if pose_mode == 'optical_flow_estimate':
                age = detail.get('board_pose_age_frames', 0)
                self._panel.scope.setText(
                    self._panel.scope.text() + f' · Optical Flow ({age} frame, ƯỚC LƯỢNG)')
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
