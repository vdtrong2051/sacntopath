"""07.5 Qt acceptance: real temp SQLite, offscreen, no camera or RAW creation."""
from __future__ import annotations

import os
import sqlite3
import time

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
pytest.importorskip("PySide6")

from PySide6.QtCore import QThread
from PySide6.QtWidgets import QApplication, QDialog, QMessageBox

from scantopath.metadata.store import MetadataStore
from scantopath.storage.numbered import NumberedStorageRegistry
from scantopath.ui.projects.edit_dialog import ProjectEditDialog
from scantopath.ui.projects.forms_contract import ProjectEditCommand
from scantopath.ui.shell import ScanToPathMainWindow


@pytest.fixture(scope="module")
def qapp():
    app = QApplication.instance() or QApplication([])
    yield app


def until(qapp, predicate, timeout=6.0):
    end = time.monotonic() + timeout
    while time.monotonic() < end:
        qapp.processEvents()
        if predicate():
            qapp.processEvents()
            return
        time.sleep(.012)
    raise AssertionError("Qt state timeout")


@pytest.fixture
def window(qapp):
    w = ScanToPathMainWindow()
    w.show()
    qapp.processEvents()
    yield w
    w.close()
    until(qapp, lambda: not w.project_loader.busy and not w.project_writer.busy)
    until(qapp, lambda: not w.task_controller.manager.worker_alive)


def seed(root, *, v2=True):
    with MetadataStore(root) as store:
        store.create_project("p", "Dự án 1")
        store.create_specimen("s", "p", "Mẫu 1")
        store.create_scan_session("t", "s", "Quét 1")
    if v2:
        NumberedStorageRegistry.migrate_database(root)
        NumberedStorageRegistry(root).assign_all()


def load(w, qapp, root):
    w._begin_project_load(str(root))
    until(qapp, lambda: not w.project_loader.busy)


def write(w, qapp, command):
    w._submit_project_write(command)
    until(qapp, lambda: not w.project_writer.busy and not w.project_loader.busy)


def test_no_store_no_writing_or_creation(window, tmp_path):
    assert not window.project_explorer.add_button.isEnabled()
    assert not window.property_inspector.edit_button.isEnabled()
    assert not window.property_inspector.close_button.isEnabled()
    assert not (tmp_path / "metadata.sqlite3").exists()


def test_v1_shows_tree_but_write_buttons_disabled(window, qapp, tmp_path):
    seed(tmp_path, v2=False)
    load(window, qapp, tmp_path)
    assert window.project_explorer.tree.topLevelItemCount() == 1
    assert not window.project_explorer.add_button.isEnabled()
    assert not window.property_inspector.edit_button.isEnabled()
    window.project_explorer.tree.setCurrentItem(window.project_explorer.tree.topLevelItem(0))
    assert not window.property_inspector.edit_button.isEnabled()
    assert not window.project_explorer.create_project_action.isEnabled()
    assert not window.project_explorer.create_specimen_action.isEnabled()
    with sqlite3.connect(tmp_path / "metadata.sqlite3") as db:
        assert db.execute("PRAGMA user_version").fetchone()[0] == 1


def test_write_capabilities_follow_selection(window, qapp, tmp_path):
    seed(tmp_path)
    load(window, qapp, tmp_path)
    w = window
    assert w.project_explorer.add_button.isEnabled()
    root = w.project_explorer.tree.topLevelItem(0)
    specimen = root.child(0)
    session = specimen.child(0)
    w.project_explorer.tree.setCurrentItem(root)
    assert w.project_explorer.create_specimen_action.isEnabled()
    assert not w.project_explorer.create_session_action.isEnabled()
    assert w.property_inspector.edit_button.isEnabled()
    w.project_explorer.tree.setCurrentItem(specimen)
    assert w.project_explorer.create_session_action.isEnabled()
    assert not w.project_explorer.create_specimen_action.isEnabled()
    w.project_explorer.tree.setCurrentItem(session)
    assert w.property_inspector.close_button.isEnabled()


def test_create_project_through_dialog_and_refresh(window, qapp, tmp_path, monkeypatch):
    seed(tmp_path)
    load(window, qapp, tmp_path)
    monkeypatch.setattr(ProjectEditDialog, "exec", lambda _: QDialog.Accepted)
    monkeypatch.setattr(ProjectEditDialog, "values", lambda _: ("Dự án mới", "Mô tả mới"))
    window._create_project()
    until(qapp, lambda: not window.project_writer.busy and not window.project_loader.busy)
    assert window.project_explorer.tree.topLevelItemCount() == 2
    with MetadataStore(tmp_path) as db:
        project = next(p for p in db.list_projects() if p["name"] == "Dự án mới")
    assert project["description"] == "Mô tả mới"
    assert window.navigation.selection.entity_id == project["project_id"]
    assert window.property_inspector.selection == window.navigation.selection


def test_add_specimen_and_session_from_selected_parent(window, qapp, tmp_path, monkeypatch):
    seed(tmp_path)
    load(window, qapp, tmp_path)
    monkeypatch.setattr(ProjectEditDialog, "exec", lambda _: QDialog.Accepted)
    monkeypatch.setattr(ProjectEditDialog, "values", lambda _: ("Thêm mới", ""))
    window.project_explorer.tree.setCurrentItem(window.project_explorer.tree.topLevelItem(0))
    window._create_specimen()
    until(qapp, lambda: not window.project_writer.busy and not window.project_loader.busy)
    assert window.navigation.selection.entity_type == "specimen"
    specimen_id = window.navigation.selection.entity_id
    window._create_session()
    until(qapp, lambda: not window.project_writer.busy and not window.project_loader.busy)
    assert window.navigation.selection.entity_type == "scan_session"
    with MetadataStore(tmp_path) as db:
        tree = db.get_project_tree("p")
    spec = next(x for x in tree["specimens"] if x["specimen_id"] == specimen_id)
    assert spec["sessions"][0]["label"] == "Thêm mới"


def test_edit_project_and_session_metadata(window, qapp, tmp_path, monkeypatch):
    seed(tmp_path)
    load(window, qapp, tmp_path)
    monkeypatch.setattr(ProjectEditDialog, "exec", lambda _: QDialog.Accepted)
    monkeypatch.setattr(ProjectEditDialog, "values", lambda _: ("Tên sửa", "Mô tả sửa"))
    root = window.project_explorer.tree.topLevelItem(0)
    window.project_explorer.tree.setCurrentItem(root)
    window._edit_selected_metadata()
    until(qapp, lambda: not window.project_writer.busy and not window.project_loader.busy)
    assert window.project_explorer.tree.topLevelItem(0).text(0).endswith("Tên sửa")
    assert window.navigation.selection.entity_id == "p"
    monkeypatch.setattr(ProjectEditDialog, "values", lambda _: ("Phiên đổi tên", ""))
    window.project_explorer.tree.setCurrentItem(window.project_explorer.tree.topLevelItem(0).child(0).child(0))
    window._edit_selected_metadata()
    until(qapp, lambda: not window.project_writer.busy and not window.project_loader.busy)
    assert window.project_explorer.tree.topLevelItem(0).child(0).child(0).text(0).endswith("Phiên đổi tên")
    assert window.navigation.selection.entity_id == "t"


def test_close_session_confirmation_and_cancel(window, qapp, tmp_path, monkeypatch):
    seed(tmp_path)
    load(window, qapp, tmp_path)
    window.project_explorer.tree.setCurrentItem(window.project_explorer.tree.topLevelItem(0).child(0).child(0))
    monkeypatch.setattr(QMessageBox, "question", lambda *a, **k: QMessageBox.No)
    window._close_selected_session()
    assert window._project_entities[window.project_explorer.selection].state == "open"
    monkeypatch.setattr(QMessageBox, "question", lambda *a, **k: QMessageBox.Yes)
    window._close_selected_session()
    until(qapp, lambda: not window.project_writer.busy and not window.project_loader.busy)
    assert window._project_entities[window.project_explorer.selection].state == "closed"
    assert not window.property_inspector.close_button.isEnabled()


def test_dialog_rejects_blank_name_without_closing(qapp):
    d = ProjectEditDialog(kind="project", create=True)
    d.name_edit.setText("   ")
    d._validate_accept()
    assert d.result() != QDialog.Accepted
    assert "256" in d.error_label.text()
    d.close()


def test_writer_busy_prevents_another_command_or_open(window, qapp, tmp_path, monkeypatch):
    seed(tmp_path)
    load(window, qapp, tmp_path)
    import scantopath.ui.projects.write_controller as ctrl
    original_factory = ctrl._make_write_service
    def slow_service(root):
        time.sleep(.15)
        return original_factory(root)
    monkeypatch.setattr(ctrl, "_make_write_service", slow_service)
    cmd = ProjectEditCommand("project.create", name="Một")
    window._submit_project_write(cmd)
    assert window.project_writer.busy
    assert not window.project_explorer.open_button.isEnabled()
    assert not window.project_explorer.refresh_button.isEnabled()
    assert not window.project_writer.submit(str(tmp_path), ProjectEditCommand("project.create", name="Hai"))
    until(qapp, lambda: not window.project_writer.busy and not window.project_loader.busy)
    with MetadataStore(tmp_path) as db:
        assert [x["name"] for x in db.list_projects()].count("Hai") == 0


def test_worker_write_signals_only_on_main_thread(window, qapp, tmp_path):
    seed(tmp_path)
    load(window, qapp, tmp_path)
    threads = []
    window.project_writer.completed.connect(lambda _: threads.append(QThread.currentThread()))
    write(window, qapp, ProjectEditCommand("project.create", name="New"))
    assert threads and all(t == qapp.thread() for t in threads)


def test_close_while_write_does_not_destroy_running_qthread(window, qapp, tmp_path, monkeypatch):
    seed(tmp_path)
    load(window, qapp, tmp_path)
    import scantopath.ui.projects.write_controller as ctrl
    old = ctrl._make_write_service
    def slow(root):
        time.sleep(.18)
        return old(root)
    monkeypatch.setattr(ctrl, "_make_write_service", slow)
    window._submit_project_write(ProjectEditCommand("project.create", name="Cần lưu"))
    assert window.project_writer.busy
    window.close()
    assert window.isVisible()
    until(qapp, lambda: not window.project_writer.busy)
    until(qapp, lambda: not window.isVisible())
    with MetadataStore(tmp_path) as db:
        assert any(r["name"] == "Cần lưu" for r in db.list_projects())
