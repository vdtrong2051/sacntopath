"""GD2-09.09.5 offline E2E: bootstrap -> CRUD -> synthetic keyframes -> RAW v2
-> SQLite/Numbered registry -> decode/Qt replay/activity -> close/reopen.

STRICT: uses pytest tmp_path/scantopath-data ONLY. It NEVER opens a real camera,
never claims measured RGB-D, and never accesses the operator's data workspace.
"""
from __future__ import annotations

import hashlib
import json
import os
import sqlite3
import time
from io import BytesIO

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest
import numpy as np
from PIL import Image

pytest.importorskip("PySide6")
from PySide6.QtCore import Qt, QSettings
from PySide6.QtWidgets import QApplication

from scantopath.acquisition.raw_rgbd import RawRgbdCapture
from scantopath.application.contracts import WorkspaceId
from scantopath.modules.capture.application.capture_pipeline import (
    CapturePipelineService, CapturePipelineError,
)
from scantopath.modules.capture.application.capture_service import CaptureCommitService
from scantopath.modules.capture.application.contracts import CaptureContext
from scantopath.modules.capture.application.decoding import RgbdDecoder
from scantopath.modules.capture.application.replay import RawReplayError, RawReplayService
from scantopath.modules.capture.infrastructure.capture_writer import NumberedCapturePersistenceAdapter
from scantopath.modules.capture.infrastructure.jpeg_codec import PillowMjpegDecoder
from scantopath.modules.capture.infrastructure.raw_reader import RawReaderAdapter
from scantopath.modules.project_workspace.application.service import ProjectWorkspaceService
from scantopath.modules.project_workspace.infrastructure.store_bootstrap import (
    initialize_empty_data_workspace,
)
from scantopath.modules.project_workspace.presentation.store_management import RecentStorePreferences
from scantopath.storage.numbered import NumberedStorageRegistry
from scantopath.ui.shell.main_window import ScanToPathMainWindow
from tests.support.raw_fixture import raw


def _wait(qapp, predicate, *, seconds=15.0):
    deadline = time.monotonic() + seconds
    while time.monotonic() < deadline:
        qapp.processEvents()
        if predicate():
            qapp.processEvents()
            return
        time.sleep(0.01)
    raise AssertionError("GD2-09.09.5 Qt worker timed out")


def _has_image(label):
    pixmap = label.pixmap()
    return pixmap is not None and not pixmap.isNull()


def _find_tree_item(tree, entity_type, entity_id):
    def find(node):
        ref = node.data(0, Qt.UserRole)
        if ref is not None and ref.entity_type == entity_type and ref.entity_id == entity_id:
            return node
        for i in range(node.childCount()):
            hit = find(node.child(i))
            if hit is not None:
                return hit
        return None
    for i in range(tree.topLevelItemCount()):
        hit = find(tree.topLevelItem(i))
        if hit is not None:
            return hit
    raise AssertionError(f"Missing {entity_type}: {entity_id}")


class _OfflineKeyframes:
    """SYNTHETIC acquisition-port fake; no SDK/native handle or hardware access."""

    def __init__(self):
        self.sequence = 0

    def capture_next_raw(self, *, session_id, specimen_id):
        self.sequence += 1
        seq = self.sequence
        rgb = np.empty((16, 24, 3), dtype=np.uint8)
        rgb[:] = (30 + 20 * seq, 75, 170)
        rgb[:, 12:, :] = (180, 25 * seq, 30)
        buf = BytesIO()
        Image.fromarray(rgb).save(buf, format="JPEG", quality=96, subsampling=0)
        jpeg = buf.getvalue()

        base = raw(session=session_id, specimen=specimen_id,
                   capture_id=f"offline-e2e-capture-{seq:03d}")
        meta = base.metadata.model_copy(update={
            "color": base.metadata.color.model_copy(update={
                "width": 24, "height": 16,
                "frame_index": seq,
                "timestamp_us": 100_000 + seq * 40_000,
                "payload_size_bytes": len(jpeg),
            }),
            "depth": base.metadata.depth.model_copy(update={
                "frame_index": seq,
                "timestamp_us": 101_000 + seq * 40_000,
            }),
            "color_intrinsics": base.metadata.color_intrinsics.model_copy(update={
                "width": 24, "height": 16,
            }),
        })
        return RawRgbdCapture(metadata=meta, color_mjpeg=jpeg,
                              depth_y16_le=base.depth_y16_le)


@pytest.fixture(scope="module")
def qapp():
    return QApplication.instance() or QApplication([])


def _make_workspace(tmp_path):
    root = tmp_path / "scantopath-data"
    assert not root.exists()
    assert initialize_empty_data_workspace(root) == root.resolve()
    service = ProjectWorkspaceService(root)
    p = service.create_project("Offline E2E Project")
    service.update_project(p.project_id, name="Offline E2E Project (updated)")
    s = service.create_specimen(p.project_id, "Fixture specimen")
    service.update_specimen(p.project_id, s.specimen_id, label="Fixture specimen v2")
    t = service.create_session(s.specimen_id, "Acquisition session")
    service.update_session(s.specimen_id, t.session_id, label="Acquisition session v2")
    assert service.get_project_tree(p.project_id).specimens[0].sessions[0].session_id == t.session_id
    return root, service, p.project_id, s.specimen_id, t.session_id


def _make_pipeline():
    adapter = NumberedCapturePersistenceAdapter()
    camera = _OfflineKeyframes()
    return CapturePipelineService(camera, CaptureCommitService(adapter), adapter)


def _commit_two(root, pid, sid, tid):
    pipe = _make_pipeline()
    ctx = CaptureContext(str(root), pid, sid, tid)
    receipts = [pipe.capture_and_commit(ctx) for _ in range(2)]
    assert len({r.capture_id for r in receipts}) == 2
    assert [r.color_frame_index for r in receipts] == [1, 2]
    assert [r.depth_frame_index for r in receipts] == [1, 2]
    return receipts, ctx, pipe


def _assert_sqlite_and_raw(root, receipts):
    registry = NumberedStorageRegistry(root)
    assert registry.pending_reservations() == ()
    paths = set()
    for receipt in receipts:
        location = registry.resolve_id("capture", receipt.capture_id, verify=True)
        assert location.layout_version == 2
        paths.add(str(location.relative_path))
        folder = root / location.relative_path
        assert (folder / "COMMITTED").is_file()
        manifest = json.loads((folder / "manifest.json").read_text(encoding="utf-8"))
        for filename in ("color.mjpg", "depth.y16", "metadata.json"):
            actual = hashlib.sha256((folder / filename).read_bytes()).hexdigest()
            assert actual == manifest["files"][filename]["sha256"]
    assert len(paths) == len(receipts)
    with sqlite3.connect(root / "metadata.sqlite3") as con:
        assert con.execute("PRAGMA user_version").fetchone()[0] == 2
        assert con.execute("PRAGMA integrity_check").fetchone()[0] == "ok"
        assert con.execute("PRAGMA foreign_key_check").fetchall() == []
        assert con.execute("SELECT COUNT(*) FROM captures").fetchone()[0] == len(receipts)
        assert con.execute("SELECT COUNT(*) FROM storage_capture_reservations").fetchone()[0] == 0
    return RawReplayService(RawReaderAdapter()), RgbdDecoder(PillowMjpegDecoder())


def _replay_and_decode(reader, decoder, root, pid, sid, tid, receipt):
    ctx = CaptureContext(str(root), pid, sid, tid, receipt.capture_id)
    packet = reader.load(ctx)
    assert packet.metadata.capture_id == receipt.capture_id
    assert not packet.metadata.measured  # explicitly SYNTHETIC, never Gemini 2 evidence
    assert packet.metadata.camera_pose is None
    assert hashlib.sha256(packet.color_mjpeg).hexdigest() == receipt.color_sha256
    assert hashlib.sha256(packet.depth_y16_le).hexdigest() == receipt.depth_sha256
    decoded = decoder.decode(packet)
    assert decoded.color_rgb.shape == (16, 24, 3)
    assert decoded.depth_u16.shape == (2, 3)
    assert decoded.depth_u16.dtype == np.uint16
    return decoded


def test_offline_full_lifecycle_to_qt_replay_and_reopen(tmp_path, qapp):
    root, service, pid, sid, tid = _make_workspace(tmp_path)
    receipts, ctx, pipeline = _commit_two(root, pid, sid, tid)
    reader, decoder = _assert_sqlite_and_raw(root, receipts)
    for receipt in receipts:
        _replay_and_decode(reader, decoder, root, pid, sid, tid, receipt)

    # Protect existing physical RAW against destructive CRUD.
    with pytest.raises(ValueError, match="ENTITY_HAS_CHILDREN"):
        service.delete_empty_entity("session", tid, sid)

    # Session is closed before Qt replay; read-only Replay must still succeed.
    assert service.close_session(sid, tid).state == "closed"
    with pytest.raises(CapturePipelineError) as rejection:
        pipeline.capture_and_commit(ctx)
    assert rejection.value.code == "SESSION_NOT_OPEN"
    assert NumberedStorageRegistry(root).pending_reservations() == ()

    window = ScanToPathMainWindow()
    # Never overwrite the operator's actual recent-store preferences.
    recent = window.project_workspace.recent_stores
    recent._prefs = RecentStorePreferences(
        QSettings(str(tmp_path / "e2e-prefs.ini"), QSettings.IniFormat)
    )
    recent.panel.display_recent(recent._prefs.paths())
    try:
        window.resize(1200, 780)
        window.show()
        qapp.processEvents()
        assert window.workspace_stack.count() == 4
        assert window.capture_workspace_layout.tabs.count() == 2
        assert window.capture_live.state.value == "idle"
        assert window.project_explorer.store_root is None  # no auto-open

        window._begin_project_load(str(root))
        _wait(qapp, lambda: not window.project_loader.busy and
              window.project_explorer.store_root == str(root.resolve()))
        assert window.project_explorer.tree.topLevelItemCount() == 1
        window.nav_buttons[WorkspaceId.CAPTURE].click()
        qapp.processEvents()
        cid = receipts[0].capture_id
        tree_item = _find_tree_item(window.project_explorer.tree, "capture", cid)
        window.project_explorer.tree.setCurrentItem(tree_item)
        _wait(qapp, lambda: not window.capture_preview.busy and
              window.capture_preview.context is not None and
              window.capture_preview.context.capture_id == cid and
              f"Capture {cid}" in window.capture_preview.panel.state_label.text() and
              _has_image(window.capture_preview.panel.rgb_image) and
              _has_image(window.capture_preview.panel.depth_image))
        assert window.capture_workspace_layout.tabs.currentWidget() is window.capture_preview.panel
        assert "24 × 16" in window.capture_preview.panel.metadata_label.text()
        assert "3 × 2" in window.capture_preview.panel.metadata_label.text()
        assert window.task_event_panel.operation_table.topLevelItemCount() > 0
        assert window.task_event_panel.audit_table is not window.task_event_panel.operation_table

        # Refresh must retain a Capture selection; no duplicate RAW writes.
        window._reload_project_store()
        _wait(qapp, lambda: not window.project_loader.busy and
              window.project_explorer.selection is not None and
              window.project_explorer.selection.entity_id == cid)
        _wait(qapp, lambda: not window.capture_preview.busy and
              _has_image(window.capture_preview.panel.rgb_image))
        assert window.capture_live.state.value == "idle"
    finally:
        window.close()
        _wait(qapp, lambda: not window.project_loader.busy and
              not window.capture_preview.busy and
              not window.project_writer.busy and
              window.capture_live.safe_to_dispose)
        qapp.processEvents()

    again = ProjectWorkspaceService(root)
    tree = again.get_project_tree(pid)
    assert tree.project.name == "Offline E2E Project (updated)"
    assert tree.specimens[0].specimen.label == "Fixture specimen v2"
    assert tree.specimens[0].sessions[0].state == "closed"
    assert {c.capture_id for c in tree.specimens[0].sessions[0].captures} == {
        r.capture_id for r in receipts
    }
    _assert_sqlite_and_raw(root, receipts)


def test_offline_tampering_is_detected_and_cannot_corrupt_operator_data(tmp_path):
    root, service, pid, sid, tid = _make_workspace(tmp_path)
    receipts, _, _ = _commit_two(root, pid, sid, tid)
    registry = NumberedStorageRegistry(root)
    location = registry.resolve_id("capture", receipts[1].capture_id, verify=True)
    damaged = root / location.relative_path / "depth.y16"
    damaged.write_bytes(damaged.read_bytes() + b"tampered")
    with pytest.raises(RawReplayError):
        RawReplayService(RawReaderAdapter()).load(
            CaptureContext(str(root), pid, sid, tid, receipts[1].capture_id)
        )
    # Other capture and SQLite remain intact. Tampering stays inside tmp_path.
    reader = RawReplayService(RawReaderAdapter())
    original = reader.load(CaptureContext(str(root), pid, sid, tid, receipts[0].capture_id))
    assert original.metadata.capture_id == receipts[0].capture_id
    with sqlite3.connect(root / "metadata.sqlite3") as con:
        assert con.execute("PRAGMA integrity_check").fetchone()[0] == "ok"
        assert con.execute("PRAGMA foreign_key_check").fetchall() == []
