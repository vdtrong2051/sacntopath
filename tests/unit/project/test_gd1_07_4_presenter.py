"""07.4 UI presentation of real SQLite data; no Qt or camera required."""
from __future__ import annotations

from pathlib import Path
import sqlite3

import pytest

from scantopath.application.projects import ProjectWorkspaceService
from scantopath.metadata.store import MetadataStore
from scantopath.storage.numbered import NumberedStorageRegistry
from scantopath.ui.projects.presentation import ProjectLoadBundle, ProjectRow, project_rows


def _seed(root: Path) -> None:
    with MetadataStore(root) as store:
        store.create_project("project-original-long-id", "Hộp giảm tốc", "Đã kiểm thử")
        store.create_specimen("specimen-original-long-id", "project-original-long-id", "Trục vít")
        store.create_scan_session("session-original-long-id", "specimen-original-long-id", "Quét lần một")


def _bundle(root: Path) -> ProjectLoadBundle:
    service = ProjectWorkspaceService(root)
    return ProjectLoadBundle(service.info,
                             tuple(service.get_project_tree(p.project_id) for p in service.list_projects()))


def test_no_database_is_created_by_presentation_import(tmp_path):
    assert project_rows(()) == ()
    assert list(tmp_path.iterdir()) == []


def test_project_tree_v1_shows_unmapped_without_inventing_codes(tmp_path):
    _seed(tmp_path)
    before = (tmp_path / "metadata.sqlite3").read_bytes()
    bundle = _bundle(tmp_path)
    assert bundle.info.schema_version == 1
    tree = project_rows(bundle.trees)
    assert len(tree) == 1
    assert tree[0].title == "Chưa cấp mã · Hộp giảm tốc"
    assert tree[0].children[0].title == "Chưa cấp mã · Trục vít"
    assert tree[0].children[0].children[0].title == "Chưa cấp mã · Quét lần một"
    assert tree[0].selection.entity_id == "project-original-long-id"
    assert tree[0].children[0].selection.entity_type == "specimen"
    assert tree[0].children[0].children[0].selection.entity_type == "scan_session"
    assert (tmp_path / "metadata.sqlite3").read_bytes() == before
    assert not (tmp_path / "01_PROJECTS").exists()


def test_project_tree_v2_numbered_alias_without_modifying_raw(tmp_path):
    _seed(tmp_path)
    NumberedStorageRegistry.migrate_database(tmp_path)
    registry = NumberedStorageRegistry(tmp_path)
    registry.assign_all()  # explicit fixture preparation; UI loader never invokes this
    before = (tmp_path / "metadata.sqlite3").read_bytes()
    tree = project_rows(_bundle(tmp_path).trees)
    assert tree[0].title.startswith("P0001 ·")
    assert tree[0].children[0].title.startswith("S0001 ·")
    assert tree[0].children[0].children[0].title.startswith("T0001 ·")
    assert dict(tree[0].fields)["Mã"] == "P0001"
    assert dict(tree[0].fields)["Tên dự án"] == "Hộp giảm tốc"
    assert not (tmp_path / "01_PROJECTS").exists()
    assert before == (tmp_path / "metadata.sqlite3").read_bytes()


def test_v2_unallocated_still_unmapped_after_read(tmp_path):
    _seed(tmp_path)
    NumberedStorageRegistry.migrate_database(tmp_path)
    tree = project_rows(_bundle(tmp_path).trees)
    assert tree[0].title.startswith("Chưa cấp mã")
    with sqlite3.connect(tmp_path / "metadata.sqlite3") as db:
        assert db.execute("SELECT count(*) FROM storage_projects").fetchone()[0] == 0
        assert db.execute("SELECT count(*) FROM storage_counters").fetchone()[0] == 0


def test_presenter_rejects_invalid_input():
    for value in ([], None, ("invalid",)):
        with pytest.raises(TypeError):
            project_rows(value)


def test_presentation_fields_do_not_pretend_metric_validity(tmp_path):
    _seed(tmp_path)
    row = project_rows(_bundle(tmp_path).trees)[0]
    assert "Đã kiểm thử" in dict(row.fields)["Mô tả"]
    assert not any("độ chính xác" in value.lower() for value in dict(row.fields).values())


def test_capture_tree_uses_display_code_but_original_capture_id(tmp_path):
    from scantopath.storage.session_store import SessionStore
    from scantopath.acquisition.sources import SyntheticSource

    _seed(tmp_path)
    store = SessionStore(tmp_path)
    saved = store.commit(SyntheticSource().capture(), "session-original-long-id", "specimen-original-long-id")
    with MetadataStore(tmp_path) as metadata:
        registered = metadata.register_capture(saved)
    NumberedStorageRegistry.migrate_database(tmp_path)
    numbered = NumberedStorageRegistry(tmp_path)
    numbered.assign_all()
    before = {p.name: p.read_bytes() for p in saved.iterdir()}
    roots = project_rows(_bundle(tmp_path).trees)
    session = roots[0].children[0].children[0]
    cap = session.children[0]
    assert cap.title == "C0001 · Bản thu 01"
    assert cap.selection.entity_id == registered["capture_id"]
    assert cap.selection.entity_type == "capture"
    assert dict(cap.fields)["RAW"] == "Chưa kiểm tra RAW"
    assert dict(cap.fields)["Đường dẫn"].startswith("sessions/")
    assert {p.name: p.read_bytes() for p in saved.iterdir()} == before
