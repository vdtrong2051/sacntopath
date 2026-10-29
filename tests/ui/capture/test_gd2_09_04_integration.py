
"""GD2-09.04: real Qt + SQLite + RAW offline integration tests.

All stores are disposable; no physical Gemini 2 or production data.
"""
from __future__ import annotations

import os
import subprocess
import sys
import threading
import time
from io import BytesIO
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import numpy as np
import pytest

pytest.importorskip("PySide6")

from PIL import Image
from PySide6.QtCore import Qt, QSettings
from PySide6.QtWidgets import QApplication, QFrame

from scantopath.acquisition.raw_rgbd import RawRgbdCapture
from scantopath.application.contracts import WorkspaceId
from scantopath.metadata.store import MetadataStore
from scantopath.storage.session_store import SessionStore
from scantopath.modules.project_workspace.presentation.store_management import (
    RecentStorePreferences,
)
from scantopath.modules.capture.presentation.replay_worker import ReplayThread
from scantopath.ui.shell import ScanToPathMainWindow
from tests.support.raw_fixture import raw


def _has_image(label) -> bool:
    """Return True only when QLabel contains a non-null QPixmap."""
    pixmap = label.pixmap()
    return pixmap is not None and not pixmap.isNull()


@pytest.fixture(scope="module")
def qapp():
    return QApplication.instance() or QApplication([])


@pytest.fixture
def window(qapp, tmp_path):
    win = ScanToPathMainWindow()

    # Do not modify the operator's real recent-store preferences.
    recent = win.project_workspace.recent_stores
    recent._prefs = RecentStorePreferences(
        QSettings(
            str(tmp_path / "preferences.ini"),
            QSettings.IniFormat,
        )
    )
    recent.panel.display_recent(recent._prefs.paths())

    win.resize(1200, 760)
    win.show()
    qapp.processEvents()

    yield win

    win.close()
    _until(
        qapp,
        lambda: (
            not win.capture_preview.busy
            and not win.project_loader.busy
            and not win.project_writer.busy
            and not win.capture_checker.busy
        ),
    )
    qapp.processEvents()


def _until(qapp, predicate, timeout=12.0):
    deadline = time.monotonic() + timeout

    while time.monotonic() < deadline:
        qapp.processEvents()

        if predicate():
            qapp.processEvents()
            return

        time.sleep(0.01)

    raise AssertionError("GD2-09.04 Qt worker timed out")


def _jpeg(*, malformed=False):
    if malformed:
        return b"\xff\xd8invalid-jpeg-fixture\xff\xd9"

    pixels = np.full(
        (16, 24, 3),
        (245, 5, 3),
        dtype=np.uint8,
    )

    pixels[:, 12:, :] = (2, 5, 245)

    out = BytesIO()
    Image.fromarray(pixels).save(
        out,
        format="JPEG",
        quality=100,
        subsampling=0,
    )
    return out.getvalue()


def _seed(root: Path, *, malformed=False):
    with MetadataStore(root) as db:
        db.create_project("p1", "UI Test Project")
        db.create_specimen("s1", "p1", "UI Test Specimen")
        db.create_scan_session("t1", "s1", "UI Test Session")

    packet = raw(
        session="t1",
        specimen="s1",
        capture_id="c1",
    )

    jpeg = _jpeg(malformed=malformed)

    meta = packet.metadata.model_copy(update={
        "color": packet.metadata.color.model_copy(update={
            "width": 24,
            "height": 16,
            "payload_size_bytes": len(jpeg),
        }),
        "color_intrinsics": packet.metadata.color_intrinsics.model_copy(update={
            "width": 24,
            "height": 16,
        }),
    })

    packet = RawRgbdCapture(
        metadata=meta,
        color_mjpeg=jpeg,
        depth_y16_le=packet.depth_y16_le,
    )

    location = SessionStore(root).commit_raw(packet)

    with MetadataStore(root) as db:
        db.register_capture(location)

    return location


def _load(window, qapp, root):
    window._begin_project_load(str(root))

    _until(qapp, lambda: not window.project_loader.busy)

    assert window.project_explorer.store_root == str(
        root.resolve()
    )


def _select_capture(window, qapp):
    tree = window.project_explorer.tree

    def find(item):
        ref = item.data(0, Qt.UserRole)

        if (
            ref is not None
            and ref.entity_type == "capture"
            and ref.entity_id == "c1"
        ):
            return item

        for i in range(item.childCount()):
            result = find(item.child(i))
            if result is not None:
                return result

        return None

    target = None

    for index in range(tree.topLevelItemCount()):
        target = find(tree.topLevelItem(index))
        if target is not None:
            break

    assert target is not None
    tree.setCurrentItem(target)
    qapp.processEvents()


def _open_capture_workspace(window, qapp):
    window.nav_buttons[WorkspaceId.CAPTURE].click()
    qapp.processEvents()


def test_capture_is_existing_workspace_and_not_new_dock(window):
    assert window.workspace_stack.count() == 4

    assert window.page_for(WorkspaceId.CAPTURE).objectName() == (
        "workspace_capture"
    )

    page = window.page_for(WorkspaceId.CAPTURE)

    assert page.findChild(QFrame, "workspacePanel") is not None
    assert page.findChild(QFrame, "capturePreview") is not None

    assert window.explorer_dock.objectName() == "explorerDock"
    assert window.inspector_dock.objectName() == "inspectorDock"
    assert window.task_dock.objectName() == "taskDock"

    assert window.capture_preview.context is None


def test_capture_navigation_does_not_open_store_or_camera(window, qapp):
    _open_capture_workspace(window, qapp)

    assert not window.capture_preview.busy
    assert window.capture_preview.context is None
    assert not window.capture_preview.panel.replay_button.isEnabled()

    assert window.project_explorer.store_root is None


def test_selected_capture_survives_navigation_handoff(
    window, qapp, tmp_path,
):
    root = tmp_path / "handoff-store"

    _seed(root)
    _load(window, qapp, root)
    _select_capture(window, qapp)

    assert window.capture_preview.context.capture_id == "c1"

    _open_capture_workspace(window, qapp)

    # GĐ1 navigation contract remains unchanged.
    assert window.project_explorer.selection is None

    # Capture owns an explicit immutable context snapshot.
    assert window.capture_preview.context.capture_id == "c1"
    assert window.capture_preview.panel.replay_button.isEnabled()


def test_replay_displays_rgb_and_depth_in_qt(
    window, qapp, tmp_path,
):
    root = tmp_path / "replay-store"

    _seed(root)
    _load(window, qapp, root)
    _select_capture(window, qapp)
    _open_capture_workspace(window, qapp)

    panel = window.capture_preview.panel

    panel.replay_button.click()

    _until(qapp, lambda: not window.capture_preview.busy)

    assert _has_image(panel.rgb_image)
    assert _has_image(panel.depth_image)

    assert "Đã phát lại RAW v2" in panel.state_label.text()
    assert "24 × 16" in panel.metadata_label.text()
    assert "3 × 2" in panel.metadata_label.text()


def test_bad_jpeg_is_reported_without_stale_preview(
    window, qapp, tmp_path,
):
    root = tmp_path / "invalid-jpeg-store"

    _seed(root, malformed=True)
    _load(window, qapp, root)
    _select_capture(window, qapp)
    _open_capture_workspace(window, qapp)

    panel = window.capture_preview.panel
    panel.replay_button.click()

    _until(qapp, lambda: not window.capture_preview.busy)

    assert "JPEG" in panel.state_label.text()
    assert not _has_image(panel.rgb_image)
    assert not _has_image(panel.depth_image)


def test_failed_store_change_invalidates_capture(
    window, qapp, tmp_path,
):
    root = tmp_path / "valid-store"

    _seed(root)
    _load(window, qapp, root)
    _select_capture(window, qapp)

    assert window.capture_preview.context is not None

    window._begin_project_load(str(tmp_path / "missing-store"))

    _until(qapp, lambda: not window.project_loader.busy)

    assert window.capture_preview.context is None
    assert not window.capture_preview.panel.replay_button.isEnabled()


def test_close_waits_for_active_replay_worker(
    window, qapp, tmp_path, monkeypatch,
):
    root = tmp_path / "slow-replay-store"

    _seed(root)
    _load(window, qapp, root)
    _select_capture(window, qapp)
    _open_capture_workspace(window, qapp)

    entered = threading.Event()
    release = threading.Event()

    original_run = ReplayThread.run

    def slow_run(self):
        entered.set()

        # Simulate an ongoing offline I/O operation.
        release.wait(timeout=5)
        original_run(self)

    monkeypatch.setattr(ReplayThread, "run", slow_run)

    try:
        assert window.capture_preview.replay()

        _until(qapp, entered.is_set)

        window.close()
        qapp.processEvents()

        assert window.isVisible()
        assert window.capture_preview.busy

    finally:
        release.set()

    _until(
        qapp,
        lambda: (
            not window.capture_preview.busy
            and not window.isVisible()
        ),
    )


def test_ui_import_does_not_load_camera_or_sqlite():
    code = (
        "import sys; "
        "import scantopath.ui.main; "
        "assert 'scantopath.metadata.store' not in sys.modules; "
        "assert 'scantopath.acquisition.native' not in sys.modules; "
        "print('UI_IMPORT_ISOLATED')"
    )

    result = subprocess.run(
        [sys.executable, "-c", code],
        capture_output=True,
        text=True,
        timeout=20,
        check=False,
    )

    assert result.returncode == 0, result.stderr
    assert "UI_IMPORT_ISOLATED" in result.stdout
