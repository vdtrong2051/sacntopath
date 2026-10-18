"""PRE-05 offline SQLite/RAW-provenance tests; no camera, GPU or GUI required."""
from __future__ import annotations

import json
import subprocess
import sys

import numpy as np
import pytest
from sqlalchemy import text
from sqlalchemy.exc import IntegrityError

from scantopath.metadata.store import MetadataStore
from scantopath.storage.session_store import SessionStore
from scantopath.acquisition.sources import SyntheticSource
from scantopath.acquisition.raw_rgbd import RawRgbdCapture
from scantopath.domain.raw_rgbd import (
    RawDepthToColorExtrinsics, RawDeviceInfo, RawDistortion, RawIntrinsics,
    RawPixelEncoding, RawRgbdCaptureMetadataV2, RawStreamInfo,
)
from scantopath.domain.models import CaptureKind


def _raw(session="session-1", specimen="specimen-1", *, measured=False):
    # Fixture is not a decodable image; PRE-05 only tests data/provenance.
    jpeg = b"\xff\xd8fixture\xff\xd9"
    depth = np.array([[0, 1000, 2048], [30, 40, 50]], dtype="<u2").tobytes()
    zeros = (0.,) * 8
    return RawRgbdCapture(
        metadata=RawRgbdCaptureMetadataV2(
            session_id=session, specimen_id=specimen,
            kind=CaptureKind.ORBBEC if measured else CaptureKind.SYNTHETIC,
            measured=measured,
            device=RawDeviceInfo(name="SYNTHETIC_METADATA_FIXTURE"),
            color=RawStreamInfo(encoding=RawPixelEncoding.MJPEG, width=5, height=4,
                                frame_index=1, timestamp_us=100000, payload_size_bytes=len(jpeg)),
            depth=RawStreamInfo(encoding=RawPixelEncoding.Y16, width=3, height=2,
                                frame_index=2, timestamp_us=101000, payload_size_bytes=len(depth)),
            color_intrinsics=RawIntrinsics(width=5, height=4, fx=4., fy=4., cx=2., cy=2.),
            depth_intrinsics=RawIntrinsics(width=3, height=2, fx=3., fy=3., cx=1., cy=1.),
            color_distortion=RawDistortion(sdk_model=0, k1_k6_p1_p2=zeros),
            depth_distortion=RawDistortion(sdk_model=0, k1_k6_p1_p2=zeros),
            depth_to_color=RawDepthToColorExtrinsics(
                rotation=(1., 0., 0., 0., 1., 0., 0., 0., 1.),
                translation_mm=(-13.78, 0., 0.)
            ),
            depth_scale_m_per_unit=0.001,
        ), color_mjpeg=jpeg, depth_y16_le=depth,
    )


def _hierarchy(registry):
    registry.create_project("project-1", "Mechanical part")
    registry.create_specimen("specimen-1", "project-1", "Part A")
    registry.create_scan_session("session-1", "specimen-1", "Handheld scan")


def _registered(tmp_path, registry, *, measured=False):
    capture = _raw(measured=measured)
    path = SessionStore(tmp_path).commit_raw(capture)
    return capture, path, registry.register_capture(path)


def test_create_update_list_project_and_specimen(tmp_path):
    with MetadataStore(tmp_path) as reg:
        p = reg.create_project("project-1", "A")
        assert p["project_id"] == "project-1"
        assert "+00:00" in p["created_at"]
        assert reg.update_project("project-1", name="Updated")["name"] == "Updated"
        s = reg.create_specimen("specimen-1", "project-1", "Original")
        assert s["project_id"] == "project-1"
        assert reg.update_specimen("specimen-1", label="Updated")["label"] == "Updated"
        assert [x["project_id"] for x in reg.list_projects()] == ["project-1"]
        with pytest.raises(ValueError):
            reg.update_project("project-1")
        with pytest.raises(ValueError):
            reg.update_specimen("specimen-1")


def test_reopen_persistent_database_and_version(tmp_path):
    with MetadataStore(tmp_path) as reg:
        _hierarchy(reg)
    with MetadataStore(tmp_path) as reg:
        tree = reg.get_project_tree("project-1")
        assert tree["specimens"][0]["sessions"][0]["session_id"] == "session-1"
        with reg.engine.connect() as conn:
            assert conn.execute(text("PRAGMA user_version")).scalar_one() == 1
            assert conn.execute(text("PRAGMA foreign_keys")).scalar_one() == 1


def test_reject_invalid_ids_and_missing_parents(tmp_path):
    with MetadataStore(tmp_path) as reg:
        with pytest.raises(ValueError):
            reg.create_project("../oops", "Oops")
        with pytest.raises(ValueError):
            reg.create_project("p", " ")
        with pytest.raises(LookupError):
            reg.create_specimen("s", "unknown", "No parent")
        with pytest.raises(LookupError):
            reg.create_scan_session("scan", "unknown")
        assert reg.list_projects() == []
        assert reg.list_events() == []


def test_uniqueness_and_audit_rollback(tmp_path):
    with MetadataStore(tmp_path) as reg:
        reg.create_project("project-1", "One")
        with pytest.raises(ValueError):
            reg.create_project("project-1", "Two")
        assert len(reg.list_events()) == 1
        assert reg.get_project("project-1")["name"] == "One"
        with pytest.raises(LookupError):
            reg.get_project("does-not-exist")


def test_sqlite_enforces_foreign_keys(tmp_path):
    with MetadataStore(tmp_path) as reg:
        with pytest.raises(IntegrityError):
            with reg.engine.begin() as conn:
                conn.exec_driver_sql(
                    "INSERT INTO specimens(specimen_id,project_id,label,description,created_at,updated_at) "
                    "VALUES ('bad','missing','bad','','t','t')"
                )


def test_raw_v2_register_and_reopen_without_mutating_files(tmp_path):
    with MetadataStore(tmp_path) as reg:
        _hierarchy(reg)
        capture = _raw()
        raw_path = SessionStore(tmp_path).commit_raw(capture)
        hashes_before = {f.name: f.read_bytes() for f in raw_path.iterdir() if f.is_file()}
        info = reg.register_capture(raw_path)
        assert info["capture_id"] == capture.metadata.capture_id
        assert info["schema_version"] == 2 and info["measured"] is False
        assert info["relative_path"].startswith("sessions/session-1/captures/")
        assert {f.name: f.read_bytes() for f in raw_path.iterdir() if f.is_file()} == hashes_before
    with MetadataStore(tmp_path) as reg:
        assert reg.get_capture(capture.metadata.capture_id, verify_raw=True)["kind"] == "synthetic"
        assert len(reg.get_project_tree("project-1")["specimens"][0]["sessions"][0]["captures"]) == 1


def test_registered_raw_orbbec_provenance_is_not_accuracy_claim(tmp_path):
    with MetadataStore(tmp_path) as reg:
        _hierarchy(reg)
        capture, path, info = _registered(tmp_path, reg, measured=True)
        assert info["kind"] == "orbbec" and info["measured"] is True
        assert SessionStore(tmp_path).read_raw(path).metadata.camera_pose is None
        assert info["relative_path"] != str(path)  # DB stores relocatable relative link.


def test_reject_corrupt_raw_and_no_side_effects(tmp_path):
    with MetadataStore(tmp_path) as reg:
        _hierarchy(reg)
        capture = _raw()
        path = SessionStore(tmp_path).commit_raw(capture)
        (path / "depth.y16").write_bytes(b"corrupted")
        with pytest.raises(ValueError, match="length|checksum"):
            reg.register_capture(path)
        assert len(reg.list_events()) == 3  # project, specimen, session only.
        assert reg.get_project_tree("project-1")["specimens"][0]["sessions"][0]["captures"] == []


def test_reject_capture_wrong_specimen_session(tmp_path):
    with MetadataStore(tmp_path) as reg:
        _hierarchy(reg)
        capture = _raw(specimen="specimen-other")
        path = SessionStore(tmp_path).commit_raw(capture)
        with pytest.raises(ValueError, match="specimen ID"):
            reg.register_capture(path)


def test_reject_external_or_traversing_capture_paths(tmp_path):
    outside = tmp_path.parent / (tmp_path.name + "-elsewhere")
    with MetadataStore(tmp_path) as reg:
        _hierarchy(reg)
        path = SessionStore(outside).commit_raw(_raw())
        with pytest.raises(ValueError, match="belong"):
            reg.register_capture(path)
        with pytest.raises((ValueError, FileNotFoundError)):
            reg.register_capture(tmp_path / "sessions" / "../" / "session-1")


def test_reject_duplicate_capture_registration(tmp_path):
    with MetadataStore(tmp_path) as reg:
        _hierarchy(reg)
        capture, path, _ = _registered(tmp_path, reg)
        with pytest.raises(ValueError, match="already registered"):
            reg.register_capture(path)
        assert sum(e["action"] == "capture.registered" for e in reg.list_events()) == 1


def test_v1_synthetic_backwards_compatibility(tmp_path):
    with MetadataStore(tmp_path) as reg:
        _hierarchy(reg)
        old = SessionStore(tmp_path).commit(SyntheticSource().capture(), "session-1", "specimen-1")
        before = (old / "metadata.json").read_bytes()
        registered = reg.register_capture(old)
        assert registered["schema_version"] == 1
        assert registered["kind"] == "synthetic"
        assert (old / "metadata.json").read_bytes() == before
        assert reg.get_capture(registered["capture_id"], verify_raw=True)["schema_version"] == 1


def test_run_lineage_state_machine_and_persistence(tmp_path):
    with MetadataStore(tmp_path) as reg:
        _hierarchy(reg)
        capture, _, info = _registered(tmp_path, reg)
        run = reg.create_processing_run(
            run_id="run-1", session_id="session-1", stage="filtering",
            algorithm="mock-only", version="0.0.1",
            input_capture_ids=[info["capture_id"]], parameters={"voxel": 0.01, "dry_run": True},
        )
        assert run["state"] == "pending" and run["input_capture_ids"] == [info["capture_id"]]
        assert reg.start_processing_run("run-1")["state"] == "running"
        with pytest.raises(ValueError, match="pending"):
            reg.start_processing_run("run-1")
        done = reg.finish_processing_run("run-1", state="succeeded", output_files=["processed/mock.pcd"])
        assert done["finished_at"] and done["state"] == "succeeded"
        with pytest.raises(ValueError, match="running"):
            reg.finish_processing_run("run-1", state="failed")
    with MetadataStore(tmp_path) as reg:
        saved = reg.get_processing_run("run-1")
        assert saved["input_capture_ids"] == [info["capture_id"]]
        assert saved["output_files"] == ["processed/mock.pcd"]
        assert saved["parameters"]["voxel"] == 0.01
        assert saved["state"] == "succeeded"


def test_run_reject_cross_session_input_and_duplicate_inputs(tmp_path):
    with MetadataStore(tmp_path) as reg:
        _hierarchy(reg)
        c, _, info = _registered(tmp_path, reg)
        reg.create_scan_session("session-2", "specimen-1")
        kwargs = dict(run_id="run-1", session_id="session-2", stage="stage",
                      algorithm="no-op", version="1", input_capture_ids=[c.metadata.capture_id])
        with pytest.raises(ValueError, match="same session"):
            reg.create_processing_run(**kwargs)
        kwargs["session_id"] = "session-1"
        kwargs["input_capture_ids"] = [c.metadata.capture_id, c.metadata.capture_id]
        with pytest.raises(ValueError, match="Duplicate"):
            reg.create_processing_run(**kwargs)
        with pytest.raises(LookupError):
            reg.get_processing_run("run-1")


def test_run_reject_missing_inputs_invalid_params_and_states(tmp_path):
    with MetadataStore(tmp_path) as reg:
        _hierarchy(reg)
        base = dict(run_id="r1", session_id="session-1", stage="stage",
                    algorithm="mock", version="1")
        with pytest.raises(ValueError, match="at least one"):
            reg.create_processing_run(**base, input_capture_ids=[])
        with pytest.raises(LookupError, match="Capture"):
            reg.create_processing_run(**base, input_capture_ids=["notregistered"])
        c, _, _ = _registered(tmp_path, reg)
        with pytest.raises(ValueError, match="Parameters"):
            reg.create_processing_run(**base, input_capture_ids=[c.metadata.capture_id],
                                      parameters={"bad": float("nan")})
        reg.create_processing_run(**base, input_capture_ids=[c.metadata.capture_id])
        with pytest.raises(ValueError, match="running"):
            reg.finish_processing_run("r1", state="failed")
        assert reg.get_processing_run("r1")["state"] == "pending"
        reg.start_processing_run("r1")
        assert reg.finish_processing_run("r1", state="failed", error_message="synthetic failure")["error_message"] == "synthetic failure"


def test_closed_session_forbids_new_capture_registration(tmp_path):
    with MetadataStore(tmp_path) as reg:
        _hierarchy(reg)
        cap_path = SessionStore(tmp_path).commit_raw(_raw())
        assert reg.close_scan_session("session-1")["state"] == "closed"
        with pytest.raises(ValueError, match="closed"):
            reg.close_scan_session("session-1")
        with pytest.raises(ValueError, match="closed"):
            reg.register_capture(cap_path)


def test_event_log_persists_order_and_validates_limit(tmp_path):
    with MetadataStore(tmp_path) as reg:
        _hierarchy(reg)
        actions = [e["action"] for e in reg.list_events()]
        assert actions == ["session.created", "specimen.created", "project.created"]
        assert reg.list_events(limit=1)[0]["action"] == "session.created"
        with pytest.raises(ValueError):
            reg.list_events(limit=0)
    with MetadataStore(tmp_path) as reg:
        assert len(reg.list_events()) == 3


def test_database_refuses_unknown_schema(tmp_path):
    with MetadataStore(tmp_path) as reg:
        with reg.engine.begin() as conn:
            conn.exec_driver_sql("PRAGMA user_version=999")
    with pytest.raises(RuntimeError, match="Unsupported metadata schema"):
        MetadataStore(tmp_path)


def test_cli_separate_process_reopen(tmp_path):
    root = str(tmp_path / "data")
    command = [sys.executable, "-m", "scantopath.metadata.cli", "--root", root]
    def invoke(*args):
        proc = subprocess.run([*command, *args], capture_output=True, text=True)
        assert proc.returncode == 0, proc.stderr
        return json.loads(proc.stdout)
    assert invoke("create-project", "--id", "proj", "--name", "Example")["name"] == "Example"
    invoke("create-specimen", "--id", "spec", "--project", "proj", "--label", "Part")
    invoke("create-session", "--id", "scan", "--specimen", "spec")
    tree = invoke("tree", "--project", "proj")
    assert tree["specimens"][0]["sessions"][0]["session_id"] == "scan"
    assert len(invoke("events")) == 3


def test_no_automatic_raw_delete_and_sqlite_only_new_data(tmp_path):
    with MetadataStore(tmp_path) as reg:
        _hierarchy(reg)
        capture, path, info = _registered(tmp_path, reg)
        reg.close_scan_session("session-1")
        assert path.is_dir() and (path / "COMMITTED").is_file()
        assert reg.db_path.is_file()
        assert not any(reg.root.rglob("*.pcd"))
        assert reg.get_capture(capture.metadata.capture_id, verify_raw=True)["relative_path"]


def test_structured_runtime_log_is_durable_and_bounded(tmp_path):
    with MetadataStore(tmp_path) as reg:
        event = reg.record_event(level="ERROR", action="camera.timeout",
                                 entity_type="session", entity_id="handheld-001",
                                 details={"attempts": 3, "retryable": True})
        assert event["level"] == "ERROR" and event["event_id"] == 1
        for args in (
            dict(level="DEBUG", action="a", entity_type="session", entity_id="s"),
            dict(level="ERROR", action="bad action", entity_type="session", entity_id="s"),
            dict(level="ERROR", action="a", entity_type="session", entity_id="../bad"),
            dict(level="ERROR", action="a", entity_type="session", entity_id="s", details={"data": float("nan")}),
            dict(level="ERROR", action="a", entity_type="session", entity_id="s", details={"data": "x" * 5000}),
        ):
            with pytest.raises(ValueError):
                reg.record_event(**args)
    with MetadataStore(tmp_path) as reg:
        assert len(reg.list_events()) == 1
        assert reg.list_events()[0]["details"] == {"attempts": 3, "retryable": True}


def test_cli_register_existing_raw_and_create_run(tmp_path):
    root = str(tmp_path / "data")
    raw_path = SessionStore(root).commit_raw(_raw())
    command = [sys.executable, "-m", "scantopath.metadata.cli", "--root", root]
    def invoke(*args):
        proc = subprocess.run([*command, *args], capture_output=True, text=True)
        assert proc.returncode == 0, proc.stderr
        return json.loads(proc.stdout)
    invoke("create-project", "--id", "project-1", "--name", "P")
    invoke("create-specimen", "--id", "specimen-1", "--project", "project-1", "--label", "S")
    invoke("create-session", "--id", "session-1", "--specimen", "specimen-1")
    info = invoke("register-capture", "--path", str(raw_path))
    assert info["schema_version"] == 2
    assert invoke("show-capture", "--id", info["capture_id"], "--verify")["capture_id"] == info["capture_id"]
    run = invoke("create-run", "--id", "run-1", "--session", "session-1",
                 "--stage", "raw-validation", "--algorithm", "no-op",
                 "--version", "v1", "--input", info["capture_id"],
                 "--parameters", '{"dry_run":true}')
    assert run["state"] == "pending" and run["parameters"]["dry_run"] is True
    assert invoke("start-run", "--id", "run-1")["state"] == "running"
    assert invoke("finish-run", "--id", "run-1", "--state", "succeeded")["state"] == "succeeded"
    assert invoke("log-event", "--level", "WARNING", "--action", "app.notice",
                  "--entity-type", "session", "--entity-id", "session-1",
                  "--details", '{"reason":"synthetic"}')["level"] == "WARNING"
    tree = invoke("tree", "--project", "project-1")
    entry = tree["specimens"][0]["sessions"][0]
    assert len(entry["captures"]) == 1 and len(entry["processing_runs"]) == 1
