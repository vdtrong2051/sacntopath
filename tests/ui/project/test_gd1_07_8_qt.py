"""07.8 Qt offscreen integrated acceptance — run on Windows with PySide6.

Uses real temporary SQLite, synthetic RAW and QThread controllers. The UI
must never create or migrate a storage root on launch.
"""
from __future__ import annotations

import os
from pathlib import Path
import time

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
pytest.importorskip("PySide6")
from PySide6.QtWidgets import QApplication

from scantopath.application.projects import ProjectWorkspaceService
from scantopath.storage.legacy_migration import LegacyRawMigrator
from scantopath.ui.projects.forms_contract import ProjectEditCommand
from scantopath.ui.shell import ScanToPathMainWindow
from tests.support.project_seed import _seed_numbered, _seed_v1


@pytest.fixture(scope="module")
def qapp():
    return QApplication.instance() or QApplication([])


def _until(app, predicate, timeout=10):
    until = time.monotonic() + timeout
    while time.monotonic() < until:
        app.processEvents()
        if predicate():
            app.processEvents()
            return
        time.sleep(.012)
    raise AssertionError("Timed out waiting for Qt project/capture worker")


@pytest.fixture
def window(qapp):
    widget = ScanToPathMainWindow()
    widget.show()
    qapp.processEvents()
    yield widget
    widget.close()
    _until(qapp, lambda: not widget.project_loader.busy
           and not widget.project_writer.busy and not widget.capture_checker.busy)
    _until(qapp, lambda: not widget.task_controller.manager.worker_alive)


def _load(w, app, root: Path):
    w._begin_project_load(str(root))
    _until(app, lambda: not w.project_loader.busy)
    assert w.project_explorer.store_root == str(root.resolve())


def _write(w, app, command):
    w._submit_project_write(command)
    _until(app, lambda: not w.project_writer.busy and not w.project_loader.busy)


def test_gui_starts_empty_and_does_not_implicitly_open_sqlite(window, tmp_path):
    assert window.project_explorer.store_root is None
    assert window.project_explorer.tree.topLevelItemCount() == 0
    assert not window.project_explorer.add_button.isEnabled()
    assert not window.property_inspector.verify_button.isEnabled()
    assert not (tmp_path / "metadata.sqlite3").exists()


def test_gui_numbered_capture_processing_run_audit_and_inspection(window, qapp, tmp_path):
    cap, _, _ = _seed_numbered(tmp_path)
    events_before = ProjectWorkspaceService(tmp_path).list_events()
    _load(window, qapp, tmp_path)
    tree = window.project_explorer.tree
    assert tree.topLevelItemCount() == 1
    project_item = tree.topLevelItem(0)
    assert project_item.text(0).startswith("P0001")
    session_item = project_item.child(0).child(0)
    assert session_item.childCount() == 2
    captures = [session_item.child(i) for i in range(session_item.childCount())
                if session_item.child(i).data(0, 0x0100).entity_type == "capture"]
    runs = [session_item.child(i) for i in range(session_item.childCount())
            if session_item.child(i).data(0, 0x0100).entity_type == "processing_run"]
    assert len(captures) == len(runs) == 1
    assert captures[0].text(0).startswith("C0001")
    assert runs[0].text(0).startswith("R0001")
    assert window.task_event_panel.audit_table.topLevelItemCount() >= len(events_before)
    tree.setCurrentItem(runs[0])
    assert window.property_inspector.selection.entity_type == "processing_run"
    assert not window.property_inspector.verify_button.isEnabled()
    tree.setCurrentItem(captures[0])
    assert window.property_inspector.selection.entity_id == cap["capture_id"]
    assert window.property_inspector.verify_button.isEnabled()
    window.property_inspector.verify_button.click()
    _until(qapp, lambda: not window.capture_checker.busy)
    assert "RAW v1" in window.property_inspector.note.text()
    assert ProjectWorkspaceService(tmp_path).list_events() == events_before


def test_gui_v1_is_readonly_and_cannot_allocate_codes(window, qapp, tmp_path):
    _seed_v1(tmp_path, with_capture=False)
    _load(window, qapp, tmp_path)
    assert "v1" in window.project_explorer.store_label.text()
    assert window.project_explorer.tree.topLevelItemCount() == 1
    window.project_explorer.tree.setCurrentItem(window.project_explorer.tree.topLevelItem(0))
    assert not window.project_explorer.add_button.isEnabled()
    assert not window.property_inspector.edit_button.isEnabled()
    assert not window.project_explorer.create_project_action.isEnabled()
    assert not (tmp_path / "01_PROJECTS").exists()


def test_gui_writer_persists_to_new_reader_and_keeps_selection(window, qapp, tmp_path):
    _seed_numbered(tmp_path, with_capture=False)
    _load(window, qapp, tmp_path)
    _write(window, qapp, ProjectEditCommand("project.create", name="Dự án nghiệm thu"))
    selection = window.navigation.selection
    assert selection is not None and selection.entity_type == "project"
    assert window.property_inspector.selection == selection
    _write(window, qapp, ProjectEditCommand("project.update", name="Dự án nghiệm thu V2",
                                           target_id=selection.entity_id))
    assert window.navigation.selection == selection
    stored = ProjectWorkspaceService(tmp_path).get_project_tree(selection.entity_id)
    assert stored.project.name == "Dự án nghiệm thu V2"
    assert stored.project.storage.public_code == "P0002"
    assert not (tmp_path / "01_PROJECTS").exists()


def test_gui_refresh_after_external_migration_and_rollback(window, qapp, tmp_path):
    cap, _, _ = _seed_numbered(tmp_path, with_run=False)
    _load(window, qapp, tmp_path)
    mig = LegacyRawMigrator(tmp_path)
    applied = mig.apply()
    window._reload_project_store()
    _until(qapp, lambda: not window.project_loader.busy)
    capture = window.project_explorer.tree.topLevelItem(0).child(0).child(0).child(0)
    window.project_explorer.tree.setCurrentItem(capture)
    window.property_inspector.verify_button.click()
    _until(qapp, lambda: not window.capture_checker.busy)
    assert "RAW v1" in window.property_inspector.note.text()
    mig.rollback(applied["migration_id"])
    window._reload_project_store()
    _until(qapp, lambda: not window.project_loader.busy)
    capture = window.project_explorer.tree.topLevelItem(0).child(0).child(0).child(0)
    window.project_explorer.tree.setCurrentItem(capture)
    assert capture.data(0, 0x0100).entity_id == cap["capture_id"]
    window.property_inspector.verify_button.click()
    _until(qapp, lambda: not window.capture_checker.busy)
    assert "RAW v1" in window.property_inspector.note.text()
