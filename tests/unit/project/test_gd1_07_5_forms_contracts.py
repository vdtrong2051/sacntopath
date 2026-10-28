"""07.5: Qt-free contracts and durable metadata mutations on temporary SQLite."""
from __future__ import annotations

import sqlite3

import pytest

from scantopath.ui.projects.forms_contract import (
    ProjectEditCommand, validate_description, validate_label,
)
from scantopath.metadata.store import MetadataStore
from scantopath.storage.numbered import NumberedStorageRegistry
from scantopath.application.projects.service import ProjectWorkspaceService


def seed(root, *, schema=2):
    with MetadataStore(root) as db:
        db.create_project("project-01", "Tên dự án")
        db.create_specimen("spec-01", "project-01", "Mẫu A")
        db.create_scan_session("session-01", "spec-01", "Quét 1")
    if schema == 2:
        NumberedStorageRegistry.migrate_database(root)
        NumberedStorageRegistry(root).assign_all()
    return ProjectWorkspaceService(root)


def test_label_trim_and_unicode():
    assert validate_label("  Hộp giảm tốc  ") == "Hộp giảm tốc"


@pytest.mark.parametrize("bad", ["", "  ", "a" * 257, None, 2])
def test_label_rejected(bad):
    with pytest.raises(ValueError):
        validate_label(bad)


def test_description_length_and_trim():
    assert validate_description(" Mô tả ") == "Mô tả"
    with pytest.raises(ValueError):
        validate_description("x" * 4097)
    with pytest.raises(ValueError):
        validate_description("invalid\0text")


@pytest.mark.parametrize("action,kwargs", [
    ("project.create", {}),
    ("specimen.create", {"parent_id": "p"}),
    ("specimen.update", {"target_id": "s", "parent_id": "p", "project_id": "p"}),
    ("session.create", {"parent_id": "s"}),
    ("session.update", {"target_id": "scan", "parent_id": "s"}),
])
def test_commands_are_immutable_and_trimmed(action, kwargs):
    cmd = ProjectEditCommand(action, name="  Đối tượng  ", description="" if action.startswith("session.") else "Mô tả", **kwargs)
    assert cmd.name == "Đối tượng"
    with pytest.raises(Exception):
        cmd.name = "changed"


@pytest.mark.parametrize("action,kwargs", [
    ("project.update", {"name": "V", "target_id": "../bad"}),
    ("specimen.create", {"name": "Mẫu"}),
    ("session.close", {"target_id": "s"}),
    ("session.create", {"name": "Scan", "parent_id": "s", "description": "not allowed"}),
    ("project.create", {"name": "OK", "parent_id": "foo"}),
    ("project.nope", {"name": "X"}),
])
def test_invalid_commands_rejected(action, kwargs):
    with pytest.raises(ValueError):
        ProjectEditCommand(action, **kwargs)


def test_session_rename_keeps_identity_state_and_code(tmp_path):
    service = seed(tmp_path)
    old = service.get_project_tree("project-01").specimens[0].sessions[0]
    renamed = service.update_session("spec-01", "session-01", label="  Quét lần hai  ")
    assert renamed.label == "Quét lần hai"
    assert renamed.session_id == old.session_id and renamed.storage == old.storage
    assert renamed.state == "open"
    with MetadataStore(tmp_path) as store:
        assert store.get_project_tree("project-01")["specimens"][0]["sessions"][0]["label"] == "Quét lần hai"
        assert any(x["action"] == "session.updated" for x in store.list_events())
    assert ProjectWorkspaceService(tmp_path).get_project_tree("project-01").specimens[0].sessions[0].label == "Quét lần hai"


def test_rename_closed_session_is_metadata_only(tmp_path):
    service = seed(tmp_path)
    service.close_session("spec-01", "session-01")
    result = service.update_session("spec-01", "session-01", label="Đã kiểm tra")
    assert result.state == "closed" and result.label == "Đã kiểm tra"
    with pytest.raises(ValueError):
        service.close_session("spec-01", "session-01")


def test_wrong_parent_never_mutates_session(tmp_path):
    service = seed(tmp_path)
    with MetadataStore(tmp_path) as db:
        db.create_project("p2", "Project 2")
        db.create_specimen("s2", "p2", "Sample 2")
    with pytest.raises(LookupError):
        service.update_session("s2", "session-01", label="wrong parent")
    assert service.get_project_tree("project-01").specimens[0].sessions[0].label == "Quét 1"


def test_v1_write_refused_without_side_effects(tmp_path):
    service = seed(tmp_path, schema=1)
    with pytest.raises(Exception):
        service.update_session("spec-01", "session-01", label="Not allowed")
    with MetadataStore(tmp_path) as db:
        assert db.get_project_tree("project-01")["specimens"][0]["sessions"][0]["label"] == "Quét 1"
    assert not (tmp_path / "01_PROJECTS").exists()


def test_invalid_label_does_not_audit(tmp_path):
    service = seed(tmp_path)
    with MetadataStore(tmp_path) as db:
        before = len(db.list_events())
    with pytest.raises(ValueError):
        service.update_session("spec-01", "session-01", label=" ")
    with MetadataStore(tmp_path) as db:
        assert len(db.list_events()) == before


def test_full_create_update_close_flow(tmp_path):
    seed(tmp_path)
    service = ProjectWorkspaceService(tmp_path)
    project = service.create_project("  Dự án mới  ")
    assert project.storage.public_code == "P0002"
    specimen = service.create_specimen(project.project_id, "Mẫu thử")
    assert specimen.storage.public_code == "S0001"
    session = service.create_session(specimen.specimen_id, "Phiên quét thử")
    assert session.storage.public_code == "T0001"
    session = service.update_session(specimen.specimen_id, session.session_id, label="Phiên sửa tên")
    assert session.storage.public_code == "T0001"
    service.update_project(project.project_id, name="Project updated")
    service.update_specimen(project.project_id, specimen.specimen_id, label="Sample updated")
    assert service.close_session(specimen.specimen_id, session.session_id).state == "closed"
    new_service = ProjectWorkspaceService(tmp_path)
    tree = new_service.get_project_tree(project.project_id)
    assert tree.project.name == "Project updated"
    assert tree.specimens[0].specimen.label == "Sample updated"
    assert tree.specimens[0].sessions[0].label == "Phiên sửa tên"
    assert tree.specimens[0].sessions[0].state == "closed"
    assert not (tmp_path / "01_PROJECTS").exists()  # Metadata does not fabricate RAW files.


def test_unknown_database_version_refused(tmp_path):
    seed(tmp_path)
    with sqlite3.connect(tmp_path / "metadata.sqlite3") as db:
        db.execute("PRAGMA user_version=300")
    with pytest.raises(RuntimeError):
        ProjectWorkspaceService(tmp_path)
