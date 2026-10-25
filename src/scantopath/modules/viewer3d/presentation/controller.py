"""Viewer MVC controller: supervise isolated VTK fixture-render process.

Never instantiate QVTKRenderWindowInteractor inside the desktop process:
a native OpenGL/Qt fault is not a catchable Python exception.
"""
from __future__ import annotations

import os
from pathlib import Path
import sys
import tempfile

from PySide6.QtCore import QObject, QProcess, QThread, QTimer
from PySide6.QtWidgets import QWidget

from .view import Viewer3DPage


class Viewer3DController(QObject):
    """One-shot VTK fixture preview, safely isolated from the application GUI."""

    TIMEOUT_MS = 30000
    MAX_LOG_BYTES = 8192
    MAX_PNG_BYTES = 8 * 1024 * 1024

    def __init__(self, parent: QWidget) -> None:
        super().__init__(parent)
        self.page = Viewer3DPage(parent)
        self._process: QProcess | None = None
        self._timeout: QTimer | None = None
        self._temp: tempfile.TemporaryDirectory | None = None
        self._image_path: Path | None = None
        self._log = b''
        self._started = False
        self._disposed = False
        self._render_pending = False
        self._attempted = False
        self._timed_out = False

    def activate(self) -> None:
        if self._disposed or self._started or self._render_pending or self._attempted:
            return
        if os.environ.get('QT_QPA_PLATFORM', '').lower() == 'offscreen':
            self.page.set_status('FIXTURE 08.02 · Qt offscreen chỉ kiểm tra UI; cần Windows HMI để render VTK.')
            return
        self._render_pending = True
        QTimer.singleShot(0, self._start_preview)

    def _start_preview(self) -> None:
        if self._disposed or not self._render_pending:
            return
        self._render_pending = False
        self._attempted = True
        if QThread.currentThread() != self.thread():
            raise RuntimeError('Viewer controller requires Qt GUI thread')
        try:
            self._temp = tempfile.TemporaryDirectory(prefix='scantopath-vtk-')
            self._image_path = Path(self._temp.name) / 'fixture.png'
            self._log = b''
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
            self._timed_out = False
            self.page.set_status('FIXTURE 08.02 · Đang tạo hình VTK trong tiến trình cách ly…')
            process.start(sys.executable, [
                '-X', 'faulthandler', '-m',
                'scantopath.modules.viewer3d.infrastructure.render_preview',
                '--output', str(self._image_path),
            ])
            timer.start(self.TIMEOUT_MS)
        except (OSError, RuntimeError) as exc:
            self.page.set_status(f'VTK chưa thể khởi động: {type(exc).__name__}: {exc}')
            self._cleanup()

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
            self.page.set_status('Không thể khởi chạy VTK subprocess: kiểm tra Python/venv.')
            self._cleanup()

    def _finished(self, code: int, status: QProcess.ExitStatus) -> None:
        self._read_output()
        if self._disposed:
            self._cleanup()
            return
        ok = (not self._timed_out and status == QProcess.NormalExit and code == 0
              and b'SCANTOPATH_VTK_PREVIEW_OK' in self._log)
        if ok and self._image_path is not None:
            try:
                if self._image_path.stat().st_size > self.MAX_PNG_BYTES:
                    raise ValueError('VTK preview exceeds size limit')
                png = self._image_path.read_bytes()
                ok = self.page.show_png(png)
            except (OSError, ValueError):
                ok = False
        if ok:
            self._started = True
            self.page.set_status('FIXTURE 08.02 · 5 điểm render bằng VTK (tiến trình riêng) · Chưa hỗ trợ tương tác/PLY.')
        else:
            code_hex = f'0x{(int(code) & 0xFFFFFFFF):08X}'
            reason = 'timeout' if self._timed_out else ('native crash' if status == QProcess.CrashExit else 'failed')
            tail = self._log.decode('utf-8', 'replace')[-500:].replace('\n', ' ')
            self.page.set_status(f'VTK isolated render {reason}, exit={code_hex}. Qt vẫn an toàn. {tail}')
            print('ScanToPath 08.02 VTK child failure:',reason,code_hex,tail,file=sys.stderr,flush=True)
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

    @property
    def render_initialized(self) -> bool:
        return self._started and not self._disposed

    def dispose(self) -> None:
        if self._disposed:
            return
        self._disposed = True
        self._render_pending = False
        self._cleanup()
