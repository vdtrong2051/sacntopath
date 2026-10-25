"""08.03 MVC controller: asynchronous isolated VTK preview for fixture and local PLY.

The ScanToPath GUI never imports VTK or parses arbitrary point clouds itself.
Native OpenGL failures can crash only the disposable child process.
"""
from __future__ import annotations
import json
import os
from pathlib import Path
import sys
import tempfile

from PySide6.QtCore import QObject, QProcess, QThread, QTimer
from PySide6.QtWidgets import QFileDialog, QWidget

from ..application.ply_contracts import PlySummary
from ..application.navigation import CameraView
from ..application.picking import PickResult
from .view import Viewer3DPage


class Viewer3DController(QObject):
    """Qt GUI owner of a read-only child render job, not of the VTK renderer."""

    TIMEOUT_MS = 60000
    MAX_LOG_BYTES = 8192
    MAX_PNG_BYTES = 8 * 1024 * 1024
    MAX_JSON_BYTES = 4096
    MAX_PICK_BYTES = 2048

    def __init__(self, parent: QWidget) -> None:
        super().__init__(parent)
        self.page = Viewer3DPage(parent)
        self.page.open_ply_requested.connect(self._choose_ply)
        self.page.navigation_requested.connect(self.navigate)
        self.page.point_requested.connect(self.pick_point)
        self.page.layer_visibility_changed.connect(self._layer_visibility)
        self._process: QProcess | None = None
        self._timeout: QTimer | None = None
        self._temp: tempfile.TemporaryDirectory | None = None
        self._image_path: Path | None = None
        self._metadata_path: Path | None = None
        self._pick_path: Path | None = None
        self._log = b''
        self._started = False
        self._disposed = False
        self._render_pending = False
        self._attempted = False
        self._timed_out = False
        self._job_kind = 'fixture'
        self._source_path: Path | None = None
        self._display_kind = 'fixture'
        self._display_ply: Path | None = None
        self._display_summary: PlySummary | None = None
        self._view_state = CameraView()
        self._pending_view: CameraView | None = None
        self._pending_pick: tuple[float, float] | None = None
        self._selected_point: PickResult | None = None

    def activate(self) -> None:
        if self._disposed or self._started or self._render_pending or self._attempted:
            return
        # Offscreen Qt tests verify composition; they do not establish Windows
        # OpenGL/driver compatibility (and must not start real renderer children).
        if os.environ.get('QT_QPA_PLATFORM', '').lower() == 'offscreen':
            self.page.set_status('FIXTURE 08.02 · Qt offscreen chỉ kiểm tra UI; cần Windows HMI để render VTK.')
            return
        self._render_pending = True
        QTimer.singleShot(0, self._start_preview)

    def navigate(self, action: str, dx: float = 0.0, dy: float = 0.0) -> bool:
        """Queue one camera update; no GUI/native render reentrancy or stale state."""
        if self._disposed or not self._started or self._process is not None or self._render_pending:
            return False
        if os.environ.get('QT_QPA_PLATFORM', '').lower() == 'offscreen':
            return False
        try:
            candidate = self._view_state.update(action, dx, dy)
        except (TypeError, ValueError, OverflowError):
            self.page.set_status('Lệnh điều khiển góc nhìn không hợp lệ.', is_error=True)
            return False
        self._pending_view = candidate
        if not self._start_job('navigation', self._display_ply):
            self._pending_view = None
            return False
        return True

    def _layer_visibility(self, visible: bool) -> None:
        if not visible:
            self._selected_point = None

    def pick_point(self, u: float, v: float) -> bool:
        """Select one visible point via isolated VTK, never via Python GUI geometry."""
        if (self._disposed or not self._started or self._process is not None
                or self._render_pending or not self.page.layer_button.isChecked()):
            return False
        if os.environ.get('QT_QPA_PLATFORM','').lower() == 'offscreen':
            return False
        try:
            if any(type(q) not in (int,float) or not 0<=q<=1 for q in (u,v)):
                raise ValueError('Invalid pixel')
        except (TypeError, ValueError):
            return False
        self._pending_pick=(float(u),float(v))
        if not self._start_job('picking',self._display_ply):
            self._pending_pick=None
            return False
        return True

    def _choose_ply(self) -> None:
        if self._disposed or self._process is not None:
            return
        name, _ = QFileDialog.getOpenFileName(self.page, 'Mở point cloud PLY', '', 'PLY (*.ply)')
        if name:
            self.load_ply(name)

    def load_ply(self, filename: str | Path) -> bool:
        """Start a read-only, asynchronous PLY preview. No VTK in Qt process."""
        if self._disposed or self._process is not None:
            return False
        try:
            source = Path(filename)
            if source.suffix.lower() != '.ply' or not source.is_file() or source.is_symlink():
                raise ValueError('Hãy chọn một tệp .ply có thật (không qua symbolic link)')
        except (TypeError, OSError, ValueError) as exc:
            self._started = False
            self._selected_point = None
            self.page.show_failure('PLY không hợp lệ: Hãy chọn tệp .ply có thể đọc được.')
            return False
        if os.environ.get('QT_QPA_PLATFORM', '').lower() == 'offscreen':
            self.page.set_status('PLY 08.03 · Qt offscreen không chạy native render; cần HMI Windows.')
            return False
        self._render_pending = False
        self._selected_point = None
        self.page.clear_point()
        return self._start_job('ply', source)

    def _start_preview(self) -> None:
        if self._disposed or not self._render_pending:
            return
        self._render_pending = False
        self._attempted = True
        self._start_job('fixture', None)

    def _start_job(self, kind: str, source: Path | None) -> bool:
        if self._disposed or self._process is not None or QThread.currentThread() != self.thread():
            return False
        try:
            if kind == 'ply':
                # Never attribute a previous cloud/image to a failed import.
                self._started = False
                self.page.clear_preview('Đang tải PLY…', 'PLY đang được kiểm tra; chưa có dữ liệu mới.')
            self._temp = tempfile.TemporaryDirectory(prefix='scantopath-vtk-')
            self._image_path = Path(self._temp.name) / 'preview.png'
            self._metadata_path = Path(self._temp.name) / 'metadata.json' if kind in ('ply', 'navigation') and source is not None else None
            self._pick_path = Path(self._temp.name) / 'pick.json' if kind == 'picking' else None
            self._source_path = source
            self._job_kind = kind
            self._log = b''
            self._timed_out = False
            process = QProcess(self)
            process.setProcessChannelMode(QProcess.MergedChannels)
            process.readyReadStandardOutput.connect(self._read_output)
            process.finished.connect(self._finished)
            process.errorOccurred.connect(self._process_error)
            self._process = process
            timer = QTimer(self)
            timer.setSingleShot(True)
            timer.timeout.connect(self._timed_out_render)
            self._timeout = timer
            self.page.set_loading(True)
            if kind == 'fixture':
                module = 'scantopath.modules.viewer3d.infrastructure.render_preview'
                args = ['--output', str(self._image_path)]
                self.page.set_status('FIXTURE 08.02 · Đang tạo hình VTK trong tiến trình cách ly…')
            elif kind == 'ply' and source is not None and self._metadata_path is not None:
                module = 'scantopath.modules.viewer3d.infrastructure.render_ply'
                args = ['--input', str(source), '--output', str(self._image_path),
                        '--metadata', str(self._metadata_path)]
                self.page.set_status('PLY 08.03 · Đang kiểm tra và tải point cloud ở tiến trình riêng…')
            elif kind == 'navigation' and self._pending_view is not None:
                module = 'scantopath.modules.viewer3d.infrastructure.render_navigation'
                args = ['--kind', self._display_kind, '--state', self._pending_view.to_json(),
                        '--output', str(self._image_path)]
                if self._display_kind == 'ply':
                    if source is None or self._display_summary is None or self._metadata_path is None:
                        raise ValueError('Missing PLY navigation source')
                    args += ['--input', str(source), '--metadata', str(self._metadata_path),
                             '--expected-sha256', self._display_summary.source_sha256]
                self.page.set_status('08.04 · Đang cập nhật góc nhìn trong tiến trình VTK cách ly…')
            elif kind == 'picking' and self._pending_pick is not None and self._pick_path is not None:
                module = 'scantopath.modules.viewer3d.infrastructure.pick_point'
                u,v = self._pending_pick
                args = ['--kind',self._display_kind,'--state',self._view_state.to_json(),
                        '--u',str(u),'--v',str(v),'--output',str(self._pick_path)]
                if self._display_kind == 'ply':
                    if source is None or self._display_summary is None:
                        raise ValueError('Missing displayed PLY for picking')
                    args += ['--input',str(source),'--expected-sha256',
                             self._display_summary.source_sha256]
                self.page.set_status('08.05 · Đang xác định điểm bằng VTK cách ly…')
            else:
                raise ValueError('Unsupported viewer job')
            process.start(sys.executable, ['-X', 'faulthandler', '-m', module, *args])
            timer.start(self.TIMEOUT_MS)
            return True
        except (OSError, RuntimeError, ValueError) as exc:
            if kind=='picking':
                self.page.clear_point('Chọn điểm thất bại.')
                self.page.set_status('Không thể khởi chạy tiến trình chọn điểm VTK.',is_error=True)
            else:
                self.page.show_failure('Không thể khởi chạy tiến trình VTK. Kiểm tra môi trường Python.')
            self._cleanup()
            return False

    def _read_output(self) -> None:
        if self._process is None:
            return
        chunk = bytes(self._process.readAllStandardOutput())
        self._log = (self._log + chunk)[-self.MAX_LOG_BYTES:]

    def _timed_out_render(self) -> None:
        self._timed_out = True
        if self._process is not None and self._process.state() != QProcess.NotRunning:
            self._process.kill()

    def _process_error(self, error: QProcess.ProcessError) -> None:
        if self._disposed:
            return
        if error == QProcess.FailedToStart:
            if self._job_kind=='picking':
                self.page.clear_point('Chọn điểm thất bại.')
                self.page.set_status('Không thể khởi chạy tiến trình chọn điểm.',is_error=True)
            else:
                self.page.show_failure('Không thể khởi chạy VTK: kiểm tra Python/venv.')
            self._cleanup()

    def _finished(self, code: int, status: QProcess.ExitStatus) -> None:
        self._read_output()
        if self._job_kind=='picking':
            self._finish_pick(code,status)
            return
        if self._disposed:
            self._cleanup()
            return
        marker = (b'SCANTOPATH_NAV_PREVIEW_OK' if self._job_kind == 'navigation'
                  else b'SCANTOPATH_PLY_PREVIEW_OK' if self._job_kind == 'ply'
                  else b'SCANTOPATH_VTK_PREVIEW_OK')
        ok = (not self._timed_out and status == QProcess.NormalExit and code == 0
              and marker in self._log)
        summary: PlySummary | None = None
        if ok and self._image_path is not None:
            try:
                if self._image_path.stat().st_size > self.MAX_PNG_BYTES:
                    raise ValueError('VTK preview exceeds size limit')
                png = self._image_path.read_bytes()
                if self._job_kind == 'ply' or (self._job_kind == 'navigation' and self._display_kind == 'ply'):
                    if self._metadata_path is None or self._metadata_path.stat().st_size > self.MAX_JSON_BYTES:
                        raise ValueError('Invalid PLY metadata result')
                    summary = PlySummary.from_result(json.loads(
                        self._metadata_path.read_text(encoding='utf-8')))
                    if self._source_path is None or summary.name != self._source_path.name:
                        raise ValueError('PLY result does not match selected file')
                    if self._job_kind == 'navigation' and (self._display_summary is None or
                            summary.source_sha256 != self._display_summary.source_sha256):
                        raise ValueError('PLY result does not match selected file')
                ok = self.page.show_png(png)
            except (OSError, ValueError, UnicodeError, json.JSONDecodeError):
                ok = False
        if ok:
            self._started = True
            if self._job_kind == 'navigation':
                self._selected_point = None
                self.page.clear_point()
                self._view_state = self._pending_view
                self.page.set_axes(self._view_state.axes)
                self.page.set_status('08.04 · Đã cập nhật góc nhìn · VTK tiến trình riêng · Chưa đo.')
            elif summary is None:
                self._selected_point = None
                self.page.clear_point()
                self._display_kind = 'fixture'
                self._display_ply = None
                self._display_summary = None
                self._view_state = CameraView()
                self.page.set_axes(False)
                self.page.show_fixture()
                self.page.set_status('FIXTURE 08.02 · 5 điểm VTK · Có thể xoay, pan và zoom ở 08.04.')
            else:
                self._selected_point = None
                self.page.clear_point()
                self._display_kind = 'ply'
                self._display_ply = self._source_path
                self._display_summary = summary
                self._view_state = CameraView()
                self.page.set_axes(False)
                self.page.show_ply(summary)
                self.page.set_status(
                    f'PLY 08.04 · {summary.point_count:,} điểm · '
                    'Dữ liệu nhập từ tệp, chưa xác nhận đơn vị/hệ tọa độ.')
        else:
            if self._job_kind != 'navigation':
                self._selected_point = None
                self.page.clear_point()
                self._started = False
                self._display_ply = None
                self._display_summary = None
            code_hex = f'0x{(int(code) & 0xFFFFFFFF):08X}'
            reason = 'timeout' if self._timed_out else ('native crash' if status == QProcess.CrashExit else 'failed')
            if self._job_kind == 'ply' and b'SCANTOPATH_PLY_REJECTED:HEADER_TERMINATOR' in self._log:
                notice = 'PLY không hợp lệ: thiếu end_header hoặc phần đầu tệp quá dài.'
            elif self._job_kind == 'ply' and b'SCANTOPATH_PLY_REJECTED:INVALID' in self._log:
                notice = 'PLY không hợp lệ hoặc không được hỗ trợ. Kiểm tra cấu trúc và dữ liệu XYZ.'
            elif self._job_kind == 'navigation' and b'SCANTOPATH_NAV_REJECTED:SOURCE_CHANGED' in self._log:
                notice = 'Tệp PLY đã thay đổi sau khi nhập. Vui lòng mở lại tệp.'
            elif self._timed_out:
                notice = 'VTK xử lý quá thời gian cho phép. Ứng dụng vẫn hoạt động.'
            elif status == QProcess.CrashExit:
                notice = f'VTK native crash (exit={code_hex}); ứng dụng vẫn hoạt động.'
            else:
                notice = f'Không thể hiển thị dữ liệu bằng VTK (exit={code_hex}); ứng dụng vẫn hoạt động.'
            if self._job_kind == 'navigation':
                self.page.set_status('08.04 · Góc nhìn KHÔNG cập nhật: ' + notice, is_error=True)
                self.page.set_axes(self._view_state.axes)
            else:
                self.page.show_failure(notice)
            # Retain bounded diagnostics in stderr only; never print traceback in a GUI label.
            tail = self._log.decode('utf-8', 'backslashreplace')[-400:].replace('\n', ' ')
            print('ScanToPath 08.03 VTK child failure:', reason, code_hex, repr(tail),
                  file=sys.stderr, flush=True)
        self._pending_view = None
        self._cleanup()

    def _finish_pick(self, code: int, status: QProcess.ExitStatus) -> None:
        if self._disposed:
            self._cleanup()
            return
        good = (not self._timed_out and status==QProcess.NormalExit and code==0
                and b'SCANTOPATH_POINT_PICK_OK' in self._log)
        picked: PickResult | None = None
        if good and self._pick_path is not None:
            try:
                if not 8 <= self._pick_path.stat().st_size <= self.MAX_PICK_BYTES:
                    raise ValueError('Invalid pick output size')
                picked = PickResult.from_result(json.loads(self._pick_path.read_text('utf-8')))
                expected = (self._display_summary.source_sha256 if self._display_kind=='ply'
                            and self._display_summary is not None else 'fixture:08.02')
                if picked.source_id != expected:
                    raise ValueError('Pick result mismatches displayed source')
                max_points = (self._display_summary.point_count if self._display_kind=='ply'
                              and self._display_summary is not None else 5)
                if picked.hit and picked.point_id >= max_points:
                    raise ValueError('Pick ID outside point cloud bounds')
            except (OSError,ValueError,UnicodeError):
                good=False
        else:
            good=False
        if good and picked is not None:
            self._selected_point = picked if picked.hit else None
            self.page.show_point(picked)
            if picked.hit:
                self.page.set_status(f'08.05 · Đã chọn Point ID {picked.point_id} · Tọa độ chưa hiệu chuẩn.')
            else:
                self.page.set_status('08.05 · Không có điểm tại vị trí nhấn. Ảnh hiện tại không đổi.')
        else:
            self._selected_point=None
            self.page.clear_point('Chọn điểm không thành công.')
            if b'SCANTOPATH_POINT_PICK_REJECTED:SOURCE_CHANGED' in self._log:
                notice='PLY đã thay đổi sau khi mở. Hãy nhập lại tệp.'
            elif self._timed_out:
                notice='Chọn điểm quá thời gian. Ứng dụng vẫn hoạt động.'
            else:
                notice='Không chọn được điểm bằng tiến trình VTK. Ứng dụng vẫn hoạt động.'
            self.page.set_status('08.05 · '+notice,is_error=True)
            tail=self._log.decode('utf-8','backslashreplace')[-200:].replace('\n',' ')
            print('ScanToPath 08.05 pick child failed:',repr(tail),file=sys.stderr,flush=True)
        self._pending_pick=None
        self._cleanup()

    def _cleanup(self) -> None:
        if self._timeout is not None:
            self._timeout.stop()
            self._timeout.deleteLater()
            self._timeout = None
        if self._process is not None:
            if self._process.state() != QProcess.NotRunning:
                self._process.kill()
                self._process.waitForFinished(200)
            self._process.deleteLater()
            self._process = None
        if self._temp is not None:
            self._temp.cleanup()
            self._temp = None
        self._image_path = None
        self._metadata_path = None
        self._pick_path = None
        self._source_path = None
        self.page.set_loading(False)

    @property
    def render_initialized(self) -> bool:
        return self._started and not self._disposed

    def dispose(self) -> None:
        if self._disposed:
            return
        self._disposed = True
        self._render_pending = False
        self._cleanup()
