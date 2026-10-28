"""PRE-06 GĐ0 acceptance regression: ALL inputs are synthetic and disposable.

Never loads Orbbec SDK or the user's actual `scantopath-data`.  The independent
Windows hardware acceptance is documented in docs/PRE_06_GD0_ACCEPTANCE.md.
"""

import hashlib
import sqlite3

import pytest

from scantopath.acquisition.raw_rgbd import RawRgbdCapture
from scantopath.acquisition.sources import SyntheticSource
from scantopath.domain.models import CaptureKind
from scantopath.domain.raw_rgbd import (
    RawDepthToColorExtrinsics, RawDeviceInfo, RawDistortion,
    RawIntrinsics, RawPixelEncoding, RawRgbdCaptureMetadataV2, RawStreamInfo,
)
from scantopath.metadata.store import MetadataStore
from scantopath.storage.session_store import SessionStore


def _raw(capture_id: str = "pre06-v2", session_id: str = "scan-1") -> RawRgbdCapture:
    mjpeg = b"\xff\xd8synthetic-contract-only\xff\xd9"
    depth = bytes((0, 0, 0xE8, 0x03, 0xFF, 0xFF, 0x2A, 0x00))
    zero = RawDistortion(sdk_model=0, k1_k6_p1_p2=(0.0,) * 8)
    meta = RawRgbdCaptureMetadataV2(
        capture_id=capture_id, session_id=session_id, specimen_id="part-1",
        kind=CaptureKind.SYNTHETIC, measured=False,
        device=RawDeviceInfo(name="PRE06_SYNTHETIC_FIXTURE"),
        color=RawStreamInfo(encoding=RawPixelEncoding.MJPEG, width=6,
                            height=3, frame_index=7, timestamp_us=101_000,
                            payload_size_bytes=len(mjpeg)),
        depth=RawStreamInfo(encoding=RawPixelEncoding.Y16, width=2,
                            height=2, frame_index=8, timestamp_us=102_000,
                            payload_size_bytes=len(depth)),
        color_intrinsics=RawIntrinsics(width=6, height=3, fx=5.0, fy=5.1, cx=3.0, cy=1.5),
        depth_intrinsics=RawIntrinsics(width=2, height=2, fx=2.0, fy=2.1, cx=1.0, cy=1.0),
        color_distortion=zero,
        depth_distortion=zero,
        depth_to_color=RawDepthToColorExtrinsics(
            rotation=(1.0, 0.0, 0.0, 0.0, 1.0, 0.0, 0.0, 0.0, 1.0),
            translation_mm=(-13.7, 0.0, 0.0),
        ),
        depth_scale_m_per_unit=0.001,
    )
    return RawRgbdCapture(metadata=meta, color_mjpeg=mjpeg, depth_y16_le=depth)


def _hierarchy(store: MetadataStore) -> None:
    store.create_project("project-1", "PRE06 project")
    store.create_specimen("part-1", "project-1", "Synthetic part")
    store.create_scan_session("scan-1", "part-1", "Synthetic session")


def _db_checks(path):
    with sqlite3.connect(path) as db:
        assert db.execute("PRAGMA integrity_check").fetchone()[0] == "ok"
        assert db.execute("PRAGMA foreign_key_check").fetchall() == []
        assert db.execute("PRAGMA user_version").fetchone()[0] == 1


def test_gd0_end_to_end_v1_v2_lineage_reopen_and_audit(tmp_path):
    """Two schemas coexist without RAW mutation; sessions/runs/audit persist."""
    store = SessionStore(tmp_path)
    raw = _raw()
    v2 = store.commit_raw(raw)
    v1 = store.commit(SyntheticSource().capture(), "scan-1", "part-1")
    before = {name: (v2 / name).read_bytes() for name in
              ("color.mjpg", "depth.y16", "metadata.json", "manifest.json", "COMMITTED")}
    with MetadataStore(tmp_path) as registry:
        _hierarchy(registry)
        assert registry.register_capture(v1)["schema_version"] == 1
        assert registry.register_capture(v2)["schema_version"] == 2
        assert registry.get_capture(raw.metadata.capture_id, verify_raw=True)["measured"] is False
        run = registry.create_processing_run(
            run_id="run-1", session_id="scan-1", stage="raw-integrity",
            algorithm="synthetic-check", version="pre06-test",
            input_capture_ids=[raw.metadata.capture_id],
            parameters={"dry_run": True},
        )
        assert run["state"] == "pending"
        assert registry.start_processing_run("run-1")["state"] == "running"
        assert registry.finish_processing_run("run-1", state="succeeded")["state"] == "succeeded"
        assert registry.close_scan_session("scan-1")["state"] == "closed"
        _db_checks(registry.db_path)
    with MetadataStore(tmp_path) as registry:
        tree = registry.get_project_tree("project-1")
        session = tree["specimens"][0]["sessions"][0]
        assert session["state"] == "closed" and len(session["captures"]) == 2
        assert session["processing_runs"][0]["state"] == "succeeded"
        assert session["processing_runs"][0]["input_capture_ids"] == [raw.metadata.capture_id]
        actions = [entry["action"] for entry in registry.list_events(limit=20)]
        for action in ("capture.registered", "run.created", "run.started",
                       "run.finished", "session.closed"):
            assert action in actions
        assert registry.get_capture(raw.metadata.capture_id, verify_raw=True)["schema_version"] == 2
    assert {name: (v2 / name).read_bytes() for name in before} == before
    assert store.read_raw(v2) == raw


def test_gd0_raw_commit_without_sqlite_can_be_registered_after_recovery(tmp_path):
    """Filesystem + SQLite are separate transactions; failed registration is retryable."""
    raw = _raw()
    store = SessionStore(tmp_path)
    path = store.commit_raw(raw)
    orig_digest = hashlib.sha256((path / "depth.y16").read_bytes()).hexdigest()
    with MetadataStore(tmp_path) as registry:
        with pytest.raises(LookupError, match="Session"):
            registry.register_capture(path)
        assert registry.list_events() == []
        _hierarchy(registry)
        registered = registry.register_capture(path)
        assert registered["capture_id"] == raw.metadata.capture_id
    assert (path / "COMMITTED").read_bytes() == b"1\n"
    assert hashlib.sha256((path / "depth.y16").read_bytes()).hexdigest() == orig_digest
    with MetadataStore(tmp_path) as registry:
        assert registry.get_capture(raw.metadata.capture_id, verify_raw=True)["capture_id"] == raw.metadata.capture_id


def test_gd0_corrupted_registered_raw_rejected_without_erasing_registry(tmp_path):
    raw = _raw()
    path = SessionStore(tmp_path).commit_raw(raw)
    with MetadataStore(tmp_path) as registry:
        _hierarchy(registry)
        registry.register_capture(path)
    color = path / "color.mjpg"
    intact = color.read_bytes()
    damaged = bytearray(intact)
    damaged[-1] ^= 1
    color.write_bytes(damaged)
    with MetadataStore(tmp_path) as registry:
        with pytest.raises(ValueError, match="checksum mismatch"):
            registry.get_capture(raw.metadata.capture_id, verify_raw=True)
        # Registry is still present and must not silently declare data healthy.
        assert registry.get_capture(raw.metadata.capture_id)["capture_id"] == raw.metadata.capture_id
    color.write_bytes(intact)
    with MetadataStore(tmp_path) as registry:
        assert registry.get_capture(raw.metadata.capture_id, verify_raw=True)["schema_version"] == 2


def test_gd0_partial_capture_is_invisible_and_unregistrable(tmp_path):
    store = SessionStore(tmp_path)
    partial_parent = tmp_path / "sessions" / "scan-1" / "captures"
    partial = partial_parent / ".interrupted.partial"
    partial.mkdir(parents=True)
    (partial / "metadata.json").write_text("{}", encoding="utf-8")
    assert store.list_committed("scan-1") == []
    with MetadataStore(tmp_path) as registry:
        _hierarchy(registry)
        with pytest.raises(ValueError, match="capture_id must be"):
            registry.register_capture(partial)
        assert registry.get_project_tree("project-1")["specimens"][0]["sessions"][0]["captures"] == []
    assert partial.is_dir()  # Do not destructively clean unknown interrupted RAW in PRE-06.


def test_gd0_metadata_transaction_rollback_keeps_raw_retryable(tmp_path, monkeypatch):
    import scantopath.metadata.store as metadata_module

    path = SessionStore(tmp_path).commit_raw(_raw())
    with MetadataStore(tmp_path) as registry:
        _hierarchy(registry)
        original_log = metadata_module._log

        def reject_audit(*args, **kwargs):
            if args[1] == "capture.registered":
                raise RuntimeError("synthetic audit-insert failure")
            return original_log(*args, **kwargs)

        with monkeypatch.context() as patch:
            patch.setattr(metadata_module, "_log", reject_audit)
            with pytest.raises(RuntimeError, match="synthetic audit-insert failure"):
                registry.register_capture(path)
        assert all(e["action"] != "capture.registered" for e in registry.list_events())
        assert registry.get_project_tree("project-1")["specimens"][0]["sessions"][0]["captures"] == []
        assert SessionStore(tmp_path).read_raw(path).metadata.capture_id == "pre06-v2"
        assert registry.register_capture(path)["capture_id"] == "pre06-v2"
    with MetadataStore(tmp_path) as registry:
        assert registry.get_capture("pre06-v2", verify_raw=True)["schema_version"] == 2
        assert sum(e["action"] == "capture.registered" for e in registry.list_events()) == 1


def test_gd0_sqlite_backup_reopens_without_modifying_source(tmp_path):
    src_root = tmp_path / "source"
    dst_root = tmp_path / "backup"
    with MetadataStore(src_root) as registry:
        registry.create_project("project-1", "PRE06 source")
        source_file = registry.db_path
        dst_root.mkdir()
        with sqlite3.connect(source_file) as original, sqlite3.connect(dst_root / "metadata.sqlite3") as copy:
            original.backup(copy)
    with MetadataStore(dst_root) as restored:
        assert restored.get_project("project-1")["name"] == "PRE06 source"
        assert restored.list_events()[0]["action"] == "project.created"
        _db_checks(restored.db_path)
    with MetadataStore(src_root) as registry:
        assert registry.get_project("project-1")["name"] == "PRE06 source"
