"""HS-01.3 Qt adapter tests with mocked live/store: no camera, no DB writes."""
from __future__ import annotations

import os
from types import SimpleNamespace

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
pytest.importorskip("PySide6")
from PySide6.QtCore import QObject, Signal
from PySide6.QtWidgets import QApplication, QWidget, QPushButton, QLabel

from scantopath.modules.capture.application.contracts import CaptureContext
from scantopath.modules.capture.domain.models import CameraState
from scantopath.modules.capture.presentation.auto_capture_controller import AutoCaptureController
from tests.unit.capture.test_hs_01_2_frame_quality import frame, roi


CTX = CaptureContext("C:/isolated", "pr", "sp", "ss")


class Camera(QObject):
    state_changed = Signal(object)
    def __init__(self):
        super().__init__()
        self.state = CameraState.STREAMING


class Live(QObject):
    analysis_ready = Signal(object, object)
    def __init__(self):
        super().__init__()
        self.camera = Camera()
        button = QPushButton("auto")
        button.setCheckable(True)  # Mirrors LiveCapturePanel production widget.
        self.panel = SimpleNamespace(
            auto_capture_button=button,
            auto_capture_status=QLabel("status"),
            manual_roi=None,
        )


class Store(QObject):
    busy_changed = Signal(bool)
    def __init__(self):
        super().__init__()
        self.busy = False


class Explorer(QObject):
    selection_changed = Signal(object)
    def __init__(self):
        super().__init__()
        self.selected = CTX


class Action(QObject):
    finished = Signal(str)
    failed = Signal(str)
    phase_changed = Signal(str, str)
    def __init__(self, explorer):
        super().__init__()
        self.explorer = explorer
        self.busy = False
        self.requests = []
    def _selected_context(self):
        return self.explorer.selected
    def _refresh(self):
        pass  # Existing CaptureActionCoordinator exposes this method.
    def capture_auto(self, ctx, *, color_frame_index, depth_frame_index):
        if self.busy:
            return False
        self.busy = True
        self.requests.append((ctx, color_frame_index, depth_frame_index))
        return True
    def succeed(self, cid="id_1"):
        self.finished.emit(cid)
        self.busy = False
    def fail(self, reason="RAW_WRITE_FAILED"):
        self.failed.emit(reason)
        self.busy = False


class View(QWidget):
    def __init__(self):
        super().__init__()
        self.capture_live = Live()
        self.project_loader = Store()
        self.project_writer = Store()
        self.project_explorer = Explorer()
        self.capture_action = Action(self.project_explorer)
        events = []
        self.task_event_panel = SimpleNamespace(add_ui_event=events.append)
        self.events = events


@pytest.fixture
def harness():
    app = QApplication.instance() or QApplication([])
    view = View()
    controller = AutoCaptureController(view)
    yield view, controller
    view.close()
    view.capture_live.panel.auto_capture_button.deleteLater()
    view.capture_live.panel.auto_capture_status.deleteLater()
    app.processEvents()


def push(view, idx, value=1000, valid=True):
    f = frame(idx, depth_value=value)
    view.capture_live.panel.manual_roi = roi(f) if valid else None
    view.capture_live.analysis_ready.emit(f, None)


def test_qt_proposal_is_not_saved_until_commit(harness):
    view, controller = harness
    btn = view.capture_live.panel.auto_capture_button
    assert btn.isEnabled()
    btn.setChecked(True)
    push(view, 1)
    push(view, 2)
    assert len(view.capture_action.requests) == 1
    assert controller.session.snapshot().saved == 0
    push(view, 3)
    assert len(view.capture_action.requests) == 1
    view.capture_action.succeed("raw_a")
    assert controller.session.snapshot().saved == 1
    push(view, 15)
    assert len(view.capture_action.requests) == 1  # duplicate view


def test_qt_context_switch_stops_capture_before_new_request(harness):
    view, controller = harness
    view.capture_live.panel.auto_capture_button.setChecked(True)
    push(view, 1)
    view.project_explorer.selected = CaptureContext("C:/isolated", "pr", "sp", "other")
    view.project_explorer.selection_changed.emit(None)
    push(view, 2)
    assert not view.capture_live.panel.auto_capture_button.isChecked()
    assert view.capture_action.requests == []


def test_qt_stop_during_commit_then_receipt(harness):
    view, controller = harness
    btn = view.capture_live.panel.auto_capture_button
    btn.setChecked(True)
    push(view, 1)
    push(view, 2)
    btn.setChecked(False)
    assert controller.session.snapshot().state.value == "STOPPING"
    view.capture_action.succeed("raw_stopped")
    assert controller.session.snapshot().state.value == "STOPPED"
    assert controller.session.snapshot().saved == 1
    push(view, 3)
    assert len(view.capture_action.requests) == 1


def test_qt_commit_failure_no_false_saved(harness):
    view, controller = harness
    view.capture_live.panel.auto_capture_button.setChecked(True)
    push(view, 1)
    push(view, 2)
    view.capture_action.fail("CAPTURE_TIMEOUT")
    assert controller.session.snapshot().saved == 0
    assert controller.session.snapshot().failures == 1
    push(view, 3)
    assert len(view.capture_action.requests) == 2
