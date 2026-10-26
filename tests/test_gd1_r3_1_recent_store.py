"""R3.1 — persistent *shortcuts* and explicit existing-store selection, actual Qt."""
from __future__ import annotations

import os
import time
from pathlib import Path

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
pytest.importorskip("PySide6")
from PySide6.QtCore import QSettings
from PySide6.QtWidgets import QApplication, QFrame
from scantopath.metadata.store import MetadataStore
from scantopath.modules.project_workspace.presentation.store_management import RecentStorePreferences
from scantopath.ui.shell import ScanToPathMainWindow


@pytest.fixture(scope="module")
def app():
    yield QApplication.instance() or QApplication([])


@pytest.fixture
def window(app, tmp_path):
    w = ScanToPathMainWindow()
    recent = w.project_workspace.recent_stores
    settings = QSettings(str(tmp_path / "prefs.ini"), QSettings.IniFormat)
    recent._prefs = RecentStorePreferences(settings)
    recent.panel.display_recent(recent._prefs.paths())
    w.show()
    app.processEvents()
    yield w
    w.close()
    app.processEvents()


def _wait(app, predicate, timeout=6.0):
    end = time.monotonic() + timeout
    while time.monotonic() < end:
        app.processEvents()
        if predicate():
            app.processEvents()
            return
        time.sleep(0.01)
    raise AssertionError("Qt loader did not reach expected state")


def test_preferences_dedupe_cap_and_roundtrip(tmp_path):
    settings = QSettings(str(tmp_path / "config.ini"), QSettings.IniFormat)
    prefs = RecentStorePreferences(settings)
    paths = [str(tmp_path / f"store{i}") for i in range(10)]
    for p in paths:
        prefs.remember(p)
    prefs.remember(paths[4])
    assert len(prefs.paths()) == 8
    assert prefs.paths()[0] == str(tmp_path / "store4")
    restored = RecentStorePreferences(QSettings(str(tmp_path / "config.ini"), QSettings.IniFormat))
    assert restored.paths() == prefs.paths()
    restored.forget(paths[4])
    assert paths[4] not in restored.paths()


def test_no_auto_sqlite_or_auto_bookmark_on_launch(window, app, tmp_path):
    panel = window.project_workspace.recent_stores.panel
    assert window.project_explorer.store_root is None
    assert not window.project_loader.busy
    assert panel.objectName() == "recentStorePanel"
    assert panel.isVisible()
    assert not (tmp_path / "metadata.sqlite3").exists()
    assert window.project_workspace.recent_stores._prefs.paths() == ()
    # An actual outline and a physically separated header are part of R3.1 UX.
    assert panel.findChild(QFrame, "recentStoreTopSeparator") is not None
    assert panel.findChild(QFrame, "recentStoreListSeparator") is not None
    legacy = window.page_for(__import__("scantopath.application.contracts", fromlist=["WorkspaceId"]).WorkspaceId.PROJECTS).findChild(QFrame, "workspacePanel")
    assert legacy is not None and not legacy.isVisible()


def test_open_valid_store_updates_recent_and_reopens_explicitly(window, app, tmp_path):
    root = tmp_path / "project-data"
    with MetadataStore(root) as db:
        db.create_project("pr1", "Thử nghiệm")
    panel = window.project_workspace.recent_stores.panel
    assert panel.recent_list.count() == 0
    window._begin_project_load(str(root))
    _wait(app, lambda: not window.project_loader.busy)
    assert window.project_explorer.store_root == str(root.resolve())
    assert panel.recent_list.count() == 1
    assert panel.recent_list.item(0).data(256) == str(root.resolve())
    assert "SQLite v1" in panel.state_label.text()
    # Bookmarks are inert until user explicitly selects/reopens them.
    window.project_workspace.recent_stores.panel.recent_list.setCurrentRow(0)
    panel.open_button.click()
    _wait(app, lambda: not window.project_loader.busy)
    assert window.project_explorer.tree.topLevelItemCount() == 1
    assert panel.recent_list.count() == 1


def test_missing_root_kept_visible_and_no_autocreate(window, app, tmp_path):
    removed = tmp_path / "deleted-store"
    recent = window.project_workspace.recent_stores
    recent._prefs.remember(str(removed))
    recent.panel.display_recent(recent._prefs.paths())
    assert recent.panel.recent_list.count() == 1
    assert "Không còn" in recent.panel.recent_list.item(0).text()
    recent.panel.recent_list.setCurrentRow(0)
    recent.panel.forget_button.click()
    assert recent._prefs.paths() == ()
    assert not removed.exists()


def test_invalid_store_not_bookmarked(window, app, tmp_path):
    bad = tmp_path / "not-a-store"
    window._begin_project_load(str(bad))
    _wait(app, lambda: not window.project_loader.busy)
    assert not bad.exists()
    assert window.project_workspace.recent_stores._prefs.paths() == ()
    assert window.project_explorer.store_root is None
    assert "Không tìm thấy" in window.project_workspace.recent_stores.panel.state_label.text()
