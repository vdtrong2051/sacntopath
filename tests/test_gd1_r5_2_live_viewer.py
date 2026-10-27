"""R5.2 UI contract and fake-session acceptance; no native GPU in pytest."""
from __future__ import annotations

from concurrent.futures import Future
from pathlib import Path
import ast
import os
import queue
import sys
import time
from types import SimpleNamespace

import pytest

ROOT = Path(__file__).resolve().parents[1]


def test_r52_no_native_vtk_imports_in_presentation():
    folder = ROOT / 'src/scantopath/modules/viewer3d/presentation'
    for filename in ('live_controller.py', 'live_view.py'):
        tree = ast.parse((folder / filename).read_text('utf-8'))
        names = []
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                names.extend(alias.name for alias in node.names)
            elif isinstance(node, ast.ImportFrom):
                names.append(node.module or '')
        assert not any(x.startswith(('vtk', 'scantopath.modules.viewer3d.infrastructure')) for x in names)


def test_r52_composition_root_contains_bounded_close_gate():
    main = (ROOT / 'src/scantopath/ui/shell/main_window.py').read_text('utf-8')
    bootstrap = (ROOT / 'src/scantopath/ui/shell/viewer_bootstrap.py').read_text('utf-8')
    assert 'controller = create_viewer_controller(self)' in main
    assert 'LiveViewer3DController(' in bootstrap
    assert 'Viewer3DController(parent)' in bootstrap
    assert "('offscreen', 'minimal')" in bootstrap
    assert 'CoalescingRenderSession(' in bootstrap
    assert "getattr(self.viewer3d, 'begin_shutdown', lambda: True)()" in main
    assert 'QTimer.singleShot(120, self.close)' in main
    assert len(main.splitlines()) < 500


class FakeSession:
    """Record real controller scheduling, not a mock of camera math or UI."""
    counter = 0

    def __init__(self):
        FakeSession.counter += 1
        self.pid = 10000 + FakeSession.counter
        self.frames = queue.Queue()
        self.stopped = False
        self.cameras = []
        self.rev = 0

    def start(self):
        future = Future()
        future.set_result(True)
        return future

    def open_source(self, path):
        future = Future()
        mesh = str(path).endswith('.obj')
        desc = {'name': Path(path).name, 'source_sha256': 'a' * 64,
                'source_bytes': 150, 'source_format': 'obj' if mesh else 'ply',
                'geometry_kind': 'mesh' if mesh else 'points',
                'point_count': 4, 'face_count': 1 if mesh else 0,
                'bounds': [0, 1, 0, 1, 0, 1], 'has_rgb': False,
                'units': 'unknown', 'coordinate_frame': 'unknown',
                'scene_revision': 1}
        self.frames.put(self._frame(0))
        future.set_result(desc)
        return future

    def _frame(self, input_revision):
        self.rev += 1
        return SimpleNamespace(scene_revision=1, frame_revision=self.rev,
                               input_revision=input_revision, width=128, height=128,
                               host_pid=self.pid, rgb=b'\x30\x60\x90' * (128 * 128))

    @property
    def statistics(self):
        return {'input_revision': len(self.cameras)}

    def camera(self, action, dx, dy):
        self.cameras.append((action, dx, dy))
        self.frames.put(self._frame(len(self.cameras)))
        return len(self.cameras)

    def next_frame(self, *, timeout=0.0):
        try:
            return self.frames.get_nowait()
        except queue.Empty as exc:
            raise TimeoutError('NO_FRAME') from exc

    def stop(self, *, timeout=2.0):
        self.stopped = True


@pytest.fixture
def qt_env(monkeypatch):
    pytest.importorskip('PySide6')
    from PySide6.QtWidgets import QApplication
    app = QApplication.instance() or QApplication([])
    # Bypass the production offscreen guard for a fake-session-only test.
    monkeypatch.delenv('QT_QPA_PLATFORM', raising=False)
    return app


def _pump(app, controller, n=8):
    for _ in range(n):
        controller._poll_live()
        app.processEvents()
        time.sleep(.01)


def test_r52_live_open_and_incremental_camera(qt_env, tmp_path):
    from PySide6.QtWidgets import QWidget
    from scantopath.modules.viewer3d.presentation.live_controller import LiveViewer3DController
    sessions = []
    def factory():
        s = FakeSession()
        sessions.append(s)
        return s
    parent = QWidget()
    viewer = LiveViewer3DController(parent, session_factory=factory)
    source = tmp_path / 'cloud.ply'
    source.write_text('ply fixture', encoding='ascii')
    try:
        assert viewer.load_ply(source)
        _pump(qt_env, viewer)
        assert viewer.live_phase == 'ready'
        assert viewer.frames_presented_to_qt >= 1
        assert viewer.navigate('orbit', 4, 2)
        _pump(qt_env, viewer)
        assert sessions[0].cameras[0] == ('orbit', 4, 2)
        assert viewer.frames_presented_to_qt >= 2
        assert viewer.page.preview.objectName() == 'viewer3dPreview'
        assert not viewer.page.preview._pick_enabled
    finally:
        viewer.begin_shutdown()
        deadline = time.monotonic() + 3
        while not viewer.begin_shutdown() and time.monotonic() < deadline:
            time.sleep(.01)
        viewer.dispose()


def test_r52_scene_switch_drops_old_frames(qt_env, tmp_path):
    from PySide6.QtWidgets import QWidget
    from scantopath.modules.viewer3d.presentation.live_controller import LiveViewer3DController
    sessions = []
    def factory():
        s = FakeSession()
        sessions.append(s)
        return s
    parent = QWidget()
    viewer = LiveViewer3DController(parent, session_factory=factory)
    src1 = tmp_path / 'one.ply'
    src2 = tmp_path / 'two.obj'
    src1.write_text('a')
    src2.write_text('b')
    try:
        assert viewer.load_ply(src1)
        _pump(qt_env, viewer)
        assert viewer._descriptor.geometry_kind == 'points'
        assert viewer.load_ply(src2)
        deadline = time.monotonic() + 5
        while viewer.live_phase != 'ready' and time.monotonic() < deadline:
            _pump(qt_env, viewer)
        assert viewer.live_phase == 'ready'
        assert viewer._descriptor.geometry_kind == 'mesh'
        assert sessions[0].stopped
        assert viewer._live_session is sessions[1]
    finally:
        viewer.begin_shutdown()
        deadline = time.monotonic() + 3
        while viewer._teardown is not None and viewer._teardown.is_alive() and time.monotonic() < deadline:
            time.sleep(.01)
        viewer.dispose()


def test_r52_bad_frame_rejected_and_failure_recoverable(qt_env, tmp_path):
    from PySide6.QtWidgets import QWidget
    from scantopath.modules.viewer3d.presentation.live_controller import LiveViewer3DController
    instances = []
    def factory():
        item = FakeSession()
        instances.append(item)
        return item
    parent = QWidget()
    viewer = LiveViewer3DController(parent, session_factory=factory)
    source = tmp_path / 'cloud.ply'
    source.write_text('data')
    try:
        viewer.load_ply(source)
        _pump(qt_env, viewer)
        before = viewer.frames_presented_to_qt
        bad = instances[0]._frame(0)
        bad.scene_revision = 0
        instances[0].frames.put(bad)
        _pump(qt_env, viewer)
        assert viewer.frames_presented_to_qt == before
        viewer._show_live_failure('Bo hien thi loi')
        assert viewer.retry_button.isEnabled()
        viewer.retry()
        deadline = time.monotonic() + 5
        while viewer.live_phase != 'ready' and time.monotonic() < deadline:
            _pump(qt_env, viewer)
        assert viewer.live_phase == 'ready'
        assert instances[0].stopped
    finally:
        viewer.begin_shutdown()
        deadline = time.monotonic() + 3
        while viewer._teardown is not None and viewer._teardown.is_alive() and time.monotonic() < deadline:
            time.sleep(.01)
        viewer.dispose()


def test_r52_image_copy_and_invalid_length(qt_env):
    from scantopath.modules.viewer3d.presentation.live_view import rgb_snapshot_to_pixmap
    frame = SimpleNamespace(width=128, height=128, rgb=b'\x01\x02\x03' * (128*128))
    pix = rgb_snapshot_to_pixmap(frame)
    assert not pix.isNull() and pix.width() == 128
    frame.rgb = b'broken'
    with pytest.raises(ValueError, match='INVALID_RGB_FRAME'):
        rgb_snapshot_to_pixmap(frame)
