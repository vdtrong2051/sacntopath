"""08.03 Qt viewer: no VTK in GUI; offscreen verifies contracts, not GPU."""
from __future__ import annotations
import os
import pytest
os.environ.setdefault('QT_QPA_PLATFORM','offscreen')
pytest.importorskip('PySide6')
from PySide6.QtWidgets import QApplication, QPushButton
from PySide6.QtCore import QProcess
from PySide6.QtGui import QImage
from scantopath.application.contracts import WorkspaceId
from scantopath.ui.shell import ScanToPathMainWindow


@pytest.fixture
def window():
    app=QApplication.instance() or QApplication([])
    w=ScanToPathMainWindow()
    w.nav_buttons[WorkspaceId.INSPECT3D].click()
    app.processEvents()
    yield w
    w.close();app.processEvents()


def test_ui_exposes_ply_file_action_without_importing_vtk(window):
    """Check lazy VTK loading in a CLEAN interpreter, not shared pytest sys.modules.

    Earlier real VTK fixture tests deliberately load vtkmodules into pytest's
    process; that must not make a lazy-import GUI test order-dependent.
    """
    page = window.page_for(WorkspaceId.INSPECT3D)
    button = page.findChild(QPushButton, 'viewer3dOpenPlyButton')
    assert button is not None and button.isEnabled()

    import subprocess
    import sys
    from pathlib import Path

    root = Path(__file__).resolve().parents[3]
    script = """
import sys
from PySide6.QtWidgets import QApplication, QPushButton
from scantopath.application.contracts import WorkspaceId
from scantopath.ui.shell import ScanToPathMainWindow

assert not any(name.startswith('vtkmodules') for name in sys.modules)
app = QApplication([])
window = ScanToPathMainWindow()
try:
    window.nav_buttons[WorkspaceId.INSPECT3D].click()
    app.processEvents()
    page = window.page_for(WorkspaceId.INSPECT3D)
    button = page.findChild(QPushButton, 'viewer3dOpenPlyButton')
    assert button is not None and button.isEnabled()
    assert 'scantopath.modules.viewer3d.infrastructure.render_ply' not in sys.modules
    assert not any(name.startswith('vtkmodules') for name in sys.modules)
finally:
    window.close()
    app.processEvents()
print('08.03 isolated Qt lazy-import PASS')
"""
    env = {
        **os.environ,
        'QT_QPA_PLATFORM': 'offscreen',
        'PYTHONPATH': str(root / 'src') + os.pathsep + os.environ.get('PYTHONPATH', ''),
    }
    completed = subprocess.run(
        [sys.executable, '-c', script], cwd=root, env=env,
        capture_output=True, text=True, timeout=35, check=False,
    )
    assert completed.returncode == 0, (
        f'Fresh-interpreter Qt lazy-import failed (exit={completed.returncode})\n'
        f'stdout: {completed.stdout}\nstderr: {completed.stderr}'
    )
    assert '08.03 isolated Qt lazy-import PASS' in completed.stdout


def test_invalid_path_does_not_launch_or_exit(window,tmp_path):
    controller=window.viewer3d
    assert controller.load_ply(tmp_path/'missing.ply') is False
    assert 'PLY không hợp lệ' in controller.page.state.text()
    assert controller._process is None
    assert not controller._disposed


def test_valid_ply_offscreen_is_not_falsely_marked_rendered(window,tmp_path):
    source=tmp_path/'valid.ply'
    source.write_text('ply\nformat ascii 1.0\nelement vertex 1\n'
                      'property float x\nproperty float y\nproperty float z\nend_header\n0 0 0\n')
    assert window.viewer3d.load_ply(source) is False
    assert 'offscreen' in window.viewer3d.page.state.text()
    assert window.viewer3d._process is None


def test_child_crash_keeps_window_usable(window):
    c=window.viewer3d
    c._process=QProcess(c)
    c._job_kind='ply'
    c._log=b'fake driver error'
    c._finished(-1073741819,QProcess.CrashExit)
    assert 'native crash' in c.page.state.text()
    assert c._process is None and not c._disposed
    window.nav_buttons[WorkspaceId.PROJECTS].click()
    assert window.active_workspace==WorkspaceId.PROJECTS


def test_isolated_success_updates_ply_label_without_vtk_import(window,tmp_path):
    import json
    from PySide6.QtCore import QBuffer, QIODevice, Qt
    from PySide6.QtGui import QImage
    from scantopath.modules.viewer3d.application.ply_contracts import PlySummary
    c=window.viewer3d
    img=QImage(32,32,QImage.Format_RGB32)
    img.fill(Qt.blue)
    buffer=QBuffer()
    assert buffer.open(QIODevice.WriteOnly)
    assert img.save(buffer,'PNG')
    png=tmp_path/'preview.png'
    png.write_bytes(bytes(buffer.data()))
    buffer.close()
    summary={
        'name':'fixture_import.ply','source_sha256':'a'*64,'source_bytes':125,
        'point_count':4,'bounds':[0,1,0,2,0,3],
        'has_rgb':True,'ply_format':'ascii','units':'unknown','coordinate_frame':'unknown',
    }
    metadata=tmp_path/'metadata.json';metadata.write_text(json.dumps(summary),encoding='utf-8')
    c._job_kind='ply';c._image_path=png;c._metadata_path=metadata
    c._source_path=tmp_path/'fixture_import.ply'
    c._process=QProcess(c);c._log=b'SCANTOPATH_PLY_PREVIEW_OK'
    c._finished(0,QProcess.NormalExit)
    assert c.render_initialized
    assert '4 điểm' in c.page.state.text()
    assert 'X[0, 1]' in c.page.note.text()
    assert 'chưa xác nhận' in c.page.note.text()
    assert c._process is None


def test_invalid_ply_child_error_clears_previous_preview(window, tmp_path):
    from PySide6.QtCore import QBuffer, QIODevice, Qt
    from PySide6.QtGui import QImage, QPixmap
    c = window.viewer3d
    # A previous valid PLY is visible before the malformed file is attempted.
    old = QImage(8, 8, QImage.Format_RGB32)
    old.fill(Qt.blue)
    raw = QBuffer()
    assert raw.open(QIODevice.WriteOnly)
    assert old.save(raw, 'PNG')
    assert c.page.show_png(bytes(raw.data()))
    c.page.note.setText('PLY: TC04_BINARY_3pts.ply · 3 điểm')
    c._job_kind = 'ply'
    c._source_path = tmp_path / 'TC05_INVALID.ply'
    c._log = b'SCANTOPATH_PLY_REJECTED:HEADER_TERMINATOR'
    c._process = QProcess(c)
    c._finished(2, QProcess.NormalExit)
    assert 'thiếu end_header' in c.page.state.text()
    assert 'Traceback' not in c.page.state.text()
    assert 'exit=' not in c.page.state.text()
    assert 'TC04' not in c.page.note.text()
    assert c.page._image.isNull()
    assert c.page.preview.pixmap().isNull()
    assert 'Không thể hiển thị PLY' in c.page.preview.text()
    assert '#9f2630' in c.page.state.styleSheet()
    assert not c.render_initialized and not c._disposed


def test_crash_failure_is_short_and_clears_stale_preview(window):
    c = window.viewer3d
    c.page.note.setText('PLY: TC03_ASCII_RGB_4pts.ply')
    c._job_kind = 'ply'
    c._log = b'x' * 2000 + b'\nTraceback: some internal line'
    c._process = QProcess(c)
    c._finished(-1073741819, QProcess.CrashExit)
    assert 'native crash' in c.page.state.text()
    assert 'Traceback' not in c.page.state.text()
    assert 'TC03_ASCII_RGB_4pts' not in c.page.note.text()
    assert len(c.page.state.text()) < 180
    assert not c._disposed
