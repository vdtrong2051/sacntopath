"""GD2-10.08.2 regression: tiny pointer jitter must not discard mouse pick."""
from __future__ import annotations
import pytest
from PySide6.QtCore import Qt, QPointF
from PySide6.QtGui import QPixmap, QColor
from PySide6.QtWidgets import QApplication
from scantopath.modules.viewer3d.presentation.live_view import LiveNavigationPreview

@pytest.fixture
def app():
    return QApplication.instance() or QApplication([])

class Mouse:
    def __init__(self,x,y,button=Qt.LeftButton):
        self.x,self.y,self._button=x,y,button
        self.accepted=False
    def button(self):return self._button
    def position(self):return QPointF(self.x,self.y)
    def accept(self):self.accepted=True

def setup_widget():
    w=LiveNavigationPreview('test')
    w.resize(300,200)
    pic=QPixmap(300,200);pic.fill(QColor('#1c2633'))
    w.setPixmap(pic);w.set_pick_enabled(True);w.interaction_mode='select'
    return w

def tap(w,start,end):
    w.mousePressEvent(Mouse(*start))
    if start!=end:w.mouseMoveEvent(Mouse(*end))
    w.mouseReleaseEvent(Mouse(*end))

def test_A_and_B_can_be_two_clicks_with_three_pixel_pointer_jitter(app):
    widget=setup_widget()
    clicks=[];drags=[]
    widget.point_clicked.connect(lambda u,v:clicks.append((u,v)))
    widget.selection_drag_ignored.connect(lambda:drags.append(True))
    try:
        tap(widget,(100,80),(102,81))
        tap(widget,(180,120),(183,122))
        assert len(clicks)==2, 'Mouse jitter discarded A or B'
        assert not drags
    finally:widget.close()

def test_actual_select_drag_emits_feedback_not_pick(app):
    widget=setup_widget();clicks=[];drags=[]
    widget.point_clicked.connect(lambda u,v:clicks.append((u,v)))
    widget.selection_drag_ignored.connect(lambda:drags.append(True))
    try:
        widget.mousePressEvent(Mouse(100,80))
        widget.mouseMoveEvent(Mouse(102,81))
        widget.mouseMoveEvent(Mouse(104,82))
        widget.mouseMoveEvent(Mouse(110,90))
        widget.mouseReleaseEvent(Mouse(110,90))
        assert clicks == []
        assert len(drags)==1
    finally:widget.close()

def test_orbit_behavior_not_changed(app):
    widget=setup_widget();moves=[];clicks=[]
    widget.interaction_mode='orbit'
    widget.gesture.connect(lambda a,x,y:moves.append(a))
    widget.point_clicked.connect(lambda u,v:clicks.append((u,v)))
    try:
        tap(widget,(100,80),(103,81))
        assert 'orbit' in moves
        assert clicks==[]
    finally:widget.close()

def test_ui_notifies_drag_ignored_in_measure_mode(app,tmp_path):
    from tests.unit.geometry.test_gd2_10_08_2_anchor_visual import prepare
    view, receipt, viewer, panel=prepare(tmp_path, app)
    try:
        viewer.page.preview.selection_drag_ignored.emit()
        assert 'kéo' in panel.readout.text()
        assert panel._session.first is None
        assert panel._session.last is None
    finally:
        panel.dispose();viewer.page.close()
