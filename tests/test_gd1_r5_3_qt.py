"""R5.3 offscreen Qt UI-contract tests; no native VTK in QApplication."""
from __future__ import annotations

import os
from pathlib import Path
from types import SimpleNamespace
from concurrent.futures import Future

os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
import pytest
from PySide6.QtCore import Qt, QPoint
from PySide6.QtGui import QPixmap
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication, QWidget

from scantopath.modules.viewer3d.presentation.interactive_controller import InteractiveViewer3DController
from scantopath.ui.components.property_inspector import PropertyInspector
from scantopath.ui.shell.viewer_inspector_bridge import SceneInspectorBridge
from scantopath.modules.viewer3d.application.scene_contracts import SceneDescriptor


@pytest.fixture
def qapp():
    return QApplication.instance() or QApplication([])


@pytest.fixture
def live(qapp):
    root = QWidget()
    panel = PropertyInspector(root)
    root.resize(1100, 720)
    root.show()
    panel.show()
    controller = InteractiveViewer3DController(root, session_factory=lambda: None)
    bridge = SceneInspectorBridge(panel, controller)
    controller.page.resize(740, 600)
    controller.page.show()
    qapp.processEvents()
    yield controller, panel, bridge
    controller._poll_timer.stop()
    controller.page.close()
    root.close()


def _desc():
    return SceneDescriptor.from_result({
        'name':'part.ply', 'source_sha256':'a'*64, 'source_bytes':200,
        'source_format':'ply','geometry_kind':'mesh','point_count':4,
        'face_count':1,'bounds':[-1,1,-1,1,0,0],
        'has_rgb':False,'units':'unknown','coordinate_frame':'unknown'})


def test_r53_localized_overlay_preserves_legacy_object_names(live):
    c, _, _ = live
    assert c.page.preview.objectName() == 'viewer3dPreview'
    assert c.tools.objectName() == 'viewer3dLiveTools'
    assert c.page.open_ply_button.text() == 'Mở mô hình…'
    for name in ('viewer3dToolSelect', 'viewer3dToolOrbit', 'viewer3dToolPan',
                 'viewer3dToolFit', 'viewer3dToolAxes', 'viewer3dToolLayer'):
        assert c.tools.findChild(QWidget, name) is not None
    assert c.page.findChild(QWidget,'viewer3dOrbitLeft') is not None
    assert not c.page.point_inspector.isVisible()


def test_r53_inspector_shows_source_without_claiming_sqlite_or_metric(live):
    c, panel, bridge = live
    c._descriptor = _desc()
    c._expected_scene_revision = 2
    c._live_phase = 'ready'
    c._emit_scene()
    assert panel.properties_frame.isVisible()
    assert 'part.ply' in panel.title_label.text()
    assert 'SQLite' in panel.note.text()
    assert panel.actions_frame.isHidden()
    c._selected = __import__('scantopath.modules.viewer3d.application.scene_contracts',
                            fromlist=['SceneSelectionRef']).SceneSelectionRef('a'*64, 2, 'face', 0, (0.,0.,0.))
    c._emit_scene()
    pairs = [(panel.details.topLevelItem(i).text(0), panel.details.topLevelItem(i).text(1))
             for i in range(panel.details.topLevelItemCount())]
    assert ('Mã phần tử', '0') in pairs
    assert any('Chưa xác nhận' in value for _,value in pairs)
    c.page.hide()
    QApplication.processEvents()
    assert panel.selection is None
    assert not bridge._owned


def test_r53_live_click_emits_uv_only_in_select_mode(live):
    c, _, _ = live
    pix = QPixmap(360, 240)
    pix.fill(Qt.white)
    c.page.preview.setPixmap(pix)
    c._live_phase = 'ready'
    c._last_frame_revision = 1  # A displayed and validated frame is mandatory for selection.
    c.page.preview.set_pick_enabled(True)
    c._set_tool_mode('select')
    points = []
    c.page.preview.point_clicked.connect(lambda u, v: points.append((u, v)))
    pos = QPoint(c.page.preview.width()//2, c.page.preview.height()//2)
    QTest.mouseClick(c.page.preview, Qt.LeftButton, Qt.NoModifier, pos)
    assert len(points) == 1
    assert 0 <= points[0][0] <= 1 and 0 <= points[0][1] <= 1
    c._set_tool_mode('orbit')
    QTest.mouseClick(c.page.preview, Qt.LeftButton, Qt.NoModifier, pos)
    assert len(points) == 1


def test_r53_invalid_or_stale_pick_cannot_populate_inspector(live):
    c,panel,_ = live
    c._descriptor = _desc()
    c._expected_scene_revision = 5
    c._last_frame_revision = 11
    c._live_phase = 'ready'
    c._emit_scene()
    future = Future()
    future.set_result({'scene_revision':4, 'frame_revision':11,'source_sha256':'a'*64,
                       'geometry_kind':'mesh','hit':True,'kind':'face','element_id':0,
                       'xyz':[0,0,0]})
    c._pick_future = future
    c._poll_selection()
    assert c._selected is None
    assert panel.kind_label.text() == 'MÔ HÌNH 3D'


def test_r53_vector_icons_and_vietnamese_accessibility(live):
    from PySide6.QtCore import QSize
    from PySide6.QtWidgets import QToolButton
    c, _, _ = live
    for name in ('viewer3dToolSelect','viewer3dToolOrbit','viewer3dToolPan',
                 'viewer3dToolFit','viewer3dToolAxes','viewer3dToolGrid',
                 'viewer3dToolLayer','viewer3dToolZoomIn','viewer3dToolZoomOut'):
        button = c.tools.findChild(QToolButton,name)
        assert button is not None
        assert not button.icon().isNull(), name
        assert not button.icon().pixmap(QSize(24,24)).isNull(), name
        assert button.toolTip() and button.accessibleName()
        assert button.text() == ''


def test_r53_selection_disabled_without_a_valid_displayed_frame(live):
    c,_,_=live
    pix=QPixmap(360,240);pix.fill(Qt.white)
    c.page.preview.setPixmap(pix)
    c._live_phase='ready'
    c._last_frame_revision=-1
    c._set_tool_mode('select')
    assert not c.page.preview._pick_enabled
    c._last_frame_revision=1
    c._ready_tools()
    assert c.page.preview._pick_enabled


def test_r53_select_drag_does_not_emit_orbit(live):
    c,_,_=live
    pix=QPixmap(360,240);pix.fill(Qt.white)
    c.page.preview.setPixmap(pix)
    c._live_phase='ready';c._last_frame_revision=1
    c._set_tool_mode('select')
    actions=[]; clicks=[]
    c.page.preview.gesture.connect(lambda *args: actions.append(args))
    c.page.preview.point_clicked.connect(lambda *args: clicks.append(args))
    x=c.page.preview.width()//2;y=c.page.preview.height()//2
    QTest.mousePress(c.page.preview,Qt.LeftButton,Qt.NoModifier,QPoint(x,y))
    QTest.mouseMove(c.page.preview,QPoint(x+60,y+15))
    QTest.mouseRelease(c.page.preview,Qt.LeftButton,Qt.NoModifier,QPoint(x+60,y+15))
    assert actions == [] and clicks == []
    c._set_tool_mode('orbit')
    assert c.page.preview.interaction_mode=='orbit'


def test_r53_xyz_inspector_copy_full_values_and_bounds(live):
    from scantopath.modules.viewer3d.application.scene_contracts import SceneSelectionRef
    from PySide6.QtWidgets import QApplication
    c,panel,bridge=live
    c._descriptor=_desc();c._expected_scene_revision=3
    c._selected=SceneSelectionRef('a'*64,3,'face',0,(0.123456789012345, -4.567890123456, 8.00123456789))
    c._emit_scene()
    pairs={panel.details.topLevelItem(i).text(0):panel.details.topLevelItem(i).text(1)
           for i in range(panel.details.topLevelItemCount())}
    for name in ('X','Y','Z','X nhỏ nhất','X lớn nhất','Y nhỏ nhất',
                 'Y lớn nhất','Z nhỏ nhất','Z lớn nhất'):
        assert name in pairs
    assert pairs['X'].startswith('0.123456789')
    assert bridge.copy_button.isVisible()
    bridge.copy_button.click()
    assert QApplication.clipboard().text() == \
           '0.123456789012345, -4.567890123456, 8.00123456789'
    c._selected=None;c._emit_scene()
    assert bridge.copy_button.isHidden()
