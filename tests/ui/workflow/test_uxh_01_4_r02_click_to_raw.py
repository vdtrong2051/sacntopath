"""R02 real Qt/SQLite/RAW regression: mouse click, not setCurrentItem, opens saved RAW.

Uses the existing GDPR-09 numbered SQLite/RAW fixtures in pytest tmp_path.
No hardware/VTK process starts; no production metadata is modified.
"""
from __future__ import annotations

import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest
pytest.importorskip("PySide6")
from PySide6.QtCore import Qt
from PySide6.QtTest import QTest
from scantopath.application.contracts import WorkspaceId

from tests.ui.capture.test_gd2_09_09_2_replay_tree import (
    qapp, window, _seed, _load, _capture_item, _selected_picture_matches,
    _has_picture, _until,
)


def _click_tree_capture(win, capture_id):
    item = _capture_item(win, capture_id)
    node = item.parent()
    while node is not None:
        node.setExpanded(True)
        node = node.parent()
    tree = win.project_explorer.tree
    tree.scrollToItem(item)
    point = tree.visualItemRect(item).center()
    assert point.x() >= 0 and point.y() >= 0
    QTest.mouseClick(tree.viewport(), Qt.MouseButton.LeftButton, pos=point)


def test_programmatic_selection_and_reload_are_not_user_clicks(qapp, window, tmp_path):
    root = tmp_path / "programmatic"
    _seed(root, ids=("cap-a",))
    _load(qapp, window, root)
    window.project_explorer.tree.setCurrentItem(_capture_item(window, "cap-a"))
    qapp.processEvents()
    assert window.active_workspace is WorkspaceId.PROJECTS
    assert window.capture_preview.context.capture_id == "cap-a"
    assert not window.capture_preview.busy
    assert not _has_picture(window.capture_preview.panel.rgb_image)

    window._reload_project_store()
    _until(qapp, lambda: not window.project_loader.busy)
    qapp.processEvents()
    assert window.project_explorer.selection.entity_id == "cap-a"
    assert window.active_workspace is WorkspaceId.PROJECTS
    assert not window.capture_preview.busy


def test_click_capture_in_explorer_opens_existing_raw_tab(qapp, window, tmp_path):
    root = tmp_path / "explorer"
    _seed(root, ids=("cap-a",))
    _load(qapp, window, root)
    _click_tree_capture(window, "cap-a")
    qapp.processEvents()
    assert window.active_workspace is WorkspaceId.CAPTURE
    assert window.capture_workspace_layout.tabs.currentWidget() is window.capture_preview.panel
    _selected_picture_matches(qapp, window, "cap-a")


def test_click_capture_in_project_dashboard_opens_same_raw(qapp, window, tmp_path):
    root = tmp_path / "dashboard"
    _seed(root, ids=("cap-b",))
    _load(qapp, window, root)
    dashboard = window.project_workspace.project_dashboard.panel
    # Project table may start with no project selected; select its real entry.
    dashboard.project_combo.setCurrentIndex(1)
    dashboard.tabs.setCurrentWidget(dashboard.tables["capture"])
    qapp.processEvents()
    table = dashboard.tables["capture"]
    assert table.topLevelItemCount() == 1
    item = table.topLevelItem(0)
    table.scrollToItem(item)
    point = table.visualItemRect(item).center()
    QTest.mouseClick(table.viewport(), Qt.MouseButton.LeftButton, pos=point)
    qapp.processEvents()
    assert window.active_workspace is WorkspaceId.CAPTURE
    assert window.capture_workspace_layout.tabs.currentWidget() is window.capture_preview.panel
    _selected_picture_matches(qapp, window, "cap-b")


def test_second_click_same_capture_does_not_decode_again(qapp, window, tmp_path, monkeypatch):
    root = tmp_path / "repeat"
    _seed(root, ids=("cap-a",))
    _load(qapp, window, root)
    _click_tree_capture(window, "cap-a")
    _selected_picture_matches(qapp, window, "cap-a")
    calls = []
    def should_not_replay():
        calls.append(True)
        raise AssertionError("duplicate Replay triggered")
    monkeypatch.setattr(window.capture_preview, "replay", should_not_replay)
    _click_tree_capture(window, "cap-a")
    qapp.processEvents()
    assert calls == []
    assert window.active_workspace is WorkspaceId.CAPTURE
    assert _has_picture(window.capture_preview.panel.rgb_image)


def test_explicit_selection_of_non_capture_does_not_route(qapp, window, tmp_path):
    root = tmp_path / "notcapture"
    _seed(root, ids=("cap-a",))
    _load(qapp, window, root)
    tree = window.project_explorer.tree
    project = tree.topLevelItem(0)
    rect = tree.visualItemRect(project)
    QTest.mouseClick(tree.viewport(), Qt.MouseButton.LeftButton, pos=rect.center())
    qapp.processEvents()
    assert window.active_workspace is WorkspaceId.PROJECTS
    assert window.capture_preview.context is None


def test_dashboard_programmatic_selection_is_not_open_request(qapp, window, tmp_path):
    root = tmp_path / "dashboard_programmatic"
    _seed(root, ids=("cap-a",))
    _load(qapp, window, root)
    dashboard = window.project_workspace.project_dashboard.panel
    dashboard.project_combo.setCurrentIndex(1)
    dashboard.tabs.setCurrentWidget(dashboard.tables["capture"])
    table = dashboard.tables["capture"]
    assert table.topLevelItemCount() == 1
    table.setCurrentItem(table.topLevelItem(0))
    qapp.processEvents()
    assert window.project_explorer.selection.entity_id == "cap-a"
    assert window.active_workspace is WorkspaceId.PROJECTS
    assert not window.capture_preview.busy
