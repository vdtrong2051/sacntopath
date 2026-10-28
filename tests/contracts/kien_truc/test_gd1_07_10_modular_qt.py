"""07.10 Windows/Qt acceptance for composition, identity, and lazy persistence."""
import os
import time
import pytest

os.environ.setdefault('QT_QPA_PLATFORM','offscreen')
pytest.importorskip('PySide6')
from PySide6.QtWidgets import QApplication
from PySide6.QtCore import QObject
from scantopath.metadata.store import MetadataStore
from scantopath.ui.shell.main_window import ScanToPathMainWindow
from scantopath.modules.project_workspace.presentation.controller import ProjectWorkspaceController


@pytest.fixture
def app():
    return QApplication.instance() or QApplication([])


def _until(app, predicate, seconds=6):
    end=time.monotonic()+seconds
    while time.monotonic()<end:
        app.processEvents()
        if predicate():
            app.processEvents()
            return
        time.sleep(0.01)
    raise AssertionError('Qt worker did not complete')


def test_shell_composes_feature_controller_without_autoload(app,tmp_path,monkeypatch):
    monkeypatch.chdir(tmp_path)
    w=ScanToPathMainWindow()
    try:
        assert isinstance(w.project_workspace,ProjectWorkspaceController)
        assert isinstance(w.project_workspace,QObject)
        assert w.project_workspace.parent() is w
        assert w.project_loader is w.project_workspace.project_loader
        assert w.project_writer is w.project_workspace.project_writer
        assert w.capture_checker is w.project_workspace.capture_checker
        assert w._project_root is None
        assert w.project_explorer.store_root is None
        assert not (tmp_path/'metadata.sqlite3').exists()
    finally:
        w.close()


def test_project_flow_through_composed_controller_in_v1_view_mode(app,tmp_path):
    with MetadataStore(tmp_path) as meta:
        meta.create_project('project-0710','Kiểm thử kiến trúc')
    w=ScanToPathMainWindow()
    try:
        w._begin_project_load(str(tmp_path))
        _until(app,lambda:not w.project_loader.busy)
        assert w._project_root == str(tmp_path.resolve())
        assert w.project_explorer.tree.topLevelItemCount() == 1
        assert not w._can_write_project()
        p=w.project_explorer.tree.topLevelItem(0)
        w.project_explorer.tree.setCurrentItem(p)
        assert w.navigation.selection.entity_id=='project-0710'
        assert w.property_inspector.selection==w.navigation.selection
    finally:
        w.close()
