"""09.09.1 Qt shell smoke: explicit default-store bootstrap and gated capture."""
from __future__ import annotations
import os
import pytest
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
pytest.importorskip("PySide6")
from PySide6.QtWidgets import QApplication, QPushButton
from scantopath.ui.shell.main_window import ScanToPathMainWindow


def test_capture_gated_without_project_and_store_init_explicit():
    app = QApplication.instance() or QApplication([])
    window = ScanToPathMainWindow()
    try:
        button = window.findChild(QPushButton, "captureLiveCommitButton")
        init_button = window.project_workspace.recent_stores.panel.init_button
        assert button is not None
        assert not button.isEnabled()
        assert init_button.objectName() == "recentStoreInitializeDefault"
        assert not window.project_workspace.store_initializer.busy
        assert window.project_workspace._project_root is None
        assert not window.capture_action.capture()
    finally:
        window.close()
        for _ in range(5):
            app.processEvents()
