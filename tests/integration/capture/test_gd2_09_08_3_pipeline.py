"""09.08.3 camera -> persisted RAW -> SQLite -> Replay on isolated test stores.

Synthetic camera facts are explicitly labelled SYNTHETIC, never hardware PASS.
"""
from __future__ import annotations

import sqlite3

import pytest

from scantopath.metadata.store import MetadataStore
from scantopath.storage.numbered import NumberedStorageRegistry
from scantopath.modules.capture.application.capture_service import CaptureCommitService
from scantopath.modules.capture.application.capture_pipeline import CapturePipelineService, CapturePipelineError
from scantopath.modules.capture.application.contracts import CaptureContext
from scantopath.modules.capture.application.replay import RawReplayService
from scantopath.modules.capture.infrastructure.capture_writer import NumberedCapturePersistenceAdapter
from scantopath.modules.capture.infrastructure.raw_reader import RawReaderAdapter
from scantopath.modules.capture.infrastructure.process_camera import ProcessIsolatedCameraAdapter
from tests.support.gd2_0983_camera_fakes import (
    good_pipeline_camera, crashing_pipeline_camera, timing_out_pipeline_camera,
)


@pytest.fixture
def root(tmp_path):
    with MetadataStore(tmp_path) as db:
        db.create_project("p1", "integration fixture")
        db.create_specimen("s1", "p1", "synthetic specimen")
        db.create_scan_session("t1", "s1", "synthetic session")
    NumberedStorageRegistry.migrate_database(tmp_path)
    return tmp_path


def context(root, *, session="t1", project="p1", specimen="s1", capture_id=None):
    return CaptureContext(str(root), project, specimen, session, capture_id)


def pipeline(camera, writer=None):
    writer = writer or NumberedCapturePersistenceAdapter()
    return CapturePipelineService(camera, CaptureCommitService(writer), writer)


def replay(root, cid):
    return RawReplayService(RawReaderAdapter()).load(context(root, capture_id=cid))


def test_five_real_sqlite_transactions_via_crash_isolated_fake_camera(root):
    camera = ProcessIsolatedCameraAdapter(camera_factory=good_pipeline_camera)
    camera.open()
    try:
        first = camera.read_next(per_attempt_timeout_ms=300, max_attempts=1)
        assert first.color_mjpeg.startswith(b"preview-")
        session = pipeline(camera)
        receipts = [session.capture_and_commit(context(root)) for _ in range(5)]
        resumed = camera.read_next(per_attempt_timeout_ms=300, max_attempts=1)
        assert resumed.color_frame_index > first.color_frame_index
    finally:
        camera.close()
    assert camera.last_exit_code == 0
    assert len(set(r.capture_id for r in receipts)) == 5
    assert [r.color_frame_index for r in receipts] == [2, 3, 4, 5, 6]
    registry = NumberedStorageRegistry(root)
    locations = [registry.resolve_id("capture", r.capture_id, verify=True) for r in receipts]
    assert len(set(loc.relative_path for loc in locations)) == 5
    assert not registry.pending_reservations()
    for r in receipts:
        packet = replay(root, r.capture_id)
        assert packet.metadata.measured is False
        assert packet.metadata.kind.value == "synthetic"
        assert packet.metadata.color.frame_index == r.color_frame_index
        assert packet.metadata.depth.frame_index == r.depth_frame_index
        assert packet.metadata.camera_pose is None
    with sqlite3.connect(root / "metadata.sqlite3") as db:
        assert db.execute("SELECT COUNT(*) FROM captures").fetchone()[0] == 5
        assert db.execute("SELECT COUNT(*) FROM storage_captures").fetchone()[0] == 5


@pytest.mark.parametrize("session,project", [("other", "p1"), ("t1", "other")])
def test_context_rejected_without_camera_capture_or_reservation(root, session, project):
    class NeverRead:
        def capture_next_raw(self, **_):
            raise AssertionError("preflight should prevent this read")
    with pytest.raises(CapturePipelineError) as e:
        pipeline(NeverRead()).capture_and_commit(context(root, session=session, project=project))
    assert e.value.code == "CAPTURE_CONTEXT_MISMATCH"
    assert NumberedStorageRegistry(root).pending_reservations() == ()


def test_session_closed_before_acquisition_no_orphan(root):
    with MetadataStore(root) as db:
        db.close_scan_session("t1")
    class NeverRead:
        def capture_next_raw(self, **_):
            raise AssertionError("closed session should reject before read")
    with pytest.raises(CapturePipelineError) as e:
        pipeline(NeverRead()).capture_and_commit(context(root))
    assert e.value.code == "SESSION_NOT_OPEN"
    assert NumberedStorageRegistry(root).pending_reservations() == ()


def test_capture_timeout_leaves_no_reservation(root):
    camera = ProcessIsolatedCameraAdapter(camera_factory=timing_out_pipeline_camera)
    camera.open()
    try:
        with pytest.raises(CapturePipelineError) as e:
            pipeline(camera).capture_and_commit(context(root))
        assert e.value.code == "CAPTURE_TIMEOUT"
    finally:
        camera.close()
    assert NumberedStorageRegistry(root).pending_reservations() == ()


def test_child_fatal_exit_is_isolated_no_registered_capture(root):
    camera = ProcessIsolatedCameraAdapter(camera_factory=crashing_pipeline_camera)
    camera.open()
    try:
        with pytest.raises(CapturePipelineError) as e:
            pipeline(camera).capture_and_commit(context(root))
        assert e.value.code == "DEVICE_PROCESS_CRASH"
    finally:
        try:
            camera.close()
        except Exception:
            pass
    assert camera.child_pid is None
    assert NumberedStorageRegistry(root).pending_reservations() == ()
    with sqlite3.connect(root / "metadata.sqlite3") as db:
        assert db.execute("SELECT COUNT(*) FROM captures").fetchone()[0] == 0


def test_sqlite_failure_retains_recoverable_raw_without_false_success(root, monkeypatch):
    camera = ProcessIsolatedCameraAdapter(camera_factory=good_pipeline_camera)
    original = NumberedStorageRegistry.register_reserved_capture
    def fail_registry(self, capture_id):
        raise sqlite3.OperationalError("injected SQLite failure")
    monkeypatch.setattr(NumberedStorageRegistry, "register_reserved_capture", fail_registry)
    camera.open()
    try:
        with pytest.raises(CapturePipelineError) as e:
            pipeline(camera).capture_and_commit(context(root))
        assert e.value.code == "CAPTURE_REGISTRATION_FAILED"
    finally:
        camera.close()
    registry = NumberedStorageRegistry(root)
    pending = registry.pending_reservations()
    assert len(pending) == 1
    cid = pending[0].capture_id
    assert (root / pending[0].relative_path / "COMMITTED").is_file()
    monkeypatch.setattr(NumberedStorageRegistry, "register_reserved_capture", original)
    assert NumberedCapturePersistenceAdapter().recover(context(root), cid) == cid
    assert replay(root, cid).metadata.capture_id == cid
    assert not NumberedStorageRegistry(root).pending_reservations()


def test_filesystem_failure_has_no_registered_capture(root, monkeypatch):
    camera = ProcessIsolatedCameraAdapter(camera_factory=good_pipeline_camera)
    def disk_full(_registry, _raw):
        raise OSError("fake disk full")
    monkeypatch.setattr(NumberedStorageRegistry, "write_reserved_capture", disk_full)
    camera.open()
    try:
        with pytest.raises(CapturePipelineError) as e:
            pipeline(camera).capture_and_commit(context(root))
        assert e.value.code == "RAW_WRITE_FAILED"
    finally:
        camera.close()
    assert len(NumberedStorageRegistry(root).pending_reservations()) == 1
    with sqlite3.connect(root / "metadata.sqlite3") as db:
        assert db.execute("SELECT COUNT(*) FROM captures").fetchone()[0] == 0


def test_close_session_during_registration_rejected_and_preserved(root, monkeypatch):
    camera = ProcessIsolatedCameraAdapter(camera_factory=good_pipeline_camera)
    original = NumberedStorageRegistry.register_reserved_capture
    def close_midway(registry, capture_id):
        with MetadataStore(root) as db:
            db.close_scan_session("t1")
        return original(registry, capture_id)
    monkeypatch.setattr(NumberedStorageRegistry, "register_reserved_capture", close_midway)
    camera.open()
    try:
        with pytest.raises(CapturePipelineError) as e:
            pipeline(camera).capture_and_commit(context(root))
        assert e.value.code == "CAPTURE_REGISTRATION_FAILED"
    finally:
        camera.close()
    assert len(NumberedStorageRegistry(root).pending_reservations()) == 1
    with sqlite3.connect(root / "metadata.sqlite3") as db:
        assert db.execute("SELECT COUNT(*) FROM captures").fetchone()[0] == 0
