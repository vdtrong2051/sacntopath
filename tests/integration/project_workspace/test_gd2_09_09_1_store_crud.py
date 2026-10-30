"""09.09.1 real SQLite v2 and safe CRUD; always in pytest tmp_path."""
from __future__ import annotations

from pathlib import Path
import sqlite3
import pytest

from scantopath.modules.project_workspace.infrastructure.store_bootstrap import initialize_empty_data_workspace
from scantopath.modules.project_workspace.application.service import ProjectWorkspaceService
from scantopath.metadata.store import MetadataStore
from scantopath.storage.numbered import NumberedStorageRegistry


def new_root(tmp_path: Path) -> Path:
    return tmp_path / "scantopath-data"


def test_explicit_bootstrap_v2_and_reopen_idempotently(tmp_path):
    root = new_root(tmp_path)
    assert not root.exists()
    assert initialize_empty_data_workspace(root) == root
    with sqlite3.connect(root / "metadata.sqlite3") as db:
        assert db.execute("PRAGMA user_version").fetchone()[0] == 2
    before = (root / "metadata.sqlite3").stat().st_size
    assert initialize_empty_data_workspace(root) == root
    assert (root / "metadata.sqlite3").stat().st_size == before
    assert list(root.glob("00_INDEX/backups/*.sqlite3"))  # v1->v2 backup


def test_bootstrap_rejects_nonempty_or_existing_v1(tmp_path):
    root = new_root(tmp_path)
    root.mkdir()
    (root / "operator_notes.txt").write_text("keep")
    with pytest.raises(ValueError, match="STORE_DIRECTORY_NOT_EMPTY"):
        initialize_empty_data_workspace(root)
    assert (root / "operator_notes.txt").read_text() == "keep"
    (root / "operator_notes.txt").unlink()
    with MetadataStore(root):
        pass
    with pytest.raises(RuntimeError):
        initialize_empty_data_workspace(root)  # Never auto-migrate an existing v1 database


def test_project_specimen_session_create_update_read_close_delete(tmp_path):
    root = initialize_empty_data_workspace(new_root(tmp_path))
    svc = ProjectWorkspaceService(root)
    project = svc.create_project("Demo 09.09.1")
    pid = project.project_id
    svc.update_project(pid, name="Demo updated", description="Test CRUD")
    specimen = svc.create_specimen(pid, "Target A")
    sid = specimen.specimen_id
    svc.update_specimen(pid, sid, label="Target updated", description="No RAW")
    session = svc.create_session(sid, "First session")
    tid = session.session_id
    svc.update_session(sid, tid, label="Renamed session")
    tree = svc.get_project_tree(pid)
    assert tree.project.name == "Demo updated"
    assert tree.specimens[0].sessions[0].label == "Renamed session"
    assert svc.close_session(sid, tid).state == "closed"
    assert svc.delete_empty_entity("session", tid, sid) == tid
    assert svc.delete_empty_entity("specimen", sid, pid) == sid
    assert svc.delete_empty_entity("project", pid) == pid
    assert svc.list_projects() == ()


def test_deletion_rejected_with_child_or_pending_raw_reservation(tmp_path):
    root = initialize_empty_data_workspace(new_root(tmp_path))
    svc = ProjectWorkspaceService(root)
    pid = svc.create_project("Protect").project_id
    sid = svc.create_specimen(pid, "Protect specimen").specimen_id
    tid = svc.create_session(sid, "Open").session_id
    with pytest.raises(ValueError, match="ENTITY_HAS_CHILDREN"):
        svc.delete_empty_entity("project", pid)
    with pytest.raises(ValueError, match="ENTITY_HAS_CHILDREN"):
        svc.delete_empty_entity("specimen", sid, pid)
    NumberedStorageRegistry(root).reserve_capture("raw-pending", tid, sid)
    with pytest.raises(ValueError, match="ENTITY_HAS_CHILDREN"):
        svc.delete_empty_entity("session", tid, sid)
    assert len(NumberedStorageRegistry(root).pending_reservations()) == 1
    assert svc.get_project_tree(pid).specimens[0].sessions[0].session_id == tid


def test_deletion_rejects_wrong_parent_and_materialized_data(tmp_path):
    root = initialize_empty_data_workspace(new_root(tmp_path))
    svc = ProjectWorkspaceService(root)
    pid = svc.create_project("Preserve physical").project_id
    sid = svc.create_specimen(pid, "Object").specimen_id
    with pytest.raises(ValueError, match="ENTITY_PARENT_MISMATCH"):
        svc.delete_empty_entity("specimen", sid, "other-project")
    relative = NumberedStorageRegistry(root).resolve_id("specimen", sid).relative_path
    (root / relative).mkdir(parents=True)
    with pytest.raises(ValueError, match="ENTITY_HAS_MATERIALIZED_FILES"):
        svc.delete_empty_entity("specimen", sid, pid)
    assert (root / relative).exists()


def test_project_numbers_not_reused_after_empty_delete(tmp_path):
    root = initialize_empty_data_workspace(new_root(tmp_path))
    svc = ProjectWorkspaceService(root)
    old = svc.create_project("Old")
    svc.delete_empty_entity("project", old.project_id)
    newer = svc.create_project("New")
    assert old.storage.public_code != newer.storage.public_code
