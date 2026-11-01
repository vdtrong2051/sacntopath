"""01.7-C Qt viewport tests with no camera initialization."""
from __future__ import annotations
import os
os.environ.setdefault('QT_QPA_PLATFORM','offscreen')
import pytest
pytest.importorskip('PySide6')
from PySide6.QtWidgets import QApplication, QWidget, QHBoxLayout, QLabel
from scantopath.application.contracts import WorkspaceId
from scantopath.modules.capture.presentation.workspace_layout import ResponsiveCaptureWorkflowBar
from scantopath.ui.shell import ScanToPathMainWindow


@pytest.fixture(scope='module')
def qapp():
    return QApplication.instance() or QApplication([])


def test_workflow_instruction_compacts_but_tooltip_stays_full(qapp):
    bar = ResponsiveCaptureWorkflowBar()
    row = QHBoxLayout(bar)
    title = QLabel('THU NHẬN RGB-D',bar)
    hint = QLabel(ResponsiveCaptureWorkflowBar.FULL_HINT,bar)
    row.addWidget(title)
    row.addWidget(hint)
    bar.attach_hint(hint)
    try:
        bar.resize(430, 70)
        bar.show()
        qapp.processEvents()
        assert hint.text() == bar.COMPACT_HINT
        assert hint.toolTip() == bar.FULL_HINT
        bar.resize(760,70)
        qapp.processEvents()
        assert hint.text() == bar.FULL_HINT
    finally:
        bar.close()


def test_capture_resizes_without_destroying_tabs_or_autostart(qapp):
    win = ScanToPathMainWindow()
    try:
        win.resize(1366, 768)
        win.show()
        win._navigate(WorkspaceId.CAPTURE)
        qapp.processEvents()
        layout = win.capture_workspace_layout
        assert layout.tabs.count() == 2
        assert layout.tabs.usesScrollButtons()
        assert layout.tabs.widget(0) is win.capture_live.panel
        assert layout.tabs.widget(1) is win.capture_preview.panel
        assert win.capture_live.state.value == 'idle'
        for width,height in [(940,620),(1280,720),(1366,768),(1920,1080)]:
            win.resize(width,height)
            qapp.processEvents()
            assert layout.tabs.count() == 2
            assert layout.tabs.widget(0) is win.capture_live.panel
            assert layout.tabs.widget(1) is win.capture_preview.panel
        layout.tabs.setCurrentIndex(1)
        qapp.processEvents()
        assert layout.tabs.currentWidget() is win.capture_preview.panel
        layout.tabs.setCurrentIndex(0)
        assert layout.tabs.currentWidget() is win.capture_live.panel
        assert win.capture_live.state.value == 'idle'
    finally:
        win.close()
        qapp.processEvents()
