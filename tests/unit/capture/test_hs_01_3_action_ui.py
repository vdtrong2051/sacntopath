"""HS-01.3 Qt action integration, mocked store/camera; no RAW or SQLite writes."""
from __future__ import annotations

import os
from types import SimpleNamespace

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
pytest.importorskip("PySide6")
from PySide6.QtCore import QObject, Signal
from PySide6.QtWidgets import QApplication, QWidget, QPushButton, QLabel

from scantopath.application.contracts import SelectionRef
from scantopath.modules.capture.application.contracts import CaptureContext
from scantopath.modules.capture.domain.models import CameraState
from scantopath.modules.capture.presentation.capture_action import CaptureActionCoordinator


CTX = CaptureContext("C:/isolated", "project", "specimen", "session")


class Busy(QObject):
    busy_changed = Signal(bool)
    def __init__(self):
        super().__init__()
        self.busy = False


class Explorer(QObject):
    selection_changed = Signal(object)
    def __init__(self):
        super().__init__()
        self.selection = SelectionRef("scan_session", "session")


class Camera(QObject):
    keyframe_ready = Signal(object)
    keyframe_failed = Signal(str)
    state_changed = Signal(object)
    def __init__(self):
        super().__init__()
        self.state = CameraState.STREAMING


class View(QWidget):
    def __init__(self):
        super().__init__()
        self.project_explorer = Explorer()
        self.project_loader = Busy()
        self.project_writer = Busy()
        self._reloaded = 0
        self.project_workspace = SimpleNamespace(
            _project_root=CTX.store_root, _project_schema=2,
            _project_entities={self.project_explorer.selection: SimpleNamespace(state="open")},
            _project_owners={
                self.project_explorer.selection: CTX.specimen_id,
                SelectionRef("specimen", CTX.specimen_id): CTX.project_id,
            },
            project_loader=self.project_loader, project_writer=self.project_writer,
            _pending_selection=None, _reload_project_store=self.reload,
        )
        self.capture_live = SimpleNamespace(
            panel=SimpleNamespace(
                capture_button=QPushButton("manual"),
                auto_capture_button=QPushButton("auto"),
                capture_context_label=QLabel("ctx"),
            ),
            camera=Camera(),
        )
        self.task_event_panel = SimpleNamespace(add_ui_event=lambda s: None)
    def _set_status(self, text):
        pass
    def reload(self):
        self._reloaded += 1


@pytest.fixture
def mock_action():
    app = QApplication.instance() or QApplication([])
    view = View()
    action = CaptureActionCoordinator(view, store_factory=lambda: None)
    yield view, action
    view.close()
    app.processEvents()


def test_verified_auto_receipt_keeps_original_scan_session(mock_action):
    view, action = mock_action
    action._context = CTX
    action._phase = "commit"
    action._preserve_session_selection = True
    action._auto_frame_floor = (20, 20)
    observed = []
    action.finished.connect(observed.append)
    action._on_storage_success("capture_A")
    assert observed == ["capture_A"]
    assert view.project_workspace._pending_selection == SelectionRef("scan_session", "session")
    assert view._reloaded == 1
    assert action._context is None and action._phase == "idle"
    assert action._auto_frame_floor is None
    assert action._preserve_session_selection is False


def test_manual_receipt_still_focuses_capture(mock_action):
    view, action = mock_action
    action._context = CTX
    action._phase = "commit"
    action._on_storage_success("capture_B")
    assert view.project_workspace._pending_selection == SelectionRef("capture", "capture_B")


def test_failed_auto_resets_capture_flags(mock_action):
    view, action = mock_action
    action._context = CTX
    action._phase = "preflight"
    action._preserve_session_selection = True
    action._auto_frame_floor = (40, 40)
    action._fail("STORE_NOT_OPEN")
    assert action._auto_frame_floor is None
    assert action._preserve_session_selection is False
    assert action._context is None
