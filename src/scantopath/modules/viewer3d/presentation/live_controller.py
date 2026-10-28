"""R5.2 live Viewer integration; Qt owns pixels but never VTK/OpenGL.

The session provider is injected by the desktop composition root. Child process
startup, IPC, PLY/OBJ loading, and teardown happen outside the Qt GUI thread.
"""
from __future__ import annotations

from concurrent.futures import Future
from pathlib import Path
import os
import threading
import time
from typing import Callable

from PySide6.QtCore import QTimer
from PySide6.QtWidgets import QFileDialog, QPushButton

from ..application.scene_contracts import SceneDescriptor
from .controller import Viewer3DController
from .live_view import LiveNavigationPreview, rgb_snapshot_to_pixmap


class LiveViewer3DController(Viewer3DController):
    """R5.2 live mode with explicit legacy PNG fallback and bounded shutdown."""

    FRAME_INTERVAL_MS = 25
    START_TIMEOUT_SECONDS = 45
    OPEN_TIMEOUT_SECONDS = 180
    SHUTDOWN_TIMEOUT_SECONDS = 12

    def __init__(self, parent, *, session_factory: Callable):
        super().__init__(parent)
        if not callable(session_factory):
            raise TypeError('SESSION_FACTORY_REQUIRED')
        self._session_factory = session_factory
        self._live_session = None
        self._start_future: Future | None = None
        self._open_future: Future | None = None
        self._teardown: threading.Thread | None = None
        self._teardown_error: BaseException | None = None
        self._pending_source: Path | None = None
        self._current_source: Path | None = None
        self._descriptor: SceneDescriptor | None = None
        self._expected_scene_revision: int | None = None
        self._last_frame_revision = -1
        self._last_input_revision = -1
        self._live_phase = 'idle'
        self._phase_deadline = 0.0
        self._legacy_mode = False
        self._closing = False
        self._live_error = ''
        self._hmi_frames = 0

        # Reuse all existing Qt objectNames and the standard page's controls.
        old = self.page.preview
        replacement = LiveNavigationPreview('Chọn Mở mô hình để bắt đầu.', self.page.surface)
        replacement.setObjectName('viewer3dPreview')
        replacement.setAlignment(old.alignment())
        replacement.setSizePolicy(old.sizePolicy())
        replacement.setMinimumSize(old.minimumSize())
        replacement.setStyleSheet(old.styleSheet())
        replacement.gesture.connect(self.page.navigation_requested.emit)
        replacement.point_clicked.connect(self.page.point_requested.emit)
        self.page.surface_layout.replaceWidget(old, replacement)
        old.setParent(None)
        old.deleteLater()
        self.page.preview = replacement
        self.page.open_ply_button.setText('Mở mô hình…')
        self.page.open_ply_button.setToolTip('Mở tệp PLY hoặc OBJ. Không chỉnh sửa dữ liệu nguồn.')
        self.page.axes_button.setToolTip('Hiện hoặc ẩn trục tham khảo; không xác nhận hệ tọa độ.')
        self.page.clear_preview('Chưa mở mô hình 3D', 'Chọn tệp PLY hoặc OBJ để xem trực tiếp.')
        self._localize_unavailable_tools()

        self.safe_preview_button = QPushButton('Xem trước an toàn', self.page)
        self.safe_preview_button.setObjectName('viewer3dSafePreviewButton')
        self.safe_preview_button.setCheckable(True)
        self.safe_preview_button.setToolTip('Chế độ PNG tương thích cũ; chỉ hỗ trợ PLY.')
        self.safe_preview_button.toggled.connect(self._select_fallback)
        self.page.layout().itemAt(0).layout().insertWidget(1, self.safe_preview_button)

        self.retry_button = QPushButton('Thử lại', self.page)
        self.retry_button.setObjectName('viewer3dRetryButton')
        self.retry_button.clicked.connect(self.retry)
        self.retry_button.setEnabled(False)
        self.page.layout().itemAt(0).layout().insertWidget(2, self.retry_button)

        self._poll_timer = QTimer(self)
        self._poll_timer.setInterval(self.FRAME_INTERVAL_MS)
        self._poll_timer.timeout.connect(self._poll_live)

    def _localize_unavailable_tools(self) -> None:
        if not self._legacy_mode:
            self.page.point_title.setText('Thông tin điểm và mặt · Chưa có lựa chọn')
            self.page.point_info.setText('Chọn điểm và mặt sẽ được bổ sung trong phiên R5.3.')

    @property
    def live_phase(self) -> str:
        return self._live_phase

    @property
    def frames_presented_to_qt(self) -> int:
        return self._hmi_frames

    def activate(self) -> None:
        if self._disposed or self._closing:
            return
        if self._legacy_mode:
            super().activate()
            return
        if os.environ.get('QT_QPA_PLATFORM', '').lower() in ('offscreen', 'minimal'):
            self.page.set_status('Chế độ kiểm thử Qt; hiển thị 3D thực cần màn hình Windows.')
            return
        if self._live_phase == 'idle':
            self.page.set_status('Sẵn sàng. Chọn Mở mô hình để xem PLY hoặc OBJ.')

    def _choose_ply(self) -> None:
        if self._closing or self._disposed or self._process is not None:
            return
        filters = 'Mô hình 3D (*.ply *.obj)' if not self._legacy_mode else 'Đám mây điểm (*.ply)'
        path, _ = QFileDialog.getOpenFileName(self.page, 'Mở mô hình 3D', '', filters)
        if path:
            self.load_ply(path)

    def load_ply(self, filename: str | Path) -> bool:
        if self._legacy_mode:
            if self._teardown is not None and self._teardown.is_alive():
                self.page.set_status('Đang đóng bộ hiển thị trước đó. Hãy mở tệp sau khi hoàn tất.')
                return False
            return super().load_ply(filename)
        if self._disposed or self._closing:
            return False
        source = Path(filename)
        if (not source.is_absolute() or not source.is_file() or source.is_symlink() or
                source.suffix.lower() not in ('.ply', '.obj')):
            self._show_live_failure('Không thể mở mô hình. Hãy chọn tệp PLY hoặc OBJ hợp lệ.')
            return False
        if os.environ.get('QT_QPA_PLATFORM', '').lower() in ('offscreen', 'minimal'):
            self.page.set_status('Kiểm thử Qt không sử dụng tiến trình VTK native.', is_error=True)
            return False
        self._last_requested_source = source
        self._pending_source = source
        self._descriptor = None
        self._current_source = None
        self._expected_scene_revision = None
        self._last_frame_revision = -1
        self._last_input_revision = -1
        self._live_error = ''
        self.retry_button.setEnabled(False)
        self.page.clear_preview('Đang mở mô hình…', 'Đang chuẩn bị khung nhìn 3D an toàn.')
        self._localize_unavailable_tools()
        self.page.set_loading(True)
        self.page.set_status('Đang tải mô hình 3D ở tiến trình riêng…')
        self._retire_current()
        self._poll_timer.start()
        return True

    def _retire_current(self) -> None:
        """Invalidate all stale frames before a source switch or native shutdown."""
        if self._live_session is None:
            return
        previous = self._live_session
        self._live_session = None
        self._start_future = self._open_future = None
        self._live_phase = 'stopping'
        self._teardown_error = None

        def stop_old():
            try:
                previous.stop(timeout=2.0)
            except BaseException as exc:
                self._teardown_error = exc

        self._teardown = threading.Thread(target=stop_old, name='R5.2-render-cleanup', daemon=True)
        self._teardown.start()

    def _begin_scene(self) -> None:
        if self._pending_source is None or self._closing:
            return
        self._live_session = self._session_factory()
        self._start_future = self._live_session.start()
        self._open_future = None
        self._live_phase = 'starting'
        self._phase_deadline = time.monotonic() + self.START_TIMEOUT_SECONDS

    def _poll_live(self) -> None:
        if self._disposed:
            self._poll_timer.stop()
            return
        if self._teardown is not None:
            if self._teardown.is_alive():
                return
            self._teardown.join(timeout=0)
            self._teardown = None
            if self._teardown_error is not None:
                self._show_live_failure('Không thể dọn tiến trình hiển thị 3D. Hãy đóng ứng dụng và kiểm tra tiến trình.')
                return
        if self._closing:
            self._poll_timer.stop()
            return
        if self._live_session is None:
            if self._pending_source is not None:
                self._begin_scene()
            else:
                self._poll_timer.stop()
            return
        try:
            if self._live_phase in ('starting', 'loading') and time.monotonic() > self._phase_deadline:
                raise TimeoutError('RENDERER_START_OR_LOAD_TIMEOUT')
            if self._live_phase == 'starting':
                if not self._start_future.done():
                    return
                self._start_future.result()
                self._open_future = self._live_session.open_source(self._pending_source)
                self._live_phase = 'loading'
                self._phase_deadline = time.monotonic() + self.OPEN_TIMEOUT_SECONDS
            if self._live_phase == 'loading':
                if not self._open_future.done():
                    return
                info = self._open_future.result()
                self._descriptor = SceneDescriptor.from_result(info)
                self._expected_scene_revision = info['scene_revision']
                self._current_source = self._pending_source
                self._pending_source = None
                self._live_phase = 'ready'
                self._started = True
                self.page.set_loading(False)
                self.page.set_axes(False)
                self.page.note.setText(
                    f'{self._descriptor.name} · {self._descriptor.point_count:,} đỉnh · '
                    f'{self._descriptor.face_count:,} mặt · Đơn vị/hệ tọa độ chưa xác nhận')
                self.page.layer_label.setText('Mô hình: ' + ('Lưới bề mặt' if self._descriptor.face_count else 'Đám mây điểm'))
                self.page.layer_button.setEnabled(False)  # Real actor visibility is R5.3.
                self.page.layer_button.setToolTip('Ẩn/hiện lớp hình học sẽ hoàn thiện trong R5.3.')
                self.page.preview.set_pick_enabled(False)  # Native point/face picking is R5.3.
                self.page.set_status('Đã tải mô hình. Kéo chuột để xoay, kéo phải để di chuyển, cuộn để thu phóng.')
            if self._live_phase == 'ready':
                self._drain_newest_frame()
        except (Exception,):
            self._show_live_failure('Bộ hiển thị 3D ngừng phản hồi. Chọn Thử lại để khởi động lại.')

    def _drain_newest_frame(self) -> None:
        # Consume at most the latest snapshot. Polling never waits for the worker.
        try:
            frame = self._live_session.next_frame(timeout=0.0)
        except TimeoutError:
            return
        if (frame.scene_revision != self._expected_scene_revision or
                frame.frame_revision <= self._last_frame_revision or
                frame.input_revision < self._last_input_revision or
                frame.input_revision > self._live_session.statistics['input_revision'] or
                frame.host_pid != self._live_session.pid):
            return  # Old/mismatched frame must never appear in a new scene.
        image = rgb_snapshot_to_pixmap(frame)
        self._last_frame_revision = frame.frame_revision
        self._last_input_revision = frame.input_revision
        self.page._image = image
        self.page._fit_preview()
        self.page.set_loading(False)
        self.page.layer_button.setEnabled(False)
        self.page.preview.set_pick_enabled(False)
        self._hmi_frames += 1

    def navigate(self, action: str, dx: float = 0.0, dy: float = 0.0) -> bool:
        if self._legacy_mode:
            return super().navigate(action, dx, dy)
        if self._disposed or self._closing or self._live_phase != 'ready':
            return False
        try:
            self._live_session.camera(action, dx, dy)
            self.page.clear_point()
            self._localize_unavailable_tools()
            return True
        except (ValueError, RuntimeError, OverflowError):
            self._show_live_failure('Không thể cập nhật góc nhìn. Chọn Thử lại để khôi phục.')
            return False

    def pick_point(self, u: float, v: float) -> bool:
        if self._legacy_mode:
            return super().pick_point(u, v)
        self.page.set_status('Chọn điểm và mặt sẽ được hoàn thiện trong phiên R5.3.')
        return False

    def _layer_visibility(self, visible: bool) -> None:
        if self._legacy_mode:
            super()._layer_visibility(visible)
        else:
            self.page.layer_button.setEnabled(False)

    def _show_live_failure(self, message: str) -> None:
        self._pending_source = None
        self._current_source = None
        self._descriptor = None
        self._expected_scene_revision = None
        self._started = False
        self._live_error = message
        self.page.clear_preview('Không thể hiển thị mô hình',
                                'Không có dữ liệu 3D đang hiển thị; dữ liệu gốc không bị sửa.')
        self.page.set_status(message, is_error=True)
        self._localize_unavailable_tools()
        self.retry_button.setEnabled(True)
        self._retire_current()

    def retry(self) -> None:
        if self._closing or self._disposed or self._legacy_mode:
            return
        source = getattr(self, '_last_requested_source', None)
        if source is not None:
            self.load_ply(source)

    def _select_fallback(self, enabled: bool) -> None:
        if self._closing or self._disposed:
            return
        self._legacy_mode = enabled
        self._started = False
        self.page.preview.live_enabled = not enabled
        self.page.preview.cancel_drag()
        if enabled:
            self._pending_source = None
            self._retire_current()
            self._poll_timer.start()
            self.page.clear_preview('Chế độ xem trước an toàn', 'Chỉ hỗ trợ PLY. Tương tác theo từng thao tác.')
            self.page.set_status('Đã chuyển sang chế độ xem trước an toàn (PNG).')
        else:
            if self._process is not None:
                self._cleanup()
            self._started = False
            self.page.clear_preview('Chưa mở mô hình', 'Chọn tệp PLY hoặc OBJ để xem trực tiếp.')
            self._localize_unavailable_tools()
            self.page.set_status('Đã bật khung nhìn 3D trực tiếp.')

    @property
    def render_initialized(self) -> bool:
        if self._legacy_mode:
            return super().render_initialized
        return self._live_phase == 'ready' and not self._disposed

    @property
    def shutdown_pending(self) -> bool:
        return self._teardown is not None and self._teardown.is_alive()

    def begin_shutdown(self) -> bool:
        """Nonblocking gate used by QMainWindow.closeEvent; never orphan a child."""
        self._closing = True
        self._pending_source = None
        if self._live_session is not None:
            self._retire_current()
        if self._teardown is not None and self._teardown.is_alive():
            return False
        if self._teardown is not None:
            self._teardown.join(timeout=0)
            self._teardown = None
        if self._teardown_error is not None:
            self.page.set_status('Không thể đóng bộ hiển thị 3D an toàn. Hãy kiểm tra tiến trình con.', is_error=True)
            return False
        return True

    def dispose(self) -> None:
        if self._disposed:
            return
        if not self.begin_shutdown():
            return
        self._poll_timer.stop()
        super().dispose()
