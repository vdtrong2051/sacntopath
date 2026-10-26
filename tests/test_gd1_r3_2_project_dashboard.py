"""R3.2: real Qt geometry, validated DTOs and existing Project write contracts."""
from __future__ import annotations

import os
import time

import pytest

os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
pytest.importorskip('PySide6')

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QApplication, QFrame, QDialog, QPushButton

from scantopath.application.contracts import SelectionRef, WorkspaceId
from scantopath.metadata.store import MetadataStore
from scantopath.storage.numbered import NumberedStorageRegistry
from scantopath.ui.shell import ScanToPathMainWindow


@pytest.fixture(scope='module')
def qapp():
    return QApplication.instance() or QApplication([])


@pytest.fixture
def window(qapp):
    w = ScanToPathMainWindow()
    w.show()
    qapp.processEvents()
    yield w
    w.close()
    qapp.processEvents()


def _wait(qapp, predicate, timeout=8.0):
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        qapp.processEvents()
        if predicate():
            qapp.processEvents()
            return
        time.sleep(0.01)
    raise AssertionError('R3.2 Qt worker did not finish')


def _seed(root):
    with MetadataStore(root) as store:
        store.create_project('p1', 'Dự án mẫu')
        store.create_specimen('s1', 'p1', 'Vật mẫu thật')
        store.create_scan_session('t1', 's1', 'Phiên thật')
    NumberedStorageRegistry.migrate_database(root)
    NumberedStorageRegistry(root).assign_all()


def _load(window, qapp, root):
    window._begin_project_load(str(root))
    _wait(qapp, lambda: not window.project_loader.busy)


def test_launch_does_not_open_database_or_create_fake_rows(window, tmp_path):
    dash = window.project_workspace.project_dashboard.panel
    assert not dash.isVisible()
    assert window.project_workspace.recent_stores.panel.isVisible()
    assert dash.tables['specimen'].topLevelItemCount() == 0
    assert not dash.create_project_button.isEnabled()
    assert window.project_explorer.store_root is None
    assert not (tmp_path / 'metadata.sqlite3').exists()


def test_real_project_data_replaces_store_card_and_preserves_borders(window, qapp, tmp_path):
    root = tmp_path / 'repo'
    _seed(root)
    _load(window, qapp, root)
    dash = window.project_workspace.project_dashboard.panel
    assert dash.isVisible()
    assert not window.project_workspace.recent_stores.panel.isVisible()
    assert dash.findChild(QFrame, 'dashboardHeaderSeparator') is not None
    assert dash.findChild(QFrame, 'dashboardContextSeparator') is not None
    assert 'SQLite v2' in dash.store_label.text()
    assert dash.project_combo.count() == 2
    # Explicit selection flows through the Explorer; it is not a shadow selection.
    dash.project_combo.setCurrentIndex(1)
    qapp.processEvents()
    assert window.project_explorer.selection == SelectionRef('project', 'p1')
    assert 'Vật mẫu: 1' in dash.stats_label.text()
    assert dash.tables['specimen'].topLevelItemCount() == 1
    assert dash.tables['scan_session'].topLevelItemCount() == 1
    assert dash.tables['capture'].topLevelItemCount() == 0
    assert dash.tables['processing_run'].topLevelItemCount() == 0
    assert dash.create_project_button.isEnabled()
    assert dash.create_specimen_button.isEnabled()
    assert not dash.create_session_button.isEnabled()
    row = dash.tables['specimen'].topLevelItem(0)
    dash.tables['specimen'].setCurrentItem(row)
    qapp.processEvents()
    assert window.project_explorer.selection == SelectionRef('specimen', 's1')
    assert window.property_inspector.selection == window.project_explorer.selection
    assert not dash.create_specimen_button.isEnabled()
    assert dash.create_session_button.isEnabled()
    assert window.workspace_stack.currentWidget() == window.page_for(WorkspaceId.PROJECTS)
    assert dash.geometry().height() > 0


def test_central_create_delegates_to_real_writer(window, qapp, tmp_path, monkeypatch):
    root = tmp_path / 'numbered'
    with MetadataStore(root):
        pass
    NumberedStorageRegistry.migrate_database(root)
    _load(window, qapp, root)
    dash = window.project_workspace.project_dashboard.panel
    assert dash.create_project_button.isEnabled()
    import scantopath.modules.project_workspace.presentation.workflows.writing as writing
    class ApprovedProjectDialog:
        def __init__(self, *, kind, create, name, description, parent):
            assert kind == 'project' and create
        def exec(self):
            return QDialog.Accepted
        def values(self):
            return ('Dự án R3.2', 'Dữ liệu từ người dùng')
    monkeypatch.setattr(writing, 'ProjectEditDialog', ApprovedProjectDialog)
    dash.create_project_button.click()
    _wait(qapp, lambda: not window.project_writer.busy and not window.project_loader.busy
          and window.project_explorer.tree.topLevelItemCount() == 1)
    assert dash.project_combo.count() == 2
    assert window.project_explorer.tree.topLevelItem(0).text(0).startswith('P0001')
    with MetadataStore(root) as store:
        assert len(store.list_projects()) == 1


def test_switch_store_exposes_r31_recent_choices_without_new_sqlite(window, qapp, tmp_path):
    root = tmp_path / 'store'
    _seed(root)
    _load(window, qapp, root)
    dash = window.project_workspace.project_dashboard.panel
    dash.change_button.click()
    qapp.processEvents()
    assert not dash.isVisible()
    assert window.project_workspace.recent_stores.panel.isVisible()
    assert window.project_explorer.store_root is not None
    assert not (tmp_path / 'metadata.sqlite3').exists()


def test_v1_keeps_project_overview_read_only(window, qapp, tmp_path):
    with MetadataStore(tmp_path) as store:
        store.create_project('legacy', 'Dữ liệu cũ')
    _load(window, qapp, tmp_path)
    dash = window.project_workspace.project_dashboard.panel
    assert dash.isVisible()
    assert dash.project_combo.count() == 2
    assert not dash.create_project_button.isEnabled()
    dash.project_combo.setCurrentIndex(1)
    assert not dash.create_specimen_button.isEnabled()
    assert not dash.create_session_button.isEnabled()
