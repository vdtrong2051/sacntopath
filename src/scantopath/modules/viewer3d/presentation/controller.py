"""Viewer MVC controller: owns GUI-thread VTK host lifetime, not geometry/data I/O."""
from __future__ import annotations

import os
from collections.abc import Callable

from PySide6.QtCore import QObject, QTimer, QThread
from PySide6.QtWidgets import QWidget

from .view import Viewer3DPage
from ..application.ports import FixtureScenePort


class Viewer3DController(QObject):
    """Lazy VTK fixture; missing VTK is visible, not a fake successful render."""

    def __init__(self, parent: QWidget, *, scene_factory: Callable[[], FixtureScenePort]) -> None:
        super().__init__(parent)
        self.page = Viewer3DPage(parent)
        self._scene_factory = scene_factory
        self._scene: FixtureScenePort | None = None
        self._host: QWidget | None = None
        self._started = False
        self._disposed = False
        self._render_pending = False

    def activate(self) -> None:
        if self._disposed or self._started or self._render_pending:
            return
        # Qt's offscreen platform cannot prove OpenGL/physical GPU behavior.
        # Avoid creating a native VTK render window in offscreen regression runs.
        if os.environ.get('QT_QPA_PLATFORM', '').lower() == 'offscreen':
            self.page.set_status('FIXTURE 08.02 · GPU render hoãn trong Qt offscreen; kiểm tra HMI Windows bắt buộc.')
            return
        self._render_pending = True
        QTimer.singleShot(0, self._initialize)

    def _initialize(self) -> None:
        self._render_pending = False
        if self._disposed or self._started:
            return
        if QThread.currentThread() != self.thread():
            raise RuntimeError('VTK renderer must be initialized on the GUI thread')
        try:
            import vtkmodules.qt
            # Matches the 08.01 Windows probe; never select a second Qt binding.
            vtkmodules.qt.PyQtImpl = 'PySide6'
            from vtkmodules.qt.QVTKRenderWindowInteractor import QVTKRenderWindowInteractor
            host = QVTKRenderWindowInteractor(self.page)
            self._host = host
            scene = self._scene_factory()
            self._scene = scene
            render_window = host.GetRenderWindow()
            render_window.AddRenderer(scene.renderer)
            self.page.mount(host)
            host.Initialize()
            self._started = True
            QTimer.singleShot(0, self._render)
        except (ImportError, RuntimeError, OSError) as exc:
            self.page.set_status(f'Không khởi tạo được VTK: {type(exc).__name__}. Cần cài viewer extra và kiểm tra môi trường.')
            self.dispose()

    def _render(self) -> None:
        if not self._started or self._disposed or self._host is None or self._scene is None:
            return
        if QThread.currentThread() != self.thread():
            raise RuntimeError('VTK Render() called outside GUI thread')
        try:
            self._host.GetRenderWindow().Render()
        except (RuntimeError, OSError) as exc:
            self.page.set_status(f'Lỗi VTK Render: {type(exc).__name__}')
            self.dispose()
            return
        self.page.set_status(f'FIXTURE 08.02 · {self._scene.point_count} điểm tổng hợp · Chưa nhập PLY · Chưa đo.')

    @property
    def render_initialized(self) -> bool:
        return self._started and not self._disposed

    def dispose(self) -> None:
        if self._disposed:
            return
        self._disposed = True
        if self._host is not None:
            try:
                self._host.Finalize()
            finally:
                self.page.unmount()
                self._host.close()
                self._host.deleteLater()
                self._host = None
        if self._scene is not None:
            self._scene.dispose()
            self._scene = None
