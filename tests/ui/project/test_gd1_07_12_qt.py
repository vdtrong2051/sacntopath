"""Qt ownership and controller workflow integration. Must execute on Windows CI."""
import os
import pytest
os.environ.setdefault('QT_QPA_PLATFORM','offscreen')
pytest.importorskip('PySide6')
from PySide6.QtWidgets import QApplication
from PySide6.QtCore import QObject
from scantopath.ui.shell.main_window import ScanToPathMainWindow
from scantopath.modules.project_workspace.presentation.workflows import (
    _ProjectReadCoordinator,_ProjectWriteCoordinator,_CaptureReviewCoordinator)

@pytest.fixture
def app():
    return QApplication.instance() or QApplication([])

def test_0712_qt_collaborators_share_only_the_feature_qobject(app):
    window=ScanToPathMainWindow()
    try:
        feature=window.project_workspace
        assert isinstance(feature,QObject)
        assert feature.parent() is window
        assert isinstance(feature._reads,_ProjectReadCoordinator)
        assert isinstance(feature._writes,_ProjectWriteCoordinator)
        assert isinstance(feature._captures,_CaptureReviewCoordinator)
        assert feature.project_loader.parent() is feature
        assert feature.project_writer.parent() is feature
        assert feature.capture_checker.parent() is feature
        assert feature._reads._owner is feature
        assert feature._writes._owner is feature
        assert feature._captures._owner is feature
    finally:
        window.close()

def test_0712_qt_shell_retains_controller_legacy_delegates(app):
    window=ScanToPathMainWindow()
    try:
        assert window.project_loader is window.project_workspace.project_loader
        assert window.project_writer is window.project_workspace.project_writer
        assert window.capture_checker is window.project_workspace.capture_checker
        assert window._project_root is None
        assert not window._can_write_project()
        window._update_project_actions()
    finally:
        window.close()
