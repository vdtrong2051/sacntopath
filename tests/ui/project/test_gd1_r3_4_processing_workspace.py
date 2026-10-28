"""R3.4: genuine ProcessingRun DTOs and compact Qt workspace behavior."""
from __future__ import annotations

import os
import time

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
pytest.importorskip("PySide6")

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QApplication, QFrame, QPushButton

from scantopath.application.contracts import SelectionRef, WorkspaceId
from scantopath.application.projects import ProjectWorkspaceService
from scantopath.metadata.store import MetadataStore
from scantopath.ui.shell import ScanToPathMainWindow
from tests.support.project_seed import _seed_numbered


@pytest.fixture(scope="module")
def qapp():
    return QApplication.instance() or QApplication([])


@pytest.fixture
def window(qapp):
    w = ScanToPathMainWindow()
    w.show()
    qapp.processEvents()
    yield w
    w.close()
    deadline = time.monotonic() + 10
    while (w.project_loader.busy or w.project_writer.busy or w.capture_checker.busy) and time.monotonic() < deadline:
        qapp.processEvents()
        time.sleep(0.01)
    qapp.processEvents()


def _wait(qapp, predicate, timeout=10):
    end = time.monotonic() + timeout
    while time.monotonic() < end:
        qapp.processEvents()
        if predicate():
            qapp.processEvents()
            return
        time.sleep(0.01)
    raise AssertionError("R3.4 asynchronous Project load did not finish")


def _load(w, app, root):
    w._begin_project_load(str(root))
    _wait(app, lambda: not w.project_loader.busy)
    assert w.project_explorer.store_root == str(root.resolve())


def test_initial_no_run_no_implicit_sqlite_and_old_action_retained(window, tmp_path):
    panel = window.project_workspace.processing_workspace.panel
    assert panel.objectName() == "processingWorkspace"
    assert panel.table.topLevelItemCount() == 0
    assert "Chưa mở kho" in panel.count_label.text()
    assert window.project_explorer.store_root is None
    assert not (tmp_path / "metadata.sqlite3").exists()
    page = window.page_for(WorkspaceId.PROCESSING)
    legacy = page.findChild(QFrame, "workspacePanel")
    assert legacy is not None and not legacy.isVisible()
    assert page.findChild(QPushButton, "workspacePrimaryAction") is not None
    assert panel.findChild(QFrame, "processingHeaderSeparator").height() == 1
    assert panel.findChild(QFrame, "processingFilterSeparator").height() == 1
    assert panel.findChild(QFrame, "processingDetailSeparator").height() == 1


def test_real_run_selection_sync_and_referenced_outputs(window, qapp, tmp_path):
    _seed_numbered(tmp_path)
    with MetadataStore(tmp_path) as db:
        db.start_processing_run("r-078")
        db.finish_processing_run("r-078", state="succeeded", output_files=["not-created.ply"])
    before = ProjectWorkspaceService(tmp_path).list_events()
    _load(window, qapp, tmp_path)
    window.nav_buttons[WorkspaceId.PROCESSING].click()
    qapp.processEvents()
    panel = window.project_workspace.processing_workspace.panel
    assert panel.isVisible()
    assert panel.table.topLevelItemCount() == 1
    row = panel.table.topLevelItem(0)
    assert row.text(0) == "R0001"
    assert row.text(2) == "Hoàn thành"
    assert "SQLite v2" in panel.count_label.text()
    panel.table.setCurrentItem(row)
    qapp.processEvents()
    ref = SelectionRef("processing_run", "r-078")
    assert window.project_explorer.selection == ref
    assert window.property_inspector.selection == ref
    assert any(panel.details.topLevelItem(i).text(1) == "not-created.ply"
               for i in range(panel.details.topLevelItemCount()))
    assert not (tmp_path / "not-created.ply").exists()
    assert ProjectWorkspaceService(tmp_path).list_events() == before
    assert panel.table.mapTo(window, panel.table.rect().topLeft()).y() < panel.details.mapTo(window, panel.details.rect().topLeft()).y()


def test_filter_project_state_and_clear_on_new_store(window, qapp, tmp_path):
    first = tmp_path / "first"
    cap, _, _ = _seed_numbered(first)
    with MetadataStore(first) as db:
        db.create_processing_run(run_id="r-other", session_id="t-078", stage="compare",
                                 algorithm="fixture", version="1", input_capture_ids=[cap["capture_id"]])
        db.start_processing_run("r-other")
        db.finish_processing_run("r-other", state="failed", error_message="test only")
    _load(window, qapp, first)
    panel = window.project_workspace.processing_workspace.panel
    assert panel.table.topLevelItemCount() == 2
    failed_index = panel.state_filter.findData("failed")
    assert failed_index >= 0
    panel.state_filter.setCurrentIndex(failed_index)
    assert panel.table.topLevelItemCount() == 1
    assert panel.table.topLevelItem(0).text(2) == "Thất bại"
    project_index = panel.project_filter.findData("p-078")
    assert project_index >= 0
    panel.project_filter.setCurrentIndex(project_index)
    assert panel.project_filter.currentData() == "p-078"
    assert panel.table.topLevelItemCount() == 1
    panel.project_filter.setCurrentIndex(0)
    panel.state_filter.setCurrentIndex(0)
    assert panel.table.topLevelItemCount() == 2

    second = tmp_path / "second"
    with MetadataStore(second) as db:
        db.create_project("p2", "Dự án khác")
    _load(window, qapp, second)
    assert panel.table.topLevelItemCount() == 0
    assert panel.details.topLevelItemCount() == 0
    assert "0 lần xử lý" in panel.count_label.text()
    assert "chưa ghi nhận" in panel.empty_label.text()


def test_invalid_store_drops_stale_runs(window, qapp, tmp_path):
    first = tmp_path / "first"
    _seed_numbered(first)
    _load(window, qapp, first)
    panel = window.project_workspace.processing_workspace.panel
    assert panel.table.topLevelItemCount() == 1
    bad = tmp_path / "does-not-exist"
    window._begin_project_load(str(bad))
    _wait(qapp, lambda: not window.project_loader.busy)
    assert window.project_explorer.store_root is None
    assert panel.table.topLevelItemCount() == 0
    assert "Chưa mở kho" in panel.count_label.text()
    assert not bad.exists()
