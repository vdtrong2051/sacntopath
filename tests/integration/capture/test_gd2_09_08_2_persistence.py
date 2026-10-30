"""09.08.2 real SQLite v2 + numbered RAW, ALL under pytest tmp_path.

No camera, GUI, actual operator dataset, Git or implicit migrations.
"""
from __future__ import annotations

import hashlib
import json
import sqlite3

import pytest

from scantopath.metadata.store import MetadataStore
from scantopath.storage.numbered import NumberedStorageRegistry
from scantopath.modules.capture.application.contracts import CaptureContext
from scantopath.modules.capture.application.capture_service import (
    CaptureCommitService, CaptureCommitError,
)
from scantopath.modules.capture.infrastructure.capture_writer import (
    NumberedCapturePersistenceAdapter,
)
from scantopath.modules.capture.application.replay import RawReplayService
from scantopath.modules.capture.infrastructure.raw_reader import RawReaderAdapter
from tests.support.raw_fixture import raw


@pytest.fixture
def store(tmp_path):
    with MetadataStore(tmp_path) as db:
        db.create_project("p1", "P1")
        db.create_specimen("s1", "p1", "S1")
        db.create_scan_session("t1", "s1", "T1")
        db.create_project("p2", "P2")
        db.create_specimen("s2", "p2", "S2")
        db.create_scan_session("t2", "s2", "T2")
    NumberedStorageRegistry.migrate_database(tmp_path)
    return tmp_path


def context(root, *, project="p1", specimen="s1", session="t1", capture_id=None):
    return CaptureContext(str(root), project, specimen, session, capture_id)


def commit(root, *, capture_id="cap-01", adapter=None):
    adapter = adapter or NumberedCapturePersistenceAdapter()
    packet = raw(session="t1", specimen="s1", capture_id=capture_id)
    return CaptureCommitService(adapter).commit(context(root), packet), packet


def replay(root, capture_id):
    return RawReplayService(RawReaderAdapter()).load(context(root, capture_id=capture_id))


def test_commit_numbered_v2_sqlite_replay_and_integrity(store):
    saved_id, packet = commit(store)
    assert saved_id == packet.metadata.capture_id
    registry = NumberedStorageRegistry(store)
    assert registry.pending_reservations() == ()
    location = registry.resolve_id("capture", saved_id, verify=True)
    assert location.layout_version == 2
    path = store / location.relative_path
    assert path.is_dir()
    assert (path / "COMMITTED").read_bytes() == b"1\n"
    manifest = json.loads((path / "manifest.json").read_text("utf-8"))
    for filename in ("color.mjpg", "depth.y16", "metadata.json"):
        assert hashlib.sha256((path / filename).read_bytes()).hexdigest() == manifest["files"][filename]["sha256"]
    with MetadataStore(store) as db:
        row = db.get_capture(saved_id)
        assert row["session_id"] == "t1"
        assert row["specimen_id"] == "s1"
        assert row["schema_version"] == 2
    assert replay(store, saved_id) == packet


def test_five_captures_distinct_numbered_paths_and_replay(store):
    registry = NumberedStorageRegistry(store)
    ids = []
    paths = []
    for i in range(5):
        cid, packet = commit(store, capture_id=f"cap-{i}")
        ids.append(cid)
        paths.append(registry.resolve_id("capture", cid, verify=True).relative_path)
        assert replay(store, cid) == packet
    assert len(set(ids)) == len(set(paths)) == 5
    assert registry.pending_reservations() == ()


def test_duplicate_capture_cannot_overwrite_registered_raw(store):
    commit(store)
    loc = NumberedStorageRegistry(store).resolve_id("capture", "cap-01", verify=True)
    path = store / loc.relative_path / "depth.y16"
    before = path.read_bytes()
    with pytest.raises(CaptureCommitError) as e:
        commit(store)
    assert e.value.code == "CAPTURE_RESERVE_REJECTED"
    assert path.read_bytes() == before


@pytest.mark.parametrize("wrong", [
    {"project": "p2"}, {"specimen": "s2"}, {"session": "t2"},
    {"session": "absent"},
])
def test_wrong_project_specimen_session_no_reservation(store, wrong):
    ctx = context(store, **wrong)
    with pytest.raises(CaptureCommitError) as e:
        CaptureCommitService(NumberedCapturePersistenceAdapter()).commit(
            ctx, raw(session=ctx.session_id, specimen=ctx.specimen_id, capture_id="bad")
        )
    assert e.value.code == "CAPTURE_CONTEXT_MISMATCH"
    assert NumberedStorageRegistry(store).pending_reservations() == ()


def test_closed_session_rejected_without_reservation(store):
    with MetadataStore(store) as db:
        db.close_scan_session("t1")
    with pytest.raises(CaptureCommitError) as e:
        commit(store)
    assert e.value.code == "SESSION_NOT_OPEN"
    assert NumberedStorageRegistry(store).pending_reservations() == ()


def test_nonexistent_root_does_not_initialize_any_database(tmp_path):
    root = tmp_path / "missing"
    with pytest.raises(CaptureCommitError) as e:
        commit(root)
    assert e.value.code == "STORE_NOT_OPEN"
    assert not root.exists()


def test_schema_v1_requires_explicit_migration(tmp_path):
    with MetadataStore(tmp_path) as db:
        db.create_project("p1", "P")
        db.create_specimen("s1", "p1", "S")
        db.create_scan_session("t1", "s1", "T")
    with pytest.raises(CaptureCommitError) as e:
        commit(tmp_path)
    assert e.value.code == "NUMBERED_SCHEMA_REQUIRED"


class FaultRegistry:
    """Proxy around a REAL numbered registry; inject faults at exact stage."""
    def __init__(self, root, stage):
        self.base = NumberedStorageRegistry(root)
        self.root = root
        self.stage = stage

    def __getattr__(self, name):
        return getattr(self.base, name)

    def write_reserved_capture(self, packet):
        if self.stage == "disk":
            raise OSError("simulated disk full")
        path = self.base.write_reserved_capture(packet)
        if self.stage == "tamper":
            file = path / "depth.y16"
            file.write_bytes(file.read_bytes()[:-1] + b"\x00")
        return path

    def register_reserved_capture(self, capture_id):
        if self.stage == "sqlite":
            raise sqlite3.OperationalError("simulated registration rollback")
        if self.stage == "session_closes":
            with MetadataStore(self.root) as db:
                db.close_scan_session("t1")
        return self.base.register_reserved_capture(capture_id)


def fault_adapter(stage):
    return NumberedCapturePersistenceAdapter(
        registry_factory=lambda root: FaultRegistry(root, stage)
    )


def test_disk_write_failure_preserves_reservation_no_registered_capture(store):
    with pytest.raises(CaptureCommitError) as e:
        commit(store, adapter=fault_adapter("disk"))
    assert e.value.code == "RAW_WRITE_FAILED"
    reservations = NumberedStorageRegistry(store).pending_reservations()
    assert len(reservations) == 1 and reservations[0].capture_id == "cap-01"
    with MetadataStore(store) as db:
        with pytest.raises(LookupError):
            db.get_capture("cap-01")
    with pytest.raises(CaptureCommitError) as recovered:
        NumberedCapturePersistenceAdapter().recover(context(store), "cap-01")
    assert recovered.value.code == "RAW_INTEGRITY_FAILED"


def test_sqlite_registration_failure_can_recover_exact_original_raw(store):
    with pytest.raises(CaptureCommitError) as e:
        commit(store, adapter=fault_adapter("sqlite"))
    assert e.value.code == "CAPTURE_REGISTRATION_FAILED"
    reservations = NumberedStorageRegistry(store).pending_reservations()
    assert len(reservations) == 1
    reserved_path = store / reservations[0].relative_path
    original = (reserved_path / "depth.y16").read_bytes()
    with pytest.raises(CaptureCommitError) as retry:
        commit(store)
    assert retry.value.code == "CAPTURE_RECOVERY_REQUIRED"
    assert (reserved_path / "depth.y16").read_bytes() == original
    assert NumberedCapturePersistenceAdapter().recover(context(store), "cap-01") == "cap-01"
    assert NumberedStorageRegistry(store).pending_reservations() == ()
    assert replay(store, "cap-01").depth_y16_le == original


def test_tamper_before_register_is_never_accepted(store):
    with pytest.raises(CaptureCommitError) as e:
        commit(store, adapter=fault_adapter("tamper"))
    assert e.value.code == "RAW_INTEGRITY_FAILED"
    assert len(NumberedStorageRegistry(store).pending_reservations()) == 1
    with pytest.raises(CaptureCommitError) as e2:
        NumberedCapturePersistenceAdapter().recover(context(store), "cap-01")
    assert e2.value.code == "RAW_INTEGRITY_FAILED"


def test_session_closed_after_raw_write_registration_rejected(store):
    with pytest.raises(CaptureCommitError) as e:
        commit(store, adapter=fault_adapter("session_closes"))
    assert e.value.code == "CAPTURE_REGISTRATION_FAILED"
    assert len(NumberedStorageRegistry(store).pending_reservations()) == 1
    with MetadataStore(store) as db:
        with pytest.raises(LookupError):
            db.get_capture("cap-01")


def test_recovery_requires_existing_pending_reservation(store):
    with pytest.raises(CaptureCommitError) as e:
        NumberedCapturePersistenceAdapter().recover(context(store), "cap-01")
    assert e.value.code == "CAPTURE_RESERVATION_NOT_FOUND"


def test_app_context_capture_id_mismatch_rejected_before_storage(store):
    packet = raw(session="t1", specimen="s1", capture_id="cap-01")
    with pytest.raises(CaptureCommitError) as e:
        CaptureCommitService(NumberedCapturePersistenceAdapter()).commit(
            context(store, capture_id="other"), packet
        )
    assert e.value.code == "CAPTURE_CONTEXT_MISMATCH"
    assert NumberedStorageRegistry(store).pending_reservations() == ()


def test_post_registration_replay_failure_is_not_false_success(store):
    class BrokenReplay:
        def load(self, _context):
            raise OSError("simulated replay failure")

    adapter = NumberedCapturePersistenceAdapter(replay_factory=lambda: BrokenReplay())
    with pytest.raises(CaptureCommitError) as e:
        commit(store, adapter=adapter)
    assert e.value.code == "REPLAY_VERIFICATION_FAILED"
    # The SQLite transaction may ALREADY have committed; do not roll it back
    # or claim success. Operator/09.08.3 must inspect this inconsistent state.
    with MetadataStore(store) as db:
        assert db.get_capture("cap-01")["capture_id"] == "cap-01"
    assert replay(store, "cap-01").metadata.capture_id == "cap-01"
