"""UXH-01.5: Qt selection cannot be resurrected by obsolete native futures."""
from __future__ import annotations

from concurrent.futures import Future
from types import SimpleNamespace
import os
import pytest

os.environ.setdefault('QT_QPA_PLATFORM','offscreen')
pytest.importorskip('PySide6')
from PySide6.QtWidgets import QApplication, QWidget
from scantopath.modules.viewer3d.application.scene_contracts import SceneDescriptor
from scantopath.modules.viewer3d.presentation.interactive_controller import InteractiveViewer3DController


@pytest.fixture
def viewer():
    app=QApplication.instance() or QApplication([])
    root=QWidget()
    controller=InteractiveViewer3DController(root,session_factory=lambda: None)
    controller._poll_timer.stop()
    controller._descriptor=SceneDescriptor.from_result({
        'name':'fixture.ply','source_sha256':'a'*64,'source_bytes':150,
        'source_format':'ply','geometry_kind':'mesh',
        'point_count':4,'face_count':2,'bounds':[-1,1,-1,1,-1,1],
        'has_rgb':False,'units':'unknown','coordinate_frame':'unknown',
    })
    controller._expected_scene_revision=3
    controller._last_frame_revision=8
    controller._live_phase='ready'
    yield controller
    controller.page.close()
    root.close()
    app.processEvents()


def _payload(**changes):
    base=dict(scene_revision=3,frame_revision=8,source_sha256='a'*64,
              geometry_kind='mesh',units='unknown',coordinate_frame='unknown',
              hit=True,kind='face',element_id=1,xyz=[0.,0.,0.])
    base.update(changes)
    return base


def _future(data):
    f=Future();f.set_result(data);return f


def test_good_pick_populates_selection(viewer):
    emitted=[];viewer.point_pick_completed.connect(emitted.append)
    viewer._pick_future=_future(_payload())
    viewer._poll_selection()
    assert viewer._selected.kind=='face'
    assert emitted[-1]==viewer._selected


def test_stale_reply_does_not_overwrite_new_selection(viewer):
    good=_future(_payload())
    viewer._pick_future=good;viewer._poll_selection()
    old=viewer._selected
    viewer._pick_future=_future(_payload(frame_revision=7))
    viewer._poll_selection()
    assert viewer._selected is old


def test_malformed_reply_cannot_populate_inspector(viewer):
    emitted=[];viewer.point_pick_completed.connect(emitted.append)
    viewer._pick_future=_future(_payload(xyz=[True,1,1]))
    viewer._poll_selection()
    assert viewer._selected is None
    assert emitted==[None]


def test_switching_tool_drops_inflight_pick(viewer):
    pending=Future()
    viewer._pick_future=pending
    viewer._set_tool_mode('orbit')
    assert viewer._pick_future is None
    pending.set_result(_payload())
    viewer._poll_selection()
    assert viewer._selected is None


def test_clear_selection_drops_inflight_pick(viewer):
    viewer._pick_future=Future()
    viewer._clear_selection()
    assert viewer._pick_future is None
    assert viewer._selected is None
