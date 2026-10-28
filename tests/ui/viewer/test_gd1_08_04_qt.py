"""08.04 Qt behavior in offscreen; no GPU render claims from this suite."""
from __future__ import annotations
import os
import pytest
os.environ.setdefault('QT_QPA_PLATFORM','offscreen')
pytest.importorskip('PySide6')
from PySide6.QtCore import QBuffer,QIODevice,Qt,QProcess
from PySide6.QtGui import QImage
from PySide6.QtWidgets import QApplication,QPushButton
from scantopath.application.contracts import WorkspaceId
from scantopath.modules.viewer3d.application.navigation import CameraView
from scantopath.ui.shell import ScanToPathMainWindow


@pytest.fixture
def view():
    app=QApplication.instance() or QApplication([])
    window=ScanToPathMainWindow()
    window.nav_buttons[WorkspaceId.INSPECT3D].click()
    app.processEvents()
    yield window,window.viewer3d
    window.close();app.processEvents()


def _png():
    image=QImage(20,20,QImage.Format_RGB32);image.fill(Qt.blue)
    io=QBuffer();assert io.open(QIODevice.WriteOnly)
    assert image.save(io,'PNG')
    return bytes(io.data())


def test_08_04_controls_exist_but_disabled_before_real_image(view):
    window,c=view
    assert c._process is None
    assert not c.render_initialized
    assert len(c.page.navigation_buttons)==7
    assert not c.page.axes_button.isEnabled()
    for name in ('viewer3dOrbitLeft','viewer3dOrbitRight','viewer3dZoomIn',
                 'viewer3dZoomOut','viewer3dReset','viewer3dAxes'):
        assert c.page.findChild(QPushButton,name) is not None


def test_08_04_gui_navigation_does_not_import_native_vtk(view):
    w,c=view
    assert not c.navigate('orbit',20,10)  # Cannot navigate unloaded view
    assert c._process is None


def test_08_04_model_commits_only_on_success(view,tmp_path):
    w,c=view
    c._started=True
    assert c.page.show_png(_png())
    c._pending_view=CameraView().update('orbit',20,15).update('axes')
    c._job_kind='navigation';c._display_kind='fixture'
    c._image_path=tmp_path/'preview.png';c._image_path.write_bytes(_png())
    c._process=QProcess(c)
    c._log=b'SCANTOPATH_NAV_PREVIEW_OK'
    c._finished(0,QProcess.NormalExit)
    assert c.render_initialized
    assert c._view_state.azimuth==20 and c._view_state.elevation==15
    assert c._view_state.axes and c.page.axes_button.isChecked()
    assert c._pending_view is None
    assert w.active_workspace is WorkspaceId.INSPECT3D


def test_08_04_nav_failure_keeps_previous_camera_and_desktop(view):
    w,c=view
    c._started=True
    c.page.show_png(_png())
    c._pending_view=CameraView().update('zoom',4)
    c._job_kind='navigation';c._log=b'native failure'
    c._process=QProcess(c)
    c._finished(-1073741819,QProcess.CrashExit)
    assert c._view_state==CameraView()
    assert c._started and not c._disposed
    assert 'KHÔNG cập nhật' in c.page.state.text()
    assert not c.page._image.isNull()
    w.nav_buttons[WorkspaceId.PROJECTS].click()
    assert w.active_workspace is WorkspaceId.PROJECTS
