"""08.05 Qt selection contract. Offscreen tests never start native VTK child."""
from __future__ import annotations
import json
import os
from pathlib import Path
import pytest
os.environ.setdefault('QT_QPA_PLATFORM','offscreen')
pytest.importorskip('PySide6')
from PySide6.QtCore import QBuffer,QIODevice,Qt,QProcess
from PySide6.QtGui import QImage
from PySide6.QtWidgets import QApplication,QPushButton,QLabel
from scantopath.application.contracts import WorkspaceId
from scantopath.modules.viewer3d.application.picking import PickResult
from scantopath.ui.shell import ScanToPathMainWindow

@pytest.fixture
def view():
    app=QApplication.instance() or QApplication([])
    w=ScanToPathMainWindow()
    w.nav_buttons[WorkspaceId.INSPECT3D].click();app.processEvents()
    yield w,w.viewer3d
    w.close();app.processEvents()


def png():
    img=QImage(100,62,QImage.Format_RGB32);img.fill(Qt.blue)
    stream=QBuffer();assert stream.open(QIODevice.WriteOnly)
    assert img.save(stream,'PNG')
    return bytes(stream.data())


def test_point_inspector_is_feature_owned_not_project_inspector(view):
    window,c=view
    assert c.page.findChild(QPushButton,'viewer3dCloudLayer') is not None
    assert c.page.findChild(QLabel,'viewer3dPointTitle') is not None
    assert c.page.findChild(QLabel,'viewer3dPointInfo') is not None
    assert not c.pick_point(.5,.5)  # no loaded renderer
    assert c._process is None
    assert window.project_explorer.store_root is None


def test_picking_success_updates_only_local_inspector(view,tmp_path):
    window,c=view
    assert c.page.show_png(png())
    c._started=True
    picked={'hit':True,'point_id':2,'xyz':[0,.25,0], 'rgb':None,
        'display_uv':[.35,.74], 'source_id':'fixture:08.02',
        'units':'unknown','coordinate_frame':'unknown'}
    output=tmp_path/'pick.json';output.write_text(json.dumps(picked))
    c._job_kind='picking';c._pick_path=output;c._pending_pick=(.35,.74)
    c._process=QProcess(c);c._log=b'SCANTOPATH_POINT_PICK_OK'
    c._finished(0,QProcess.NormalExit)
    assert c._selected_point is not None and c._selected_point.point_id==2
    assert 'Point ID 2' in c.page.point_title.text()
    assert 'Y = 0.25' in c.page.point_info.text()
    assert window.property_inspector.selection is None
    assert c._process is None


def test_no_hit_clears_point_without_deleting_render(view,tmp_path):
    _,c=view
    c.page.show_png(png());c._started=True
    c._selected_point=PickResult(True,0,(0.,0.,0.),None,(.5,.5),'fixture:08.02')
    miss={'hit':False,'point_id':None,'xyz':None,'rgb':None,'display_uv':None,
        'source_id':'fixture:08.02','units':'unknown','coordinate_frame':'unknown'}
    output=tmp_path/'miss.json';output.write_text(json.dumps(miss))
    c._job_kind='picking';c._pick_path=output;c._process=QProcess(c)
    c._log=b'SCANTOPATH_POINT_PICK_OK';c._finished(0,QProcess.NormalExit)
    assert c._selected_point is None and 'Không tìm thấy điểm' in c.page.point_title.text()
    assert not c.page._image.isNull() and c._started


def test_native_failure_does_not_crash_or_keep_stale_selection(view):
    w,c=view
    c.page.show_png(png());c._started=True
    c._selected_point=PickResult(True,0,(0.,0.,0.),None,(.5,.5),'fixture:08.02')
    c._job_kind='picking';c._process=QProcess(c);c._log=b'native crash'
    c._finished(-1073741819,QProcess.CrashExit)
    assert c._selected_point is None and c._process is None
    assert c._started and not c._disposed and not c.page._image.isNull()
    assert 'Ứng dụng vẫn hoạt động' in c.page.state.text()
    w.nav_buttons[WorkspaceId.PROJECTS].click()
    assert w.active_workspace is WorkspaceId.PROJECTS


def test_layer_visibility_and_new_ply_clear_selection(view):
    _,c=view
    assert c.page.show_png(png());c._started=True
    c.page.show_point(PickResult(True,0,(0.,0.,0.),None,(.5,.5),'fixture:08.02'))
    c._selected_point=PickResult(True,0,(0.,0.,0.),None,(.5,.5),'fixture:08.02')
    c.page.layer_button.click()
    assert not c.page.layer_button.isChecked() and c._selected_point is None
    assert not c.page.preview._pick_enabled
    c.page.layer_button.click()
    assert c.page.layer_button.isChecked() and not c.page._image.isNull()
    assert c.page.preview.pixmap() is not None and not c.page.preview.pixmap().isNull()


def test_navigation_preview_emits_pick_only_for_click_not_drag(view):
    from PySide6.QtCore import QPoint
    from PySide6.QtTest import QTest
    w,c=view
    w.show()
    QApplication.instance().processEvents()
    assert c.page.show_png(png())
    c.page.preview.set_pick_enabled(True)
    pix=c.page.preview.pixmap()
    assert pix is not None and not pix.isNull()
    x=(c.page.preview.width()-pix.width())//2 + pix.width()//2
    y=(c.page.preview.height()-pix.height())//2 + pix.height()//2
    emitted=[]
    c.page.preview.point_clicked.connect(lambda u,v: emitted.append((u,v)))
    QTest.mouseClick(c.page.preview,Qt.LeftButton,Qt.NoModifier,QPoint(x,y))
    QApplication.instance().processEvents()
    assert len(emitted)==1
    assert emitted[0][0]==pytest.approx(.5,abs=.015)
    assert emitted[0][1]==pytest.approx(.5,abs=.015)
    QTest.mousePress(c.page.preview,Qt.LeftButton,Qt.NoModifier,QPoint(x,y))
    QTest.mouseRelease(c.page.preview,Qt.LeftButton,Qt.NoModifier,QPoint(x+25,y))
    QApplication.instance().processEvents()
    assert len(emitted)==1  # left drag belongs to 08.04 orbit
