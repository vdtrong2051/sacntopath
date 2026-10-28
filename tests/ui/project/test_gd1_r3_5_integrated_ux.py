"""R3.5 integrated acceptance for the already implemented R3.1–R3.4 UI.

All stores are disposable. Tests use genuine SQLite/RAW fixtures and Qt event
processing; they never open hardware or assert physical/metric correctness.
Windows operator HMI acceptance remains a separate mandatory gate.
"""
from __future__ import annotations

import hashlib
import os
import time

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
pytest.importorskip("PySide6")

from PySide6.QtCore import QSettings, Qt
from PySide6.QtWidgets import QApplication, QFrame

from scantopath.application.contracts import SelectionRef, WorkspaceId
from scantopath.application.projects import ProjectWorkspaceService
from scantopath.metadata.store import MetadataStore
from scantopath.modules.project_workspace.presentation.store_management import RecentStorePreferences
from scantopath.ui.shell import ScanToPathMainWindow
from tests.support.project_seed import _seed_numbered, _seed_v1


@pytest.fixture(scope="module")
def qapp():
    return QApplication.instance() or QApplication([])


@pytest.fixture
def window(qapp, tmp_path):
    w = ScanToPathMainWindow()
    recent = w.project_workspace.recent_stores
    recent._prefs = RecentStorePreferences(
        QSettings(str(tmp_path / "ui-preferences.ini"), QSettings.IniFormat)
    )
    recent.panel.display_recent(recent._prefs.paths())
    w.resize(1366, 768)
    w.show()
    qapp.processEvents()
    yield w
    w.close()
    _until(qapp, lambda: not w.project_loader.busy
           and not w.project_writer.busy and not w.capture_checker.busy)
    _until(qapp, lambda: not w.task_controller.manager.worker_alive)
    qapp.processEvents()


def _until(app, predicate, timeout=12.0):
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        app.processEvents()
        if predicate():
            app.processEvents()
            return
        time.sleep(0.012)
    raise AssertionError("R3.5 Qt worker/lifecycle timed out")


def _load(w, app, root):
    w._begin_project_load(str(root))
    _until(app, lambda: not w.project_loader.busy)
    assert w.project_explorer.store_root == str(root.resolve())


def _fields(inspector):
    return {
        inspector.details.topLevelItem(i).text(0):
        inspector.details.topLevelItem(i).text(1)
        for i in range(inspector.details.topLevelItemCount())
    }


def test_r35_launch_is_explicit_empty_without_phantom_data(window, qapp, tmp_path):
    recent = window.project_workspace.recent_stores.panel
    dashboard = window.project_workspace.project_dashboard.panel
    processing = window.project_workspace.processing_workspace.panel
    assert window.project_explorer.store_root is None
    assert recent.isVisible() and not dashboard.isVisible()
    assert processing.table.topLevelItemCount() == 0
    assert "Chưa mở kho" in processing.count_label.text()
    assert window.property_inspector.selection is None
    assert not window.property_inspector.actions_frame.isVisible()
    assert not window.project_loader.busy
    assert len(window.nav_buttons) == 4
    assert not (tmp_path / "metadata.sqlite3").exists()
    assert recent.findChild(QFrame, "recentStoreTopSeparator").height() == 1
    assert recent.findChild(QFrame, "recentStoreListSeparator").height() == 1


def test_r35_real_capture_to_processing_selection_and_read_only_provenance(
    window, qapp, tmp_path,
):
    root = tmp_path / "v2"
    capture, _, _ = _seed_numbered(root)
    with MetadataStore(root) as db:
        db.start_processing_run("r-078")
        db.finish_processing_run(
            "r-078", state="succeeded", output_files=["unverified-output.ply"]
        )
    db_hash = hashlib.sha256((root / "metadata.sqlite3").read_bytes()).hexdigest()
    raw_files = tuple(sorted(p for p in (root / "sessions").rglob("*") if p.is_file()))
    assert raw_files, "Synthetic RAW fixture unexpectedly empty"
    raw_hashes = tuple(hashlib.sha256(p.read_bytes()).hexdigest() for p in raw_files)
    events_before = ProjectWorkspaceService(root).list_events()
    _load(window, qapp, root)

    dashboard = window.project_workspace.project_dashboard.panel
    assert dashboard.isVisible()
    assert not window.project_workspace.recent_stores.panel.isVisible()
    dashboard.project_combo.setCurrentIndex(1)
    qapp.processEvents()
    assert window.project_explorer.selection == SelectionRef("project", "p-078")
    assert "Bản thu: 1" in dashboard.stats_label.text()
    assert "Lần xử lý: 1" in dashboard.stats_label.text()
    assert dashboard.findChild(QFrame, "dashboardHeaderSeparator").height() == 1
    assert dashboard.findChild(QFrame, "dashboardContextSeparator").height() == 1

    cap_row = dashboard.tables["capture"].topLevelItem(0)
    assert cap_row.data(0, Qt.UserRole) == SelectionRef("capture", capture["capture_id"])
    dashboard.tables["capture"].setCurrentItem(cap_row)
    qapp.processEvents()
    assert window.project_explorer.selection == SelectionRef("capture", capture["capture_id"])
    assert window.property_inspector.selection == window.project_explorer.selection
    assert "Chưa kiểm tra RAW" in _fields(window.property_inspector)["RAW"]
    assert window.property_inspector.verify_button.isEnabled()

    window.nav_buttons[WorkspaceId.PROCESSING].click()
    qapp.processEvents()
    assert window.project_explorer.store_root == str(root.resolve())
    processing = window.project_workspace.processing_workspace.panel
    assert processing.isVisible()
    assert processing.table.topLevelItemCount() == 1
    assert "SQLite v2" in processing.count_label.text()
    processing.table.setCurrentItem(processing.table.topLevelItem(0))
    qapp.processEvents()
    run_ref = SelectionRef("processing_run", "r-078")
    assert window.project_explorer.selection == run_ref
    assert window.property_inspector.selection == run_ref
    assert "Đầu ra (tham chiếu)" in _fields(window.property_inspector)
    assert any(
        "unverified-output.ply" in processing.details.topLevelItem(i).text(1)
        for i in range(processing.details.topLevelItemCount())
    )
    assert not (root / "unverified-output.ply").exists()
    assert not window.property_inspector.actions_frame.isVisible()
    assert all(
        processing.findChild(QFrame, name).height() == 1
        for name in ("processingHeaderSeparator", "processingFilterSeparator",
                     "processingDetailSeparator")
    )
    assert ProjectWorkspaceService(root).list_events() == events_before
    assert hashlib.sha256((root / "metadata.sqlite3").read_bytes()).hexdigest() == db_hash
    assert tuple(hashlib.sha256(p.read_bytes()).hexdigest() for p in raw_files) == raw_hashes


def test_r35_changing_to_missing_store_clears_all_presentations(window, qapp, tmp_path):
    source = tmp_path / "source"
    _seed_numbered(source)
    _load(window, qapp, source)
    window.nav_buttons[WorkspaceId.PROCESSING].click()
    qapp.processEvents()
    processing = window.project_workspace.processing_workspace.panel
    assert processing.table.topLevelItemCount() == 1
    processing.table.setCurrentItem(processing.table.topLevelItem(0))
    qapp.processEvents()
    assert window.property_inspector.selection is not None

    missing = tmp_path / "missing-store"
    window._begin_project_load(str(missing))
    _until(qapp, lambda: not window.project_loader.busy)
    assert window.project_explorer.store_root is None
    assert window.project_explorer.selection is None
    assert window.property_inspector.selection is None
    assert window.property_inspector.details.topLevelItemCount() == 0
    assert processing.table.topLevelItemCount() == 0
    assert processing.details.topLevelItemCount() == 0
    assert "Chưa mở kho" in processing.count_label.text()
    assert not window.project_workspace.project_dashboard.panel.isVisible()
    assert not missing.exists()
    assert str(missing) not in window.project_workspace.recent_stores._prefs.paths()


def test_r35_v1_remains_read_only_across_project_and_processing(window, qapp, tmp_path):
    root = tmp_path / "legacy-v1"
    _seed_v1(root, with_capture=False)
    before = (root / "metadata.sqlite3").read_bytes()
    _load(window, qapp, root)
    dash = window.project_workspace.project_dashboard.panel
    assert dash.isVisible()
    assert "SQLite v1" in dash.store_label.text()
    assert not dash.create_project_button.isEnabled()
    dash.project_combo.setCurrentIndex(1)
    qapp.processEvents()
    assert not dash.create_specimen_button.isEnabled()
    assert not window.property_inspector.edit_button.isEnabled()

    window.nav_buttons[WorkspaceId.PROCESSING].click()
    qapp.processEvents()
    panel = window.project_workspace.processing_workspace.panel
    assert panel.table.topLevelItemCount() == 0
    assert "SQLite v1" in panel.count_label.text()
    assert "chưa ghi nhận" in panel.empty_label.text()
    assert (root / "metadata.sqlite3").read_bytes() == before
    assert not (root / "01_PROJECTS").exists()


def test_r35_recent_store_reopen_retains_project_and_processing_truth(window, qapp, tmp_path):
    root = tmp_path / "remembered"
    _seed_numbered(root, with_capture=False, with_run=False)
    _load(window, qapp, root)
    dashboard = window.project_workspace.project_dashboard.panel
    dashboard.change_button.click()
    qapp.processEvents()
    recent = window.project_workspace.recent_stores.panel
    assert recent.isVisible() and not dashboard.isVisible()
    assert recent.recent_list.count() == 1
    recent.recent_list.setCurrentRow(0)
    recent.open_button.click()
    _until(qapp, lambda: not window.project_loader.busy)
    assert dashboard.isVisible() and not recent.isVisible()
    assert window.project_explorer.store_root == str(root.resolve())
    assert dashboard.project_combo.count() == 2
    processing = window.project_workspace.processing_workspace.panel
    assert processing.table.topLevelItemCount() == 0
    assert "0 lần xử lý" in processing.count_label.text()
