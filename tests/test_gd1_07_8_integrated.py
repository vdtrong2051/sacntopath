"""GĐ1 07.8 — independent end-to-end acceptance on disposable SQLite/RAW.

No camera, no user datasets, no network, no implicit v1→v2 upgrade.  This file
exercises the public GĐ0/07.2/07.3/07.6/07.7 contracts rather than internal UI
fixtures. A successful test does not certify metrology or 3D reconstruction.
"""
from __future__ import annotations

import hashlib
from pathlib import Path
import sqlite3

import pytest

from scantopath.acquisition.sources import SyntheticSource
from scantopath.application.projects import ProjectWorkspaceService
from scantopath.metadata.store import MetadataStore
from scantopath.storage.legacy_migration import LegacyRawMigrator
from scantopath.storage.numbered import NumberedStorageRegistry
from scantopath.storage.session_store import SessionStore
from scantopath.ui.projects.presentation import project_rows


def _db(root: Path):
    return sqlite3.connect(root / "metadata.sqlite3")


def _seed_v1(root: Path, *, with_capture: bool = True):
    with MetadataStore(root) as db:
        db.create_project("p-078", "Dự án V1")
        db.create_specimen("s-078", "p-078", "Vật mẫu V1")
        db.create_scan_session("t-078", "s-078", "Phiên V1")
    if not with_capture:
        return None
    raw_dir = SessionStore(root).commit(SyntheticSource().capture(), "t-078", "s-078")
    with MetadataStore(root) as db:
        return db.register_capture(raw_dir)


def _seed_numbered(root: Path, *, with_capture: bool = True, with_run: bool = True):
    cap = _seed_v1(root, with_capture=with_capture)
    if cap is not None and with_run:
        with MetadataStore(root) as db:
            db.create_processing_run(
                run_id="r-078", session_id="t-078", stage="metadata-review",
                algorithm="synthetic-record-only", version="0", input_capture_ids=[cap["capture_id"]],
            )
    backup = NumberedStorageRegistry.migrate_database(root)
    assigned = NumberedStorageRegistry(root).assign_all()
    return cap, backup, assigned


def _pointers(root: Path, capture_id: str):
    with _db(root) as db:
        return db.execute(
            "SELECT c.relative_path, s.relative_path, s.layout_version "
            "FROM captures c JOIN storage_captures s ON c.capture_id=s.capture_id "
            "WHERE c.capture_id=?", (capture_id,),
        ).fetchone()


def _file_hashes(folder: Path):
    return {
        p.relative_to(folder).as_posix(): hashlib.sha256(p.read_bytes()).hexdigest()
        for p in folder.rglob("*") if p.is_file()
    }


def test_v1_can_be_opened_without_numbering_or_schema_migration(tmp_path):
    _seed_v1(tmp_path, with_capture=False)
    before = (tmp_path / "metadata.sqlite3").read_bytes()
    service = ProjectWorkspaceService(tmp_path)
    assert service.info.schema_version == 1
    assert not service.info.writable_with_codes
    assert len(service.list_projects()) == 1
    assert service.get_project_tree("p-078").project.storage.public_code is None
    assert (tmp_path / "metadata.sqlite3").read_bytes() == before
    assert not (tmp_path / "01_PROJECTS").exists()
    with _db(tmp_path) as db:
        assert db.execute("PRAGMA user_version").fetchone()[0] == 1
        assert db.execute("SELECT COUNT(*) FROM audit_events").fetchone()[0] == 3


def test_explicit_v2_and_project_forms_survive_service_reopen(tmp_path):
    _seed_numbered(tmp_path, with_capture=False)
    service = ProjectWorkspaceService(tmp_path)
    assert service.info.schema_version == 2
    assert service.info.writable_with_codes
    project = service.create_project("Hộp giảm tốc", "Thử nghiệm")
    specimen = service.create_specimen(project.project_id, "Trục vít")
    session = service.create_session(specimen.specimen_id, "Quét thử")
    codes = (project.storage.public_code, specimen.storage.public_code, session.storage.public_code)
    assert codes == ("P0002", "S0001", "T0001")
    service.update_project(project.project_id, name="Hộp giảm tốc V2")
    service.update_specimen(project.project_id, specimen.specimen_id, label="Trục vít mẫu A")
    service.update_session(specimen.specimen_id, session.session_id, label="Quét lần 01")
    service.close_session(specimen.specimen_id, session.session_id)
    reopened = ProjectWorkspaceService(tmp_path)
    node = reopened.get_project_tree(project.project_id)
    assert node.project.name == "Hộp giảm tốc V2"
    assert node.specimens[0].specimen.label == "Trục vít mẫu A"
    saved = node.specimens[0].sessions[0]
    assert saved.label == "Quét lần 01" and saved.state == "closed" and saved.closed_at
    assert (node.project.storage.public_code, node.specimens[0].specimen.storage.public_code,
            saved.storage.public_code) == codes
    assert saved.captures == () and saved.processing_runs == ()
    assert not (tmp_path / "01_PROJECTS").exists()  # metadata alone creates no fake RAW
    with _db(tmp_path) as db:
        assert db.execute("PRAGMA integrity_check").fetchone()[0] == "ok"
        assert db.execute("PRAGMA foreign_key_check").fetchall() == []


def test_capture_run_audit_and_presenter_are_real_readonly_dtos(tmp_path):
    cap, _, _ = _seed_numbered(tmp_path)
    svc = ProjectWorkspaceService(tmp_path)
    events_before = svc.list_events()
    tree = svc.get_project_tree("p-078")
    session = tree.specimens[0].sessions[0]
    assert len(session.captures) == 1 and len(session.processing_runs) == 1
    assert session.captures[0].storage.public_code == "C0001"
    assert session.processing_runs[0].storage.public_code == "R0001"
    assert session.processing_runs[0].state == "pending"
    assert session.processing_runs[0].output_files == ()
    rows = project_rows((tree,))
    titles = [r.title for r in rows[0].children[0].children[0].children]
    assert any(t.startswith("C0001") for t in titles)
    assert any(t.startswith("R0001") for t in titles)
    assert any(e.action == "run.created" for e in events_before)
    assert svc.inspect_capture(cap["capture_id"]).status == "verified"
    assert "không có SHA-256" in svc.inspect_capture(cap["capture_id"]).message
    assert ProjectWorkspaceService(tmp_path).list_events() == events_before


def test_full_legacy_roundtrip_preserves_hashes_and_sqlite_integrity(tmp_path):
    cap, backup, _ = _seed_numbered(tmp_path)
    assert Path(backup).is_file()
    migrator = LegacyRawMigrator(tmp_path)
    before_events = len(ProjectWorkspaceService(tmp_path).list_events())
    original = _pointers(tmp_path, cap["capture_id"])
    assert original[0] == original[1] and original[0].startswith("sessions/") and original[2] == 1
    original_bytes = _file_hashes(tmp_path / original[0])
    plan = migrator.plan()
    assert len(plan) == 1 and plan[0].target.endswith("C0001")
    assert _pointers(tmp_path, cap["capture_id"]) == original
    assert len(ProjectWorkspaceService(tmp_path).list_events()) == before_events
    assert not (tmp_path / plan[0].target).exists()
    applied = migrator.apply()
    assert applied["status"] == "applied" and applied["count"] == 1
    assert applied["legacy_retained"]
    target = tmp_path / plan[0].target
    assert _file_hashes(target) == original_bytes == _file_hashes(tmp_path / original[0])
    assert _pointers(tmp_path, cap["capture_id"]) == (plan[0].target, plan[0].target, 2)
    assert ProjectWorkspaceService(tmp_path).inspect_capture(cap["capture_id"]).status == "verified"
    assert migrator.plan() == ()
    rolled = migrator.rollback(applied["migration_id"])
    assert rolled["status"] == "rolled_back" and rolled["restored"] == 1
    assert rolled["numbered_copies_retained"] is True
    assert _pointers(tmp_path, cap["capture_id"]) == original
    assert _file_hashes(target) == original_bytes == _file_hashes(tmp_path / original[0])
    assert ProjectWorkspaceService(tmp_path).inspect_capture(cap["capture_id"]).status == "verified"
    with _db(tmp_path) as db:
        assert db.execute("PRAGMA integrity_check").fetchone()[0] == "ok"
        assert db.execute("PRAGMA foreign_key_check").fetchall() == []
        assert db.execute("SELECT COUNT(*) FROM audit_events WHERE action='storage.raw.migrated'").fetchone()[0] == 1
        assert db.execute("SELECT COUNT(*) FROM audit_events WHERE action='storage.raw.rolled_back'").fetchone()[0] == 1


def test_dry_run_after_rollback_refuses_retained_numbered_copy(tmp_path):
    """07.7 intentional safety behavior: collision != failed rollback."""
    cap, _, _ = _seed_numbered(tmp_path, with_run=False)
    migrator = LegacyRawMigrator(tmp_path)
    before = _pointers(tmp_path, cap["capture_id"])
    result = migrator.apply()
    migrator.rollback(result["migration_id"])
    with pytest.raises(FileExistsError, match="already exists"):
        migrator.plan()
    assert _pointers(tmp_path, cap["capture_id"]) == before
    assert ProjectWorkspaceService(tmp_path).inspect_capture(cap["capture_id"]).status == "verified"


def test_missing_raw_and_corruption_never_masquerade_as_verified(tmp_path):
    cap, _, _ = _seed_numbered(tmp_path, with_run=False)
    service = ProjectWorkspaceService(tmp_path)
    events = service.list_events()
    raw_dir = tmp_path / cap["relative_path"]
    (raw_dir / "depth.npy").write_bytes(b"damaged")
    assert service.inspect_capture(cap["capture_id"]).status == "corrupt"
    assert service.list_events() == events
    (raw_dir / "depth.npy").unlink()
    assert service.inspect_capture(cap["capture_id"]).status in ("missing", "corrupt")
    assert service.list_events() == events
    assert _pointers(tmp_path, cap["capture_id"])[2] == 1


def test_absent_database_does_not_create_files(tmp_path):
    root = tmp_path / "never-created"
    with pytest.raises(Exception):
        ProjectWorkspaceService(root)
    assert not root.exists()


def test_empty_v2_store_has_no_fake_objects(tmp_path):
    with MetadataStore(tmp_path):
        pass
    NumberedStorageRegistry.migrate_database(tmp_path)
    svc = ProjectWorkspaceService(tmp_path)
    assert svc.list_projects() == ()
    assert [event.action for event in svc.list_events()] == ["storage.schema.migrated"]
    assert not (tmp_path / "01_PROJECTS").exists()


def test_numbered_raw_v2_hash_verification_and_tamper_without_audit(tmp_path):
    """End-to-end SHA-256 verification of data created only in a temp test root."""
    from test_gd1_07_2_numbered_storage import raw
    _seed_v1(tmp_path, with_capture=False)
    NumberedStorageRegistry.migrate_database(tmp_path)
    numbered = NumberedStorageRegistry(tmp_path)
    numbered.assign_all()
    cid = "cap-078-v2"
    numbered.reserve_capture(cid, "t-078", "s-078")
    folder = numbered.write_reserved_capture(raw(session="t-078", specimen="s-078", capture_id=cid))
    numbered.register_reserved_capture(cid)
    service = ProjectWorkspaceService(tmp_path)
    events_before = service.list_events()
    ok = service.inspect_capture(cid)
    assert ok.status == "verified" and "SHA-256" in ok.message
    assert service.get_project_tree("p-078").specimens[0].sessions[0].captures[0].storage.public_code == "C0001"
    (folder / "depth.y16").write_bytes(b"tampered")
    assert service.inspect_capture(cid).status == "corrupt"
    assert ProjectWorkspaceService(tmp_path).list_events() == events_before
