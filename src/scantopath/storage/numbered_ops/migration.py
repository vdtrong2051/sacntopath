"""Numbered-storage operations grouped by responsibility.

All code assignment and registration transactions preserve BEGIN IMMEDIATE,
COMMIT/ROLLBACK, and RAW immutability from GĐ1-07.2–07.7.
"""
from __future__ import annotations
import csv
import json
from datetime import datetime, timezone
import os
from pathlib import Path
import shutil
import sqlite3
import tempfile
from scantopath.storage.numbered_contracts import (
    Kind, _TABLES, _PARENT, _CODE, _HIERARCHY, _now, _safe_id,
    _relative, _safe_path, StorageLocation, CaptureReservation)
from scantopath.storage.numbered_schema import DDL, TABLES
from scantopath.storage.session_store import SessionStore
from scantopath.acquisition.raw_rgbd import RawRgbdCapture


class _SchemaMigration:
    """Explicit v1→v2, backup-first only."""

    @staticmethod
    def migrate_database(root: str | Path) -> Path:
        """Explicit one-way schema migration with consistent SQLite backup.

        The operator must close all other application processes before migration.
        Failure before COMMIT preserves SQLite v1 and a separate backup.
        """
        location = Path(root).absolute()
        database = location / "metadata.sqlite3"
        if not database.is_file():
            raise FileNotFoundError("No metadata.sqlite3: refusing to create an empty store")
        backup_dir = location / "00_INDEX" / "backups"
        backup_dir.mkdir(parents=True, exist_ok=True)
        source = sqlite3.connect(database, timeout=10, isolation_level=None)
        source.execute("PRAGMA foreign_keys=ON")
        try:
            ver = source.execute("PRAGMA user_version").fetchone()[0]
            if ver != 1:
                raise RuntimeError(f"Expected SQLite schema 1 for migration, found {ver}")
            if source.execute("PRAGMA integrity_check").fetchone()[0] != "ok":
                raise RuntimeError("Database integrity check failed")
            if source.execute("PRAGMA foreign_key_check").fetchone() is not None:
                raise RuntimeError("Database has broken foreign keys")
            tables = {r[0] for r in source.execute("SELECT name FROM sqlite_master WHERE type='table'")}
            needed = {"projects", "specimens", "scan_sessions", "captures", "processing_runs",
                      "processing_run_inputs", "audit_events"}
            if not needed.issubset(tables):
                raise RuntimeError("Incomplete v1 schema: refusing migration")
            if set(TABLES) & tables:
                raise RuntimeError("Unexpected numbered tables in v1 database")
            size = source.execute("PRAGMA page_count").fetchone()[0] * source.execute("PRAGMA page_size").fetchone()[0]
            if shutil.disk_usage(location).free < max(size * 2, 1024 * 1024):
                raise OSError("Insufficient free disk space for backup and migration")
            # Exclusive creation (no silent clobber); copy of a live WAL database uses SQLite backup API.
            fd, name = tempfile.mkstemp(prefix=".metadata-before-v2-", suffix=".partial", dir=backup_dir)
            os.close(fd)
            temporary = Path(name)
            stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ")
            dest = backup_dir / f"metadata-before-v2-{stamp}.sqlite3"
            try:
                target = sqlite3.connect(temporary)
                try:
                    source.backup(target)
                    if target.execute("PRAGMA integrity_check").fetchone()[0] != "ok":
                        raise RuntimeError("Backup integrity check failed")
                finally:
                    target.close()
                temporary.replace(dest)
            finally:
                if temporary.exists():
                    temporary.unlink()
            # Lock readers/writers for DDL; no executescript() (which implicitly COMMITs).
            source.execute("BEGIN EXCLUSIVE")
            try:
                if source.execute("PRAGMA user_version").fetchone()[0] != 1:
                    raise RuntimeError("Database version changed during migration")
                buffer = ""
                for line in DDL.splitlines(keepends=True):
                    buffer += line
                    if sqlite3.complete_statement(buffer):
                        if buffer.strip():
                            source.execute(buffer)
                        buffer = ""
                if buffer.strip():
                    raise RuntimeError("Incomplete numbered schema DDL")
                source.execute("PRAGMA user_version=2")
                source.execute(
                    "INSERT INTO audit_events(occurred_at,action,level,entity_type,entity_id,details) "
                    "VALUES(?,?,?,?,?,?)",
                    (_now(), "storage.schema.migrated", "INFO", "project", "storage-root",
                     '{"from_version":1,"to_version":2}'),
                )
                source.execute("COMMIT")
            except BaseException:
                source.execute("ROLLBACK")
                raise
            return dest
        finally:
            source.close()
