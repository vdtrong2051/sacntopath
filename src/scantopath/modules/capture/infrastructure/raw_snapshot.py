"""UXH-01.1: read-only source RAW/SQLite Capture snapshot adapter.

The source Store must never be created/updated here; only a disposable copy
is written. The replay reader subsequently verifies RAW manifest checksums.
"""
from __future__ import annotations

from dataclasses import replace
from hashlib import sha256
from pathlib import Path
import sqlite3

from scantopath.application.contracts.preview import GeometryPreviewError
from scantopath.modules.capture.application.contracts import CaptureContext


def snapshot_capture(context: CaptureContext, destination: Path) -> CaptureContext:
    """Copy one registered Capture into an isolated SQLite/RAW snapshot."""
    if not isinstance(context, CaptureContext) or not context.capture_id:
        raise GeometryPreviewError("CAPTURE_ID_REQUIRED")
    source = Path(context.store_root).absolute()
    if (not source.is_dir() or source.is_symlink() or
            source.resolve(strict=True) != source):
        raise GeometryPreviewError("STORE_NOT_OPEN")
    db_path = source / "metadata.sqlite3"
    if not db_path.is_file() or db_path.is_symlink():
        raise GeometryPreviewError("STORE_NOT_OPEN")
    destination = Path(destination)
    if destination.exists():
        raise GeometryPreviewError("SNAPSHOT_DESTINATION_EXISTS")
    destination.mkdir(parents=True)
    db_hash_before = sha256(db_path.read_bytes()).digest()
    conn = sqlite3.connect(db_path.as_uri() + "?mode=ro", uri=True)
    try:
        conn.execute("PRAGMA query_only=ON")
        row = conn.execute(
            "SELECT relative_path, schema_version, session_id, specimen_id "
            "FROM captures WHERE capture_id=?", (context.capture_id,),
        ).fetchone()
        if (row is None or row[1:] != (2, context.session_id, context.specimen_id)):
            raise GeometryPreviewError("CAPTURE_CONTEXT_MISMATCH")
        relative = row[0]
        parts = relative.split("/") if isinstance(relative, str) else []
        if (not 1 <= len(parts) <= 8 or "\\" in relative or
                any(p in ("", ".", "..") for p in parts) or
                (len(parts) == 8 and (parts[0] != "01_PROJECTS" or parts[6] != "01_CAPTURES")) or
                (len(parts) == 4 and (parts[0] != "sessions" or parts[2] != "captures")) or
                len(parts) not in (4, 8)):
            raise GeometryPreviewError("RAW_PATH_UNSAFE")
        src_dir = source.joinpath(*parts)
        if (not src_dir.is_dir() or src_dir.is_symlink() or
                not src_dir.resolve(strict=True).is_relative_to(source)):
            raise GeometryPreviewError("RAW_PATH_UNSAFE")
        target_db = sqlite3.connect(destination / "metadata.sqlite3")
        try:
            conn.backup(target_db)
        finally:
            target_db.close()
    finally:
        conn.close()
    dst_dir = destination.joinpath(*parts)
    dst_dir.mkdir(parents=True, exist_ok=True)
    for filename in ("color.mjpg", "depth.y16", "metadata.json", "manifest.json", "COMMITTED"):
        source_file = src_dir / filename
        if not source_file.is_file() or source_file.is_symlink():
            raise GeometryPreviewError("RAW_MISSING")
        data = source_file.read_bytes()
        digest = sha256(data).digest()
        (dst_dir / filename).write_bytes(data)
        if (sha256(source_file.read_bytes()).digest() != digest or
                sha256((dst_dir / filename).read_bytes()).digest() != digest):
            raise GeometryPreviewError("RAW_CHANGED_DURING_SNAPSHOT")
    if sha256(db_path.read_bytes()).digest() != db_hash_before:
        raise GeometryPreviewError("SQLITE_CHANGED_DURING_SNAPSHOT")
    return replace(context, store_root=str(destination))
