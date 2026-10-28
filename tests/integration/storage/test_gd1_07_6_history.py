"""07.6 headless acceptance: read-only Capture inspection, Run/Audit presentation."""
from __future__ import annotations

from dataclasses import FrozenInstanceError
from pathlib import Path

import pytest

from scantopath.application.projects import ProjectWorkspaceService
from scantopath.metadata.store import MetadataStore
from scantopath.storage.session_store import SessionStore
from scantopath.acquisition.sources import SyntheticSource
from scantopath.ui.projects.presentation import project_rows, ProjectLoadBundle


def setup_v1(root: Path, *, with_capture=True):
    with MetadataStore(root) as store:
        store.create_project("project-id", "Dự án thật")
        store.create_specimen("specimen-id", "project-id", "Mẫu")
        store.create_scan_session("session-id", "specimen-id", "Quét")
    if not with_capture:
        return None
    cap_path = SessionStore(root).commit(SyntheticSource().capture(), "session-id", "specimen-id")
    with MetadataStore(root) as store:
        cap = store.register_capture(cap_path)
    return cap


def test_run_tree_and_sqlite_timeline_are_real(tmp_path):
    cap = setup_v1(tmp_path)
    with MetadataStore(tmp_path) as store:
        store.create_processing_run(run_id="run-id", session_id="session-id", stage="filter",
                                    algorithm="demo-fixture-only", version="0", input_capture_ids=[cap["capture_id"]])
        events_before = store.list_events()
    service = ProjectWorkspaceService(tmp_path)
    trees = (service.get_project_tree("project-id"),)
    row = project_rows(trees)[0].children[0].children[0]
    assert len(row.children) == 2
    capture, run = row.children
    assert capture.selection.entity_type == "capture"
    assert run.selection.entity_type == "processing_run"
    assert run.selection.entity_id == "run-id"
    assert "filter" in run.title
    assert any(f[0] == "Đầu ra (tham chiếu)" and f[1] == "Chưa có" for f in run.fields)
    events = service.list_events(limit=100)
    assert len(events) == len(events_before)
    assert any(e.action == "run.created" for e in events)
    assert ProjectLoadBundle(service.info, trees, events).audit_events == events


def test_capture_legacy_v1_integrity_no_fake_checksum(tmp_path):
    cap = setup_v1(tmp_path)
    service = ProjectWorkspaceService(tmp_path)
    result = service.inspect_capture(cap["capture_id"])
    assert result.status == "verified"
    assert result.raw_schema_version == 1
    assert "không có SHA-256" in result.message
    with pytest.raises(FrozenInstanceError):
        result.status = "corrupt"
    assert service.get_capture(cap["capture_id"], verify_raw=False).storage.state == "legacy_unmapped"


def test_capture_missing_returns_missing_without_sqlite_write(tmp_path):
    cap = setup_v1(tmp_path)
    before = ProjectWorkspaceService(tmp_path).list_events()
    capture_path = tmp_path / cap["relative_path"]
    capture_path.rename(tmp_path / "removed-capture")
    result = ProjectWorkspaceService(tmp_path).inspect_capture(cap["capture_id"])
    assert result.status == "missing"
    assert ProjectWorkspaceService(tmp_path).list_events() == before


def test_v1_capture_corrupt_does_not_claim_verified(tmp_path):
    cap = setup_v1(tmp_path)
    capture_path = tmp_path / cap["relative_path"]
    (capture_path / "depth.npy").write_bytes(b"not-a-numpy-file")
    assert ProjectWorkspaceService(tmp_path).inspect_capture(cap["capture_id"]).status == "corrupt"


def test_unregistered_id_refused(tmp_path):
    setup_v1(tmp_path, with_capture=False)
    with pytest.raises(LookupError):
        ProjectWorkspaceService(tmp_path).inspect_capture("unregistered")


def test_no_data_no_fake_rows_and_v1_readonly(tmp_path):
    setup_v1(tmp_path, with_capture=False)
    service = ProjectWorkspaceService(tmp_path)
    assert service.info.schema_version == 1
    assert service.get_project_tree("project-id").specimens[0].sessions[0].captures == ()
    assert service.get_project_tree("project-id").specimens[0].sessions[0].processing_runs == ()
    assert project_rows((service.get_project_tree("project-id"),))[0].children[0].children[0].children == ()


def test_run_output_references_are_not_verified_files(tmp_path):
    cap = setup_v1(tmp_path)
    with MetadataStore(tmp_path) as store:
        store.create_processing_run(run_id="run-id", session_id="session-id", stage="fixture",
                                    algorithm="ref-only", version="1", input_capture_ids=[cap["capture_id"]])
        store.start_processing_run("run-id")
        store.finish_processing_run("run-id", state="succeeded", output_files=["nonexistent.ply"])
    tree = ProjectWorkspaceService(tmp_path).get_project_tree("project-id")
    run = project_rows((tree,))[0].children[0].children[0].children[1]
    assert ("Đầu ra (tham chiếu)", "nonexistent.ply") in run.fields
    assert not (tmp_path / "nonexistent.ply").exists()


def test_numbered_raw_v2_checks_sha256_without_rewriting(tmp_path):
    from scantopath.storage.numbered import NumberedStorageRegistry
    from tests.support.raw_fixture import raw
    setup_v1(tmp_path, with_capture=False)
    NumberedStorageRegistry.migrate_database(tmp_path)
    numbered = NumberedStorageRegistry(tmp_path)
    packet = raw(session="session-id", specimen="specimen-id", capture_id="cap-v2")
    numbered.reserve_capture("cap-v2", "session-id", "specimen-id")
    original = numbered.write_reserved_capture(packet)
    numbered.register_reserved_capture("cap-v2")
    service = ProjectWorkspaceService(tmp_path)
    assert service.inspect_capture("cap-v2").status == "verified"
    assert "SHA-256" in service.inspect_capture("cap-v2").message
    baseline = (original / "depth.y16").read_bytes()
    assert baseline
    assert (original / "depth.y16").read_bytes() == baseline
    (original / "depth.y16").write_bytes(b"tampered")
    assert service.inspect_capture("cap-v2").status == "corrupt"
    with MetadataStore(tmp_path) as store:
        assert store.get_capture("cap-v2")["relative_path"].startswith("01_PROJECTS/")


def test_public_code_run_when_assigned(tmp_path):
    from scantopath.storage.numbered import NumberedStorageRegistry
    cap = setup_v1(tmp_path)
    with MetadataStore(tmp_path) as store:
        store.create_processing_run(run_id="run-1", session_id="session-id", stage="check",
                                    algorithm="fixture", version="v1", input_capture_ids=[cap["capture_id"]])
    NumberedStorageRegistry.migrate_database(tmp_path)
    numbered = NumberedStorageRegistry(tmp_path)
    numbered.assign_all()
    tree = ProjectWorkspaceService(tmp_path).get_project_tree("project-id")
    row = project_rows((tree,))[0].children[0].children[0]
    assert row.children[1].title.startswith("R0001")
    assert row.children[0].title.startswith("C0001")
