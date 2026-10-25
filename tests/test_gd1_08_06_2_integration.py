"""08.06.2 cross-feature Qt integration; synthetic outcomes never claim native GPU.

Run with QT_QPA_PLATFORM=offscreen; real OpenGL/HMI is a separate 08.06.4 gate.
"""
from __future__ import annotations
import json
import os
from pathlib import Path
import sys
import tempfile

import pytest
os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
pytest.importorskip('PySide6')
from PySide6.QtCore import QBuffer, QIODevice, QProcess
from PySide6.QtGui import QImage
from PySide6.QtWidgets import QApplication

from scantopath.application.contracts import WorkspaceId
from scantopath.ui.shell import ScanToPathMainWindow


@pytest.fixture
def ui():
    app = QApplication.instance() or QApplication([])
    window = ScanToPathMainWindow()
    app.processEvents()
    yield window, app
    window.close()
    app.processEvents()


def _preview_png() -> bytes:
    image = QImage(32, 32, QImage.Format_RGB32)
    image.fill(0xff2277dd)
    io = QBuffer()
    assert io.open(QIODevice.WriteOnly)
    assert image.save(io, 'PNG')
    data = bytes(io.data())
    io.close()
    return data


def test_08062_workspace_switch_preserves_project_and_single_viewer(ui):
    w, app = ui
    project_page = w.page_for(WorkspaceId.PROJECTS)
    project_root = w.project_explorer.store_root
    assert w.viewer3d is None
    for _ in range(10):
        w.nav_buttons[WorkspaceId.INSPECT3D].click()
        app.processEvents()
        controller = w.viewer3d
        assert controller is not None
        assert w.page_for(WorkspaceId.INSPECT3D) is controller.page
        assert controller._process is None  # offscreen never launches native VTK
        w.nav_buttons[WorkspaceId.PROJECTS].click()
        app.processEvents()
        assert w.active_workspace is WorkspaceId.PROJECTS
        assert w.page_for(WorkspaceId.PROJECTS) is project_page
        assert w.project_explorer.store_root == project_root
    assert w.viewer3d is controller


def test_08062_ply_success_then_rejection_never_leaks_old_data_to_ui(ui, tmp_path):
    w, app = ui
    w.nav_buttons[WorkspaceId.INSPECT3D].click()
    app.processEvents()
    c = w.viewer3d
    old_project_root = w.project_explorer.store_root
    source = tmp_path / 'four_points.ply'
    source.write_text('ply\nformat ascii 1.0\nelement vertex 1\n'
                      'property float x\nproperty float y\nproperty float z\n'
                      'end_header\n0 0 0\n', encoding='ascii')
    image_path = tmp_path / 'preview.png'
    image_path.write_bytes(_preview_png())
    meta = tmp_path / 'metadata.json'
    meta.write_text(json.dumps({
        'name': source.name, 'source_sha256': 'a' * 64,
        'source_bytes': source.stat().st_size, 'point_count': 1,
        'bounds': [0, 0, 0, 0, 0, 0], 'has_rgb': False,
        'ply_format': 'ascii', 'units': 'unknown',
        'coordinate_frame': 'unknown'}), encoding='utf-8')
    c._job_kind = 'ply'
    c._source_path = source
    c._image_path = image_path
    c._metadata_path = meta
    c._log = b'SCANTOPATH_PLY_PREVIEW_OK'
    c._process = QProcess(c)
    c._finished(0, QProcess.NormalExit)
    assert c.render_initialized
    assert '1 điểm' in c.page.note.text()
    assert not c.page._image.isNull()
    assert c._process is None
    # An invalid second PLY must not leave the previous cloud/metadata visible.
    c._job_kind = 'ply'
    c._process = QProcess(c)
    c._log = b'SCANTOPATH_PLY_REJECTED:HEADER_TERMINATOR'
    c._finished(2, QProcess.NormalExit)
    assert not c.render_initialized
    assert c.page._image.isNull()
    assert source.name not in c.page.note.text()
    assert 'Traceback' not in c.page.state.text()
    assert 'thiếu end_header' in c.page.state.text()
    assert w.project_explorer.store_root == old_project_root
    assert w.property_inspector.selection is None
    w.nav_buttons[WorkspaceId.PROJECTS].click()
    app.processEvents()
    assert w.active_workspace is WorkspaceId.PROJECTS


def test_08062_shutdown_cancels_pending_render_and_cleans_temp(ui):
    w, app = ui
    w.nav_buttons[WorkspaceId.INSPECT3D].click()
    app.processEvents()
    c = w.viewer3d
    tmp = tempfile.TemporaryDirectory(prefix='scantopath-08062-')
    folder = Path(tmp.name)
    c._temp = tmp
    c._render_pending = True
    assert folder.exists()
    assert w.close()
    app.processEvents()
    assert c._disposed
    assert c._process is None
    assert c._temp is None
    assert not folder.exists()
    c._start_preview()  # delayed QTimer must be inert after closing
    assert c._process is None


def test_08062_shutdown_kills_active_isolated_child(ui):
    """Exercise QProcess kill on a harmless sleeping Python, never native VTK."""
    w, app = ui
    w.nav_buttons[WorkspaceId.INSPECT3D].click()
    app.processEvents()
    c = w.viewer3d
    p = QProcess(c)
    p.start(sys.executable, ['-c', 'import time; time.sleep(30)'])
    assert p.waitForStarted(5000), p.errorString()
    c._process = p
    assert w.close()
    # Inspect QProcess before event-loop deleteLater invalidates its PySide wrapper.
    assert p.waitForFinished(1500) or p.state() == QProcess.NotRunning
    assert c._disposed and c._process is None
    app.processEvents()
