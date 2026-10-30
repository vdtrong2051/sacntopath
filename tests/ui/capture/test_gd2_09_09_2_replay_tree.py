"""GD2-09.09.2: real Qt + numbered SQLite v2 + replay integration.

All RAW/SQLite fixtures stay under pytest tmp_path; NEVER use scantopath-data.
No OrbbecSDK or physical camera required.
"""
from __future__ import annotations

import os
import threading
import time
from io import BytesIO

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
pytest.importorskip("PySide6")

import numpy as np
from PIL import Image
from PySide6.QtCore import Qt, QSettings
from PySide6.QtWidgets import QApplication

from scantopath.application.contracts import WorkspaceId
from scantopath.metadata.store import MetadataStore
from scantopath.storage.numbered import NumberedStorageRegistry
from scantopath.acquisition.raw_rgbd import RawRgbdCapture
from scantopath.modules.capture.presentation.replay_worker import ReplayThread
from scantopath.modules.project_workspace.presentation.store_management import RecentStorePreferences
from scantopath.ui.shell.main_window import ScanToPathMainWindow
from tests.support.raw_fixture import raw


def _until(qapp, condition, timeout=12.0):
    end = time.monotonic() + timeout
    while time.monotonic() < end:
        qapp.processEvents()
        if condition():
            qapp.processEvents()
            return
        time.sleep(0.01)
    raise AssertionError("09.09.2 Qt/SQLite worker timeout")


def _has_picture(label):
    value = label.pixmap()
    return value is not None and not value.isNull()


def _seed(root, ids=("cap-a", "cap-b"), *, close_session=False):
    with MetadataStore(root) as db:
        db.create_project("p1", "09.09.2 Project")
        db.create_specimen("s1", "p1", "09.09.2 Specimen")
        db.create_scan_session("t1", "s1", "09.09.2 Session")
    NumberedStorageRegistry.migrate_database(root)
    registry = NumberedStorageRegistry(root)
    paths = {}
    for index, cid in enumerate(ids):
        source = raw(session="t1", specimen="s1", capture_id=cid)
        rgb = np.zeros((16, 24, 3), dtype=np.uint8)
        rgb[:, :, :] = (180, 25 + index * 45, 7)
        payload = BytesIO()
        Image.fromarray(rgb).save(payload, format="JPEG", quality=95)
        jpeg = payload.getvalue()
        meta = source.metadata.model_copy(update={
            "color": source.metadata.color.model_copy(update={
                "width": 24, "height": 16, "payload_size_bytes": len(jpeg),
            }),
            "color_intrinsics": source.metadata.color_intrinsics.model_copy(update={
                "width": 24, "height": 16,
            }),
        })
        packet = RawRgbdCapture(metadata=meta, color_mjpeg=jpeg,
                                depth_y16_le=source.depth_y16_le)
        registry.reserve_capture(cid, "t1", "s1")
        registry.write_reserved_capture(packet)
        location = registry.register_reserved_capture(cid)
        paths[cid] = root / location.relative_path
    if close_session:
        with MetadataStore(root) as db:
            db.close_scan_session("t1")
    return paths


@pytest.fixture(scope="module")
def qapp():
    return QApplication.instance() or QApplication([])


@pytest.fixture
def window(qapp, tmp_path):
    win = ScanToPathMainWindow()
    # Isolate local QSettings bookmarks from an operator's real project history.
    recent = win.project_workspace.recent_stores
    recent._prefs = RecentStorePreferences(
        QSettings(str(tmp_path / "settings.ini"), QSettings.IniFormat)
    )
    recent.panel.display_recent(recent._prefs.paths())
    win.show()
    qapp.processEvents()
    yield win
    win.close()
    _until(qapp, lambda: not win.project_loader.busy and not win.capture_preview.busy
           and not win.project_writer.busy and win.capture_live.safe_to_dispose)
    qapp.processEvents()


def _load(qapp, win, root):
    win._begin_project_load(str(root))
    _until(qapp, lambda: not win.project_loader.busy)
    assert win.project_explorer.store_root == str(root.resolve())


def _capture_item(win, capture_id):
    tree = win.project_explorer.tree
    def walk(item):
        reference = item.data(0, Qt.UserRole)
        if (reference is not None and reference.entity_type == "capture"
                and reference.entity_id == capture_id):
            return item
        for index in range(item.childCount()):
            found = walk(item.child(index))
            if found is not None:
                return found
        return None
    for i in range(tree.topLevelItemCount()):
        target = walk(tree.topLevelItem(i))
        if target is not None:
            return target
    raise AssertionError("Capture missing from numbered Project Tree: " + capture_id)


def _capture_workspace(qapp, win):
    win.nav_buttons[WorkspaceId.CAPTURE].click()
    qapp.processEvents()


def _selected_picture_matches(qapp, win, capture_id):
    preview = win.capture_preview
    _until(qapp, lambda: not preview.busy
           and preview.context is not None
           and preview.context.capture_id == capture_id
           and f"Capture {capture_id}" in preview.panel.state_label.text()
           and _has_picture(preview.panel.rgb_image)
           and _has_picture(preview.panel.depth_image))


def test_select_capture_in_rgbd_workspace_auto_replays_v2(qapp, window, tmp_path):
    root = tmp_path / "numbered"
    _seed(root)
    _load(qapp, window, root)
    _capture_workspace(qapp, window)
    window.project_explorer.tree.setCurrentItem(_capture_item(window, "cap-a"))
    _selected_picture_matches(qapp, window, "cap-a")
    assert "24 × 16" in window.capture_preview.panel.metadata_label.text()
    assert "3 × 2" in window.capture_preview.panel.metadata_label.text()
    assert window.capture_live.state.value in ("idle", "IDLE")


def test_reselection_during_replay_ignores_stale_result(qapp, window, tmp_path, monkeypatch):
    root = tmp_path / "switch"
    _seed(root)
    _load(qapp, window, root)
    _capture_workspace(qapp, window)
    entered = threading.Event()
    release = threading.Event()
    original = ReplayThread.run
    def slow_replay(self):
        if self.context.capture_id == "cap-a":
            entered.set()
            release.wait(timeout=8)
        original(self)
    monkeypatch.setattr(ReplayThread, "run", slow_replay)
    try:
        window.project_explorer.tree.setCurrentItem(_capture_item(window, "cap-a"))
        _until(qapp, entered.is_set)
        assert window.capture_preview.busy
        window.project_explorer.tree.setCurrentItem(_capture_item(window, "cap-b"))
        qapp.processEvents()
        assert window.capture_preview.context.capture_id == "cap-b"
        assert not _has_picture(window.capture_preview.panel.rgb_image)
    finally:
        release.set()
    _selected_picture_matches(qapp, window, "cap-b")


def test_refresh_preserves_selected_capture_and_replays(qapp, window, tmp_path):
    root = tmp_path / "reload"
    _seed(root)
    _load(qapp, window, root)
    _capture_workspace(qapp, window)
    window.project_explorer.tree.setCurrentItem(_capture_item(window, "cap-a"))
    _selected_picture_matches(qapp, window, "cap-a")
    window._reload_project_store()
    _until(qapp, lambda: not window.project_loader.busy)
    _selected_picture_matches(qapp, window, "cap-a")
    assert window.project_explorer.selection.entity_id == "cap-a"


def test_closed_session_still_replays_existing_raw(qapp, window, tmp_path):
    root = tmp_path / "closed"
    _seed(root, ids=("cap-a",), close_session=True)
    _load(qapp, window, root)
    _capture_workspace(qapp, window)
    window.project_explorer.tree.setCurrentItem(_capture_item(window, "cap-a"))
    _selected_picture_matches(qapp, window, "cap-a")


def test_invalid_raw_clears_previous_capture(qapp, window, tmp_path):
    root = tmp_path / "damaged"
    paths = _seed(root)
    damaged = paths["cap-b"] / "depth.y16"
    damaged.write_bytes(damaged.read_bytes() + b"x")
    _load(qapp, window, root)
    _capture_workspace(qapp, window)
    window.project_explorer.tree.setCurrentItem(_capture_item(window, "cap-a"))
    _selected_picture_matches(qapp, window, "cap-a")
    window.project_explorer.tree.setCurrentItem(_capture_item(window, "cap-b"))
    _until(qapp, lambda: not window.capture_preview.busy and
           "checksum" in window.capture_preview.panel.state_label.text().lower())
    assert not _has_picture(window.capture_preview.panel.rgb_image)
    assert not _has_picture(window.capture_preview.panel.depth_image)


def test_navigation_from_projects_retains_manual_replay_contract(qapp, window, tmp_path):
    root = tmp_path / "manual"
    _seed(root, ids=("cap-a",))
    _load(qapp, window, root)
    # Select in Projects, then navigate. The old explicit Replay behavior remains.
    window.project_explorer.tree.setCurrentItem(_capture_item(window, "cap-a"))
    qapp.processEvents()
    assert window.capture_preview.context.capture_id == "cap-a"
    assert not window.capture_preview.busy
    _capture_workspace(qapp, window)
    assert window.capture_preview.panel.replay_button.isEnabled()
    window.capture_preview.panel.replay_button.click()
    _selected_picture_matches(qapp, window, "cap-a")


def test_changing_store_discards_capture_context(qapp, window, tmp_path):
    first = tmp_path / "first"
    second = tmp_path / "second"
    _seed(first, ids=("cap-a",))
    _seed(second, ids=("cap-b",))
    _load(qapp, window, first)
    _capture_workspace(qapp, window)
    window.project_explorer.tree.setCurrentItem(_capture_item(window, "cap-a"))
    _selected_picture_matches(qapp, window, "cap-a")
    _load(qapp, window, second)
    assert window.project_explorer.selection is None
    assert window.capture_preview.context is None
    assert not _has_picture(window.capture_preview.panel.rgb_image)
    assert not window.capture_preview.panel.replay_button.isEnabled()


def test_selecting_non_capture_clears_replay_images(qapp, window, tmp_path):
    root = tmp_path / "unselect"
    _seed(root, ids=("cap-a",))
    _load(qapp, window, root)
    _capture_workspace(qapp, window)
    window.project_explorer.tree.setCurrentItem(_capture_item(window, "cap-a"))
    _selected_picture_matches(qapp, window, "cap-a")
    tree = window.project_explorer.tree
    project = tree.topLevelItem(0)
    specimen = project.child(0)
    session = specimen.child(0)
    assert session.data(0, Qt.UserRole).entity_type == "scan_session"
    tree.setCurrentItem(session)
    qapp.processEvents()
    assert window.capture_preview.context is None
    assert not _has_picture(window.capture_preview.panel.rgb_image)
    assert not _has_picture(window.capture_preview.panel.depth_image)
    assert not window.capture_preview.panel.replay_button.isEnabled()
