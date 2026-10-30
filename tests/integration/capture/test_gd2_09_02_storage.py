"""09.02 real SQLite/RAW fixtures in tmp_path; never accesses operator stores."""
from __future__ import annotations

import hashlib
import json
import sqlite3

import pytest

from scantopath.acquisition.sources import SyntheticSource
from scantopath.metadata.store import MetadataStore
from scantopath.storage.numbered import NumberedStorageRegistry
from scantopath.storage.session_store import SessionStore
from scantopath.modules.capture.application.contracts import CaptureContext
from scantopath.modules.capture.application.replay import RawReplayError, RawReplayService
from scantopath.modules.capture.infrastructure.raw_reader import RawReaderAdapter
from tests.support.raw_fixture import raw


def context(root, *, project="p1", specimen="s1", session="t1", capture_id="c1"):
    return CaptureContext(str(root), project, specimen, session, capture_id)


def replay(ctx):
    return RawReplayService(RawReaderAdapter()).load(ctx)


def db_seed(root):
    with MetadataStore(root) as db:
        db.create_project("p1", "Project")
        db.create_specimen("s1", "p1", "Specimen")
        db.create_scan_session("t1", "s1", "Scan")


def legacy_capture(root, *, capture_id="c1"):
    capture = raw(session="t1", specimen="s1", capture_id=capture_id)
    location = SessionStore(root).commit_raw(capture)
    with MetadataStore(root) as db:
        db.register_capture(location)
    return capture, location


@pytest.fixture
def legacy_store(tmp_path):
    db_seed(tmp_path)
    expected, path = legacy_capture(tmp_path)
    return tmp_path, expected, path


def test_legacy_layout_v2_replay_roundtrip(legacy_store):
    root, expected, _ = legacy_store
    observed = replay(context(root))
    assert observed == expected
    assert observed.color_mjpeg == expected.color_mjpeg
    assert observed.depth_y16_le == expected.depth_y16_le
    assert observed.metadata.camera_pose is None


def test_numbered_v2_replay_with_real_registry(tmp_path):
    db_seed(tmp_path)
    NumberedStorageRegistry.migrate_database(tmp_path)
    registry = NumberedStorageRegistry(tmp_path)
    packet = raw(session="t1", specimen="s1", capture_id="c1")
    registry.reserve_capture("c1", "t1", "s1")
    location = registry.write_reserved_capture(packet)
    registry.register_reserved_capture("c1")
    before = (location / "manifest.json").read_bytes()
    result = replay(context(tmp_path))
    assert result == packet
    assert (location / "manifest.json").read_bytes() == before


def test_numbered_mismatched_mapping_is_rejected(tmp_path, monkeypatch):
    from dataclasses import replace

    db_seed(tmp_path)
    NumberedStorageRegistry.migrate_database(tmp_path)

    registry = NumberedStorageRegistry(tmp_path)
    packet = raw(session="t1", specimen="s1", capture_id="c1")

    registry.reserve_capture("c1", "t1", "s1")
    registry.write_reserved_capture(packet)
    registry.register_reserved_capture("c1")

    bad_path = (
        "01_PROJECTS/P9999/01_SPECIMENS/S9999/"
        "01_SESSIONS/T9999/01_CAPTURES/C9999"
    )

    # 1. GĐ1 SQLite trigger must reject an illegal mapping update.
    with sqlite3.connect(tmp_path / "metadata.sqlite3") as db:
        original_path = db.execute(
            "SELECT relative_path FROM captures WHERE capture_id=?",
            ("c1",),
        ).fetchone()[0]

        with pytest.raises(
            sqlite3.IntegrityError,
            match="cannot move numbered capture",
        ):
            db.execute(
                "UPDATE captures SET relative_path=? WHERE capture_id=?",
                (bad_path, "c1"),
            )

        db.rollback()

        current_path = db.execute(
            "SELECT relative_path FROM captures WHERE capture_id=?",
            ("c1",),
        ).fetchone()[0]

        assert current_path == original_path

    # 2. Simulate an inconsistent mapping returned by the registry.
    # Do not disable SQLite triggers or corrupt the actual database.
    original_resolve = NumberedStorageRegistry.resolve_id

    def inconsistent_resolve(
        self,
        entity_type,
        internal_id,
        *,
        verify=False,
    ):
        location = original_resolve(
            self,
            entity_type,
            internal_id,
            verify=verify,
        )

        if entity_type == "capture" and internal_id == "c1":
            return replace(location, relative_path=bad_path)

        return location

    monkeypatch.setattr(
        NumberedStorageRegistry,
        "resolve_id",
        inconsistent_resolve,
    )

    # 3. RAW Replay must reject the inconsistent mapping.
    with pytest.raises(RawReplayError) as error:
        replay(context(tmp_path))

    assert error.value.code == "STORAGE_MAPPING_MISMATCH"


def test_unregistered_raw_is_never_replayed(tmp_path):
    db_seed(tmp_path)
    SessionStore(tmp_path).commit_raw(raw(session="t1", specimen="s1", capture_id="c1"))
    with pytest.raises(RawReplayError) as e:
        replay(context(tmp_path))
    assert e.value.code == "CAPTURE_NOT_REGISTERED"


def test_reserved_but_unregistered_numbered_raw_is_never_replayed(tmp_path):
    db_seed(tmp_path)
    NumberedStorageRegistry.migrate_database(tmp_path)
    registry = NumberedStorageRegistry(tmp_path)
    registry.reserve_capture("c1", "t1", "s1")
    registry.write_reserved_capture(raw(session="t1", specimen="s1", capture_id="c1"))
    with pytest.raises(RawReplayError) as e:
        replay(context(tmp_path))
    assert e.value.code == "CAPTURE_NOT_REGISTERED"


@pytest.mark.parametrize("change", [
    {"project": "missing"}, {"project": "p1", "specimen": "other"},
    {"session": "other"}, {"capture_id": "missing"},
])
def test_wrong_project_specimen_session_capture_rejected(legacy_store, change):
    root, _, _ = legacy_store
    with pytest.raises(RawReplayError) as e:
        replay(context(root, **change))
    assert e.value.code in ("CAPTURE_CONTEXT_MISMATCH", "CAPTURE_NOT_REGISTERED")


@pytest.mark.parametrize("file_name", ["COMMITTED", "color.mjpg", "depth.y16", "metadata.json"])
def test_missing_raw_file_rejected(legacy_store, file_name):
    root, _, path = legacy_store
    (path / file_name).unlink()
    with pytest.raises(RawReplayError) as e:
        replay(context(root))
    assert e.value.code == "RAW_INTEGRITY_FAILED"


@pytest.mark.parametrize("file_name", ["color.mjpg", "depth.y16", "metadata.json"])
def test_modified_raw_bytes_rejected(legacy_store, file_name):
    root, _, path = legacy_store
    file = path / file_name
    modified = bytearray(file.read_bytes())
    modified[-1] ^= 0x01
    file.write_bytes(modified)
    with pytest.raises(RawReplayError) as e:
        replay(context(root))
    assert e.value.code == "RAW_INTEGRITY_FAILED"


def test_bad_manifest_sha_rejected(legacy_store):
    root, _, path = legacy_store
    manifest = path / "manifest.json"
    obj = json.loads(manifest.read_text("utf-8"))
    obj["files"]["depth.y16"]["sha256"] = "0" * 64
    manifest.write_text(json.dumps(obj), encoding="utf-8")
    with pytest.raises(RawReplayError) as e:
        replay(context(root))
    assert e.value.code == "RAW_INTEGRITY_FAILED"


def test_metadata_specimen_mismatch_with_updated_hash_rejected(legacy_store):
    root, _, path = legacy_store
    file = path / "metadata.json"
    obj = json.loads(file.read_text("utf-8"))
    obj["specimen_id"] = "other"
    changed = json.dumps(obj, ensure_ascii=False).encode("utf-8")
    file.write_bytes(changed)
    manifest = path / "manifest.json"
    manifest_data = json.loads(manifest.read_text("utf-8"))
    manifest_data["files"]["metadata.json"] = {
        "size_bytes": len(changed), "sha256": hashlib.sha256(changed).hexdigest(),
    }
    manifest.write_text(json.dumps(manifest_data), encoding="utf-8")
    with pytest.raises(RawReplayError) as e:
        replay(context(root))
    assert e.value.code == "CAPTURE_CONTEXT_MISMATCH"


def test_v1_raw_rejected_as_unsupported(tmp_path):
    db_seed(tmp_path)
    path = SessionStore(tmp_path).commit(SyntheticSource().capture(), "t1", "s1")
    with MetadataStore(tmp_path) as db:
        row = db.register_capture(path)
    with pytest.raises(RawReplayError) as e:
        replay(context(tmp_path, capture_id=row["capture_id"]))
    assert e.value.code == "UNSUPPORTED_RAW_SCHEMA"


def test_missing_store_never_created(tmp_path):
    root = tmp_path / "absent"
    with pytest.raises(RawReplayError) as e:
        replay(context(root))
    assert e.value.code == "STORE_NOT_OPEN"
    assert not root.exists()


def test_existing_folder_without_database_is_not_initialized(tmp_path):
    with pytest.raises(RawReplayError) as e:
        replay(context(tmp_path))
    assert e.value.code == "STORE_NOT_OPEN"
    assert not (tmp_path / "metadata.sqlite3").exists()


def test_capture_replay_preserves_raw_bytes_and_sqlite_records(legacy_store):
    root, _, location = legacy_store
    before = {p.name: hashlib.sha256(p.read_bytes()).hexdigest() for p in location.iterdir()}
    with MetadataStore(root) as db:
        audit_before = db.list_events()
    with sqlite3.connect(root / "metadata.sqlite3") as db:
        captures_before = db.execute("SELECT COUNT(*) FROM captures").fetchone()[0]
    assert replay(context(root)) == replay(context(root))
    after = {p.name: hashlib.sha256(p.read_bytes()).hexdigest() for p in location.iterdir()}
    with MetadataStore(root) as db:
        assert db.list_events() == audit_before
    with sqlite3.connect(root / "metadata.sqlite3") as db:
        assert db.execute("SELECT COUNT(*) FROM captures").fetchone()[0] == captures_before
    assert before == after


def test_closed_session_still_allows_replay(legacy_store):
    root, expected, _ = legacy_store
    with MetadataStore(root) as db:
        db.close_scan_session("t1")
    assert replay(context(root)) == expected


def test_corrupted_registered_relative_path_cannot_escape_root(legacy_store):
    root, _, _ = legacy_store
    with sqlite3.connect(root / "metadata.sqlite3") as db:
        db.execute("UPDATE captures SET relative_path=? WHERE capture_id=?", ("../outside", "c1"))
    with pytest.raises(RawReplayError) as e:
        replay(context(root))
    assert e.value.code == "RAW_PATH_UNSAFE"
