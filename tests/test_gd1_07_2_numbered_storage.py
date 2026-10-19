"""07.2 executable storage contract: no Qt, SDK, VTK or hardware needed."""
from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
import csv
import json
from pathlib import Path
import sqlite3

import numpy as np
import pytest

from scantopath.acquisition.raw_rgbd import RawRgbdCapture
from scantopath.domain.models import CaptureKind
from scantopath.domain.raw_rgbd import (
    RawDepthToColorExtrinsics, RawDeviceInfo, RawDistortion, RawIntrinsics,
    RawPixelEncoding, RawRgbdCaptureMetadataV2, RawStreamInfo,
)
from scantopath.metadata.store import MetadataStore
from scantopath.storage.numbered import NumberedStorageRegistry, _safe_path
from scantopath.storage.session_store import SessionStore


def raw(*, session="sess", specimen="spec", capture_id="fixed-raw-id") -> RawRgbdCapture:
    jpeg = b"\xff\xd8fixture\xff\xd9"
    depth = np.array([[0, 1, 99], [100, 900, 1200]], dtype="<u2").tobytes()
    zeros = (0.0,) * 8
    return RawRgbdCapture(
        metadata=RawRgbdCaptureMetadataV2(
            session_id=session, specimen_id=specimen, capture_id=capture_id,
            kind=CaptureKind.SYNTHETIC, measured=False,
            device=RawDeviceInfo(name="FIXTURE_NOT_REAL_CAMERA"),
            color=RawStreamInfo(encoding=RawPixelEncoding.MJPEG, width=5, height=4,
                                frame_index=1, timestamp_us=100000, payload_size_bytes=len(jpeg)),
            depth=RawStreamInfo(encoding=RawPixelEncoding.Y16, width=3, height=2,
                                frame_index=2, timestamp_us=101000, payload_size_bytes=len(depth)),
            color_intrinsics=RawIntrinsics(width=5, height=4, fx=4., fy=4., cx=2., cy=2.),
            depth_intrinsics=RawIntrinsics(width=3, height=2, fx=3., fy=3., cx=1., cy=1.),
            color_distortion=RawDistortion(sdk_model=0, k1_k6_p1_p2=zeros),
            depth_distortion=RawDistortion(sdk_model=0, k1_k6_p1_p2=zeros),
            depth_to_color=RawDepthToColorExtrinsics(
                rotation=(1.,0.,0.,0.,1.,0.,0.,0.,1.), translation_mm=(0.,0.,0.)),
            depth_scale_m_per_unit=0.001,
        ), color_mjpeg=jpeg, depth_y16_le=depth,
    )


def create_v1(root: Path) -> None:
    with MetadataStore(root) as store:
        store.create_project("prj", "Tên dự án tiếng Việt")
        store.create_specimen("spec", "prj", "Chi tiết")
        store.create_scan_session("sess", "spec", "Quét thử")


def open_v2(root: Path) -> NumberedStorageRegistry:
    return NumberedStorageRegistry(root)


def prepare(tmp_path: Path) -> NumberedStorageRegistry:
    create_v1(tmp_path)
    backup = NumberedStorageRegistry.migrate_database(tmp_path)
    assert backup.is_file()
    return open_v2(tmp_path)


def test_schema_requires_explicit_migration(tmp_path):
    with pytest.raises(FileNotFoundError):
        open_v2(tmp_path)
    with pytest.raises(FileNotFoundError):
        NumberedStorageRegistry.migrate_database(tmp_path)
    create_v1(tmp_path)
    with pytest.raises(RuntimeError, match="migration"):
        open_v2(tmp_path)
    assert (tmp_path / "metadata.sqlite3").exists()


def test_migration_backup_and_v1_restore(tmp_path):
    prepare(tmp_path)
    with sqlite3.connect(tmp_path / "metadata.sqlite3") as db:
        assert db.execute("PRAGMA user_version").fetchone()[0] == 2
        assert db.execute("PRAGMA foreign_key_check").fetchall() == []
    backups = list((tmp_path / "00_INDEX" / "backups").glob("*.sqlite3"))
    assert len(backups) == 1
    with sqlite3.connect(backups[0]) as db:
        assert db.execute("PRAGMA user_version").fetchone()[0] == 1
        assert db.execute("SELECT name FROM projects WHERE project_id='prj'").fetchone()[0] == "Tên dự án tiếng Việt"
    with MetadataStore(tmp_path) as store:
        assert store.get_project_tree("prj")["specimens"][0]["sessions"][0]["session_id"] == "sess"
    with pytest.raises(RuntimeError):
        NumberedStorageRegistry.migrate_database(tmp_path)


def test_assign_without_files_and_public_path_roundtrip(tmp_path):
    registry = prepare(tmp_path)
    session = registry.assign("session", "sess")
    assert session.public_path == "P0001/S0001/T0001"
    assert session.relative_path == "01_PROJECTS/P0001/01_SPECIMENS/S0001/01_SESSIONS/T0001"
    assert not session.exists and session.integrity_state == "not_materialized"
    assert registry.resolve_id("project", "prj").public_path == "P0001"
    assert registry.resolve_public_path("P0001/S0001/T0001").internal_id == "sess"
    assert registry.assign("session", "sess") == session
    with MetadataStore(tmp_path) as store:
        store.update_project("prj", name="Tên đã đổi")
    assert registry.resolve_id("session", "sess").relative_path == session.relative_path
    assert registry.assign_all() == {"project": 0, "specimen": 0, "session": 0, "capture": 0, "run": 0}


def test_legacy_capture_gets_code_but_raw_does_not_move(tmp_path):
    create_v1(tmp_path)
    raw_packet = raw()
    path = SessionStore(tmp_path).commit_raw(raw_packet)
    with MetadataStore(tmp_path) as store:
        store.register_capture(path)
    NumberedStorageRegistry.migrate_database(tmp_path)
    registry = open_v2(tmp_path)
    assert registry.assign_all()["capture"] == 1
    location = registry.resolve_public_path("P0001/S0001/T0001/C0001", verify=True)
    assert location.layout_version == 1 and location.integrity_state == "verified"
    assert location.relative_path == "sessions/sess/captures/fixed-raw-id"
    assert path.is_dir() and SessionStore(tmp_path).read_raw(path) == raw_packet
    with MetadataStore(tmp_path) as store:
        assert store.get_capture("fixed-raw-id", verify_raw=True)["relative_path"] == location.relative_path


def test_v2_reserve_write_register_roundtrip(tmp_path):
    registry = prepare(tmp_path)
    registry.assign_all()
    packet = raw()
    reservation = registry.reserve_capture(packet.metadata.capture_id, "sess", "spec")
    assert reservation.public_path == "P0001/S0001/T0001/C0001"
    assert reservation == registry.reserve_capture(packet.metadata.capture_id, "sess", "spec")
    assert not (tmp_path / reservation.relative_path).exists()
    saved = registry.write_reserved_capture(packet)
    assert saved == tmp_path / reservation.relative_path
    assert set(f.name for f in saved.iterdir()) == {"color.mjpg", "depth.y16", "metadata.json", "manifest.json", "COMMITTED"}
    assert json.loads((saved / "manifest.json").read_text())["capture_id"] == packet.metadata.capture_id
    assert json.loads((saved / "metadata.json").read_text())["capture_id"] == packet.metadata.capture_id
    with pytest.raises(FileExistsError):
        registry.write_reserved_capture(packet)
    result = registry.register_reserved_capture("fixed-raw-id")
    assert result.layout_version == 2 and result.integrity_state == "verified"
    assert result.public_path == reservation.public_path
    assert registry.resolve_public_path(reservation.public_path, verify=True) == result
    assert registry.pending_reservations() == ()
    assert SessionStore(tmp_path).read_raw_numbered(saved, expected_capture_id="fixed-raw-id", expected_session_id="sess") == packet
    with pytest.raises(ValueError):
        SessionStore(tmp_path).read_raw(saved)  # legacy reader must still reject numbered layout
    with MetadataStore(tmp_path) as store:
        assert store.get_capture("fixed-raw-id", verify_raw=True)["relative_path"] == reservation.relative_path


def test_bad_new_raw_checksum_never_marked_verified(tmp_path):
    registry = prepare(tmp_path)
    res = registry.reserve_capture("fixed-raw-id", "sess", "spec")
    path = registry.write_reserved_capture(raw())
    (path / "depth.y16").write_bytes(b"tampered")
    with pytest.raises(ValueError):
        registry.register_reserved_capture("fixed-raw-id")
    assert len(registry.pending_reservations()) == 1
    with MetadataStore(tmp_path) as store:
        assert store.get_project_tree("prj")["specimens"][0]["sessions"][0]["captures"] == []
    assert (tmp_path / res.relative_path).exists()


def test_registration_failure_preserves_orphan_and_id(tmp_path):
    registry = prepare(tmp_path)
    registry.reserve_capture("fixed-raw-id", "sess", "spec")
    path = registry.write_reserved_capture(raw())
    with MetadataStore(tmp_path) as store:
        store.close_scan_session("sess")
    with pytest.raises(ValueError):
        registry.register_reserved_capture("fixed-raw-id")
    assert path.is_dir() and len(registry.pending_reservations()) == 1
    with pytest.raises(ValueError):
        registry.reserve_capture("another-raw", "sess", "spec")


def test_path_rejects_escape_alias_and_symlinks(tmp_path):
    registry = prepare(tmp_path)
    for value in ("../outside", "A/../B", "C:\\Windows", "/etc/passwd", "a//b", "a/./b"):
        with pytest.raises(ValueError):
            _safe_path(registry.root, value, require_exists=False)
    with pytest.raises(ValueError):
        registry.resolve_public_path("C0001")
    with pytest.raises(ValueError):
        registry.resolve_public_path("P0001/S0001/T0001/C0001/extra")
    with pytest.raises(LookupError):
        registry.resolve_public_path("P0009")
    rootlink = tmp_path / "01_PROJECTS"
    outside = tmp_path.parent / (tmp_path.name + "_outer")
    outside.mkdir()
    try:
        rootlink.symlink_to(outside, target_is_directory=True)
    except (OSError, NotImplementedError):
        pytest.skip("Creating symlinks requires Windows privilege")
    with pytest.raises(ValueError):
        registry.reserve_capture("fixed-raw-id", "sess", "spec")


def test_parent_ownership_constraints_enforced_by_sqlite(tmp_path):
    registry = prepare(tmp_path)
    registry.assign_all()
    with MetadataStore(tmp_path) as store:
        store.create_project("second", "Two")
        store.create_specimen("second-spec", "second", "Other")
        store.create_specimen("unmapped-spec", "prj", "Not yet mapped")
    registry.assign("specimen", "second-spec")
    with sqlite3.connect(tmp_path / "metadata.sqlite3") as db:
        db.execute("PRAGMA foreign_keys=ON")
        with pytest.raises(sqlite3.IntegrityError):
            db.execute("INSERT INTO storage_specimens VALUES(?,?,?,?,?)",
                       ("unmapped-spec", "second", 11, "S0011", "oops"))
        with pytest.raises(sqlite3.IntegrityError):
            db.execute("UPDATE specimens SET project_id='second' WHERE specimen_id='spec'")
        with pytest.raises(sqlite3.IntegrityError):
            db.execute("UPDATE storage_specimens SET code='S9999' WHERE specimen_id='spec'")


def test_codes_scoped_per_parent_and_reopen(tmp_path):
    registry = prepare(tmp_path)
    with MetadataStore(tmp_path) as store:
        store.create_project("other", "Other")
        store.create_specimen("sp2", "other", "S")
        store.create_scan_session("ses2", "sp2")
    assert registry.assign("session", "sess").public_path == "P0001/S0001/T0001"
    assert registry.assign("session", "ses2").public_path == "P0002/S0001/T0001"
    assert open_v2(tmp_path).resolve_public_path("P0002/S0001/T0001").internal_id == "ses2"


def test_concurrent_allocations_unique_and_persistent(tmp_path):
    registry = prepare(tmp_path)
    with MetadataStore(tmp_path) as store:
        for i in range(12):
            store.create_project(f"p{i:02d}", f"Project {i}")
    with ThreadPoolExecutor(max_workers=6) as pool:
        results = list(pool.map(lambda i: registry.assign("project", f"p{i:02d}"), range(12)))
    assert len({x.public_path for x in results}) == 12
    assert len({x.internal_id for x in results}) == 12
    assert set(x.public_path for x in results) == set(
        x.public_path for x in (open_v2(tmp_path).resolve_id("project", f"p{i:02d}") for i in range(12)))


def test_run_code_metadata_only_and_catalog_csv(tmp_path):
    registry = prepare(tmp_path)
    legacy = SessionStore(tmp_path).commit_raw(raw())
    with MetadataStore(tmp_path) as store:
        store.register_capture(legacy)
        store.create_processing_run(run_id="run1", session_id="sess", stage="check",
                                    algorithm="fixture", version="v1", input_capture_ids=["fixed-raw-id"])
    registry.assign_all()
    run = registry.resolve_public_path("P0001/S0001/T0001/R0001")
    assert run.entity_type == "run" and run.integrity_state == "not_materialized"
    out = registry.export_catalog()
    with out.open(encoding="utf-8-sig", newline="") as stream:
        rows = list(csv.DictReader(stream))
    assert len(rows) == 5
    assert {x["entity_type"] for x in rows} == {"project", "specimen", "session", "capture", "run"}
    assert any(x["state"] == "legacy" for x in rows)
    assert not (tmp_path / "01_PROJECTS").exists()


def test_unknown_version_refused_and_unmodified(tmp_path):
    create_v1(tmp_path)
    with sqlite3.connect(tmp_path / "metadata.sqlite3") as db:
        db.execute("PRAGMA user_version=999")
    with pytest.raises(RuntimeError):
        NumberedStorageRegistry.migrate_database(tmp_path)
    with pytest.raises(RuntimeError):
        MetadataStore(tmp_path)
    assert not list((tmp_path / "00_INDEX" / "backups").glob("*.sqlite3"))


def test_old_synthetic_v1_reader_survives_numbering(tmp_path):
    from scantopath.acquisition.sources import SyntheticSource
    create_v1(tmp_path)
    store = SessionStore(tmp_path)
    path = store.commit(SyntheticSource().capture(), "sess", "spec")
    with MetadataStore(tmp_path) as reg:
        reg.register_capture(path)
    NumberedStorageRegistry.migrate_database(tmp_path)
    numbered = NumberedStorageRegistry(tmp_path)
    numbered.assign_all()
    location = numbered.resolve_public_path("P0001/S0001/T0001/C0001", verify=True)
    assert location.layout_version == 1 and location.integrity_state == "verified"
    with MetadataStore(tmp_path) as reg:
        assert reg.get_capture(location.internal_id, verify_raw=True)["schema_version"] == 1
    assert (path / "rgb.npy").is_file()


def test_numbered_code_grows_above_9999(tmp_path):
    numbered = prepare(tmp_path)
    numbered.assign("session", "sess")
    with sqlite3.connect(tmp_path / "metadata.sqlite3") as db:
        db.execute("INSERT INTO storage_counters VALUES('capture','sess',10000)")
    slot = numbered.reserve_capture("raw-10000", "sess", "spec")
    assert slot.public_path == "P0001/S0001/T0001/C10000"
    assert slot.relative_path.endswith("/C10000")


def test_parallel_reservations_cannot_duplicate_code(tmp_path):
    numbered = prepare(tmp_path)
    with ThreadPoolExecutor(max_workers=8) as pool:
        reservations = list(pool.map(lambda i: numbered.reserve_capture(f"cap-{i}", "sess", "spec"), range(20)))
    assert len({r.public_path for r in reservations}) == 20
    assert len(numbered.pending_reservations()) == 20
    assert numbered.reserve_capture("cap-1", "sess", "spec") == reservations[1]
    assert len(numbered.pending_reservations()) == 20


def test_cli_status_must_not_initialize_database(tmp_path):
    from scantopath.storage.numbered_cli import main
    assert main(["--root", str(tmp_path), "status"]) == 0
    assert not (tmp_path / "metadata.sqlite3").exists()
