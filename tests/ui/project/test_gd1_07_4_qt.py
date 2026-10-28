"""07.4: Qt offscreen acceptance of explicit SQLite store loading.

Executed on operator Windows with PySide6; no camera, real RAW or schema writes.
"""
from __future__ import annotations

import os
from pathlib import Path
import sqlite3
import time

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
pytest.importorskip("PySide6")

from PySide6.QtWidgets import QApplication, QFileDialog
from PySide6.QtCore import QThread

from scantopath.metadata.store import MetadataStore
from scantopath.storage.numbered import NumberedStorageRegistry
from scantopath.ui.shell import ScanToPathMainWindow


@pytest.fixture(scope="module")
def qapp():
    app = QApplication.instance() or QApplication([])
    yield app


@pytest.fixture
def window(qapp):
    window = ScanToPathMainWindow()
    window.show()
    qapp.processEvents()
    yield window
    window.close()
    _wait(qapp, lambda: not window.project_loader.busy)
    _wait(qapp, lambda: not window.task_controller.manager.worker_alive)


def _wait(app, predicate, timeout: float = 5.0):
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        app.processEvents()
        if predicate():
            app.processEvents()
            return
        time.sleep(0.009)
    raise AssertionError("Timed out waiting for Qt state")


def _seed(root: Path, *, numbered: bool = False):
    with MetadataStore(root) as store:
        store.create_project("project-internal-id", "Dự án thật")
        store.create_specimen("specimen-internal-id", "project-internal-id", "Chi tiết A")
        store.create_scan_session("session-internal-id", "specimen-internal-id", "Quét một")
    if numbered:
        NumberedStorageRegistry.migrate_database(root)
        NumberedStorageRegistry(root).assign_all()


def _load(window, qapp, root: Path):
    window._begin_project_load(str(root))
    _wait(qapp, lambda: not window.project_loader.busy)


def test_initial_window_does_not_create_sqlite(window, tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    assert window.project_explorer.store_root is None
    assert window.project_explorer.tree.topLevelItemCount() == 0
    assert window.project_explorer.open_button.isEnabled()
    assert not window.project_explorer.refresh_button.isEnabled()
    assert not (tmp_path / "metadata.sqlite3").exists()


def test_open_dialog_requires_explicit_choice(window, qapp, tmp_path, monkeypatch):
    _seed(tmp_path)
    import scantopath.ui.shell.main_window as main_window_mod
    monkeypatch.setattr(main_window_mod, "QFileDialog", type("Dialog", (), {"getExistingDirectory": staticmethod(lambda *a, **kw: str(tmp_path))}))
    window.project_explorer.open_button.click()
    _wait(qapp, lambda: not window.project_loader.busy)
    assert window.project_explorer.store_root == str(tmp_path.resolve())
    assert window.project_explorer.tree.topLevelItemCount() == 1
    assert window.project_explorer.refresh_button.isEnabled()


def test_dialog_cancel_has_no_io(window, tmp_path, monkeypatch):
    import scantopath.ui.shell.main_window as main_window_mod
    monkeypatch.setattr(main_window_mod, "QFileDialog", type("Dialog", (), {"getExistingDirectory": staticmethod(lambda *a, **kw: "")}))
    window.project_explorer.open_button.click()
    assert window.project_explorer.store_root is None
    assert not (tmp_path / "metadata.sqlite3").exists()


def test_v1_tree_selection_and_inspector(window, qapp, tmp_path):
    _seed(tmp_path)
    _load(window, qapp, tmp_path)
    root = window.project_explorer.tree.topLevelItem(0)
    assert root.text(0) == "Chưa cấp mã · Dự án thật"
    assert root.child(0).text(0) == "Chưa cấp mã · Chi tiết A"
    assert root.child(0).child(0).text(0) == "Chưa cấp mã · Quét một"
    window.project_explorer.tree.setCurrentItem(root.child(0))
    assert window.navigation.selection.entity_id == "specimen-internal-id"
    assert window.property_inspector.selection == window.navigation.selection
    assert any(window.property_inspector.details.topLevelItem(i).text(1) == "Chi tiết A"
               for i in range(window.property_inspector.details.topLevelItemCount()))
    with sqlite3.connect(tmp_path / "metadata.sqlite3") as db:
        assert db.execute("PRAGMA user_version").fetchone()[0] == 1


def test_numbered_tree_does_not_reassign_codes(window, qapp, tmp_path):
    _seed(tmp_path, numbered=True)
    with sqlite3.connect(tmp_path / "metadata.sqlite3") as db:
        start_codes = db.execute("SELECT COUNT(*) FROM storage_projects").fetchone()[0]
    _load(window, qapp, tmp_path)
    item = window.project_explorer.tree.topLevelItem(0)
    assert item.text(0) == "P0001 · Dự án thật"
    assert item.child(0).text(0) == "S0001 · Chi tiết A"
    assert item.child(0).child(0).text(0) == "T0001 · Quét một"
    item.child(0).setExpanded(True)
    window.project_explorer.tree.setCurrentItem(item)
    assert any(window.property_inspector.details.topLevelItem(i).text(1) == "P0001"
               for i in range(window.property_inspector.details.topLevelItemCount()))
    with sqlite3.connect(tmp_path / "metadata.sqlite3") as db:
        assert db.execute("SELECT COUNT(*) FROM storage_projects").fetchone()[0] == start_codes
    assert not (tmp_path / "01_PROJECTS").exists()


def test_empty_sqlite_store_gives_real_empty_state(window, qapp, tmp_path):
    with MetadataStore(tmp_path):
        pass
    _load(window, qapp, tmp_path)
    assert window.project_explorer.tree.topLevelItemCount() == 0
    assert "chưa có dự án" in window.project_explorer.empty_label.text().lower()
    assert window.project_explorer.store_root is not None
    assert "0 dự án" in window.data_status.text()


def test_invalid_folder_does_not_create_database(window, qapp, tmp_path):
    _load(window, qapp, tmp_path)
    assert window.project_explorer.store_root is None
    assert "Không tìm thấy kho" in window.project_explorer.empty_label.text()
    assert not (tmp_path / "metadata.sqlite3").exists()


def test_unknown_schema_reported_without_modification(window, qapp, tmp_path):
    _seed(tmp_path)
    with sqlite3.connect(tmp_path / "metadata.sqlite3") as db:
        db.execute("PRAGMA user_version=99")
    _load(window, qapp, tmp_path)
    assert "không được hỗ trợ" in window.project_explorer.empty_label.text()
    with sqlite3.connect(tmp_path / "metadata.sqlite3") as db:
        assert db.execute("PRAGMA user_version").fetchone()[0] == 99


def test_refresh_finds_new_records_and_drops_old_selection(window, qapp, tmp_path):
    _seed(tmp_path)
    _load(window, qapp, tmp_path)
    item = window.project_explorer.tree.topLevelItem(0)
    window.project_explorer.tree.setCurrentItem(item)
    with MetadataStore(tmp_path) as store:
        store.create_project("project-new-id", "Dự án mới")
    window.project_explorer.refresh_button.click()
    _wait(qapp, lambda: not window.project_loader.busy)
    assert window.project_explorer.tree.topLevelItemCount() == 2
    assert window.navigation.selection is None
    assert window.property_inspector.selection is None


def test_reselecting_different_store_replaces_tree(window, qapp, tmp_path):
    original = tmp_path / "one"
    alternative = tmp_path / "two"
    _seed(original)
    with MetadataStore(alternative) as store:
        store.create_project("other", "Kho khác")
    _load(window, qapp, original)
    _load(window, qapp, alternative)
    assert window.project_explorer.tree.topLevelItemCount() == 1
    assert window.project_explorer.tree.topLevelItem(0).text(0).endswith("Kho khác")


def test_project_load_ui_signals_are_on_main_thread(window, qapp, tmp_path):
    _seed(tmp_path)
    threads = []
    window.project_loader.loaded.connect(lambda _: threads.append(QThread.currentThread()))
    _load(window, qapp, tmp_path)
    assert threads and all(t == qapp.thread() for t in threads)


def test_window_close_waits_for_project_loader(window, qapp, tmp_path, monkeypatch):
    _seed(tmp_path)
    # Simulate slow I/O without actually locking a database.
    import scantopath.ui.projects.controller as ctrl
    original_factory = ctrl._make_project_service

    class SlowService:
        def __init__(self, root):
            time.sleep(0.15)
            self.inner = original_factory(root)
            self.info = self.inner.info
        def list_projects(self):
            return self.inner.list_projects()
        def get_project_tree(self, pid):
            return self.inner.get_project_tree(pid)

    monkeypatch.setattr(ctrl, "_make_project_service", SlowService)
    window._begin_project_load(str(tmp_path))
    assert window.project_loader.busy
    window.close()
    assert window.isVisible()  # rejected while the QThread is alive
    _wait(qapp, lambda: not window.project_loader.busy)
    _wait(qapp, lambda: not window.isVisible())
