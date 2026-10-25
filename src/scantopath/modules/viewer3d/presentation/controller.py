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
from .view import Viewer3DPage


class Viewer3DController(QObject):
    """Qt GUI owner of a read-only child render job, not of the VTK renderer."""

    TIMEOUT_MS = 60000
    MAX_LOG_BYTES = 8192
    MAX_PNG_BYTES = 8 * 1024 * 1024
    MAX_JSON_BYTES = 4096

    def __init__(self, parent: QWidget) -> None:
        super().__init__(parent)
        self.page = Viewer3DPage(parent)
        self.page.open_ply_requested.connect(self._choose_ply)
        self._process: QProcess | None = None
        self._timeout: QTimer | None = None
        self._temp: tempfile.TemporaryDirectory | None = None
        self._image_path: Path | None = None
        self._metadata_path: Path | None = None
        self._log = b''
        self._started = False
        self._disposed = False
        self._render_pending = False
        self._attempted = False
        self._timed_out = False
        self._job_kind = 'fixture'
        self._source_path: Path | None = None

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
            self.page.show_failure('PLY không hợp lệ: Hãy chọn tệp .ply có thể đọc được.')
            return False
        if os.environ.get('QT_QPA_PLATFORM', '').lower() == 'offscreen':
            self.page.set_status('PLY 08.03 · Qt offscreen không chạy native render; cần HMI Windows.')
            return False
        self._render_pending = False
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
            self._metadata_path = Path(self._temp.name) / 'metadata.json' if kind == 'ply' else None
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
            else:
                raise ValueError('Unsupported viewer job')
            process.start(sys.executable, ['-X', 'faulthandler', '-m', module, *args])
            timer.start(self.TIMEOUT_MS)
            return True
        except (OSError, RuntimeError, ValueError) as exc:
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
            self.page.show_failure('Không thể khởi chạy VTK: kiểm tra Python/venv.')
            self._cleanup()

    def _finished(self, code: int, status: QProcess.ExitStatus) -> None:
        self._read_output()
        if self._disposed:
            self._cleanup()
            return
        marker = (b'SCANTOPATH_PLY_PREVIEW_OK' if self._job_kind == 'ply'
                  else b'SCANTOPATH_VTK_PREVIEW_OK')
        ok = (not self._timed_out and status == QProcess.NormalExit and code == 0
              and marker in self._log)
        summary: PlySummary | None = None
        if ok and self._image_path is not None:
            try:
                if self._image_path.stat().st_size > self.MAX_PNG_BYTES:
                    raise ValueError('VTK preview exceeds size limit')
                png = self._image_path.read_bytes()
                if self._job_kind == 'ply':
                    if self._metadata_path is None or self._metadata_path.stat().st_size > self.MAX_JSON_BYTES:
                        raise ValueError('Invalid PLY metadata result')
                    summary = PlySummary.from_result(json.loads(
                        self._metadata_path.read_text(encoding='utf-8')))
                    if self._source_path is None or summary.name != self._source_path.name:
                        raise ValueError('PLY result does not match selected file')
                ok = self.page.show_png(png)
            except (OSError, ValueError, UnicodeError, json.JSONDecodeError):
                ok = False
        if ok:
            self._started = True
            if summary is None:
                self.page.show_fixture()
                self.page.set_status('FIXTURE 08.02 · 5 điểm VTK · Nhấn Mở PLY để nhập dữ liệu (chưa tương tác 3D).')
            else:
                self.page.show_ply(summary)
                self.page.set_status(
                    f'PLY 08.03 · {summary.point_count:,} điểm · '
                    'Dữ liệu nhập từ tệp, chưa xác nhận đơn vị/hệ tọa độ.')
        else:
            self._started = False
            code_hex = f'0x{(int(code) & 0xFFFFFFFF):08X}'
            reason = 'timeout' if self._timed_out else ('native crash' if status == QProcess.CrashExit else 'failed')
            if self._job_kind == 'ply' and b'SCANTOPATH_PLY_REJECTED:HEADER_TERMINATOR' in self._log:
                notice = 'PLY không hợp lệ: thiếu end_header hoặc phần đầu tệp quá dài.'
            elif self._job_kind == 'ply' and b'SCANTOPATH_PLY_REJECTED:INVALID' in self._log:
                notice = 'PLY không hợp lệ hoặc không được hỗ trợ. Kiểm tra cấu trúc và dữ liệu XYZ.'
            elif self._timed_out:
                notice = 'VTK xử lý quá thời gian cho phép. Ứng dụng vẫn hoạt động.'
            elif status == QProcess.CrashExit:
                notice = f'VTK native crash (exit={code_hex}); ứng dụng vẫn hoạt động.'
            else:
                notice = f'Không thể hiển thị dữ liệu bằng VTK (exit={code_hex}); ứng dụng vẫn hoạt động.'
            self.page.show_failure(notice)
            # Retain bounded diagnostics in stderr only; never print traceback in a GUI label.
            tail = self._log.decode('utf-8', 'backslashreplace')[-400:].replace('\n', ' ')
            print('ScanToPath 08.03 VTK child failure:', reason, code_hex, repr(tail),
                  file=sys.stderr, flush=True)
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
