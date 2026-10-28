"""Fixture SQLite/RAW dùng chung từ 07.8, chỉ tạo dữ liệu trong tmp_path test."""
from __future__ import annotations
from pathlib import Path
from scantopath.acquisition.sources import SyntheticSource
from scantopath.metadata.store import MetadataStore
from scantopath.storage.numbered import NumberedStorageRegistry
from scantopath.storage.session_store import SessionStore


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
