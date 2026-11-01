"""HS-01.4: Qt signal integration and fail-closed guard; no physical camera/DB."""
import os
from types import SimpleNamespace

import pytest
os.environ.setdefault('QT_QPA_PLATFORM','offscreen')
pytest.importorskip('PySide6')

from scantopath.modules.capture.domain.models import DepthRoi, RoiSource
from tests.unit.capture.test_hs_01_3_qt_adapter import harness, push
from tests.unit.capture.test_hs_01_2_frame_quality import frame


def start(view):
    button=view.capture_live.panel.auto_capture_button
    assert button.isEnabled()
    button.setChecked(True)
    assert button.isChecked()


def test_wide_auto_bbox_never_triggers_camera(harness):
    view, ctl=harness
    start(view)
    f=frame(1,size=(800,1280))
    invalid=DepthRoi(201,582,1079,214,1280,800,RoiSource.DEPTH_SUGGESTION)
    view.capture_live.analysis_ready.emit(f,SimpleNamespace(roi=invalid,usable=True))
    assert view.capture_action.requests==[]
    assert ctl.session.snapshot().last_reason=='ROI_TOO_WIDE'
    assert 'BLOCKED' in view.capture_live.panel.roi_safety_status.text()
    assert '84%' in view.capture_live.panel.roi_safety_status.text()


def test_close_camera_does_not_capture_and_recovers_after_adjustment(harness):
    view, ctl=harness
    start(view)
    push(view,1,value=150)
    assert ctl.session.snapshot().last_reason=='DEPTH_TOO_NEAR'
    assert view.capture_action.requests==[]
    push(view,2,value=1000)  # warm-up after invalid data
    push(view,3,value=1000)
    assert len(view.capture_action.requests)==1
    assert 'READY_PROXY' in view.capture_live.panel.roi_safety_status.text()
    assert ctl.session.snapshot().failures==0


def test_no_roi_waits_with_reason_and_no_false_capture(harness):
    view, ctl=harness
    start(view)
    view.capture_live.panel.manual_roi=None
    view.capture_live.analysis_ready.emit(frame(1),None)
    snap=ctl.session.snapshot()
    assert snap.last_reason=='ROI_REQUIRED' and snap.proposals==0
    assert not view.capture_action.requests


def test_operator_stop_remains_distinct_from_camera_stop(harness):
    view, ctl=harness
    start(view)
    view.capture_live.panel.auto_capture_button.setChecked(False)
    assert ctl.session.snapshot().state.value=='STOPPED'
    assert view.capture_live.camera.state.value=='streaming'
    assert not view.capture_action.requests
