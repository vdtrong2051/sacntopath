"""Delete EMPTY project hierarchy entities only; never delete captures or RAW.

The numbered mapping and metadata row disappear in one SQLite transaction.
Counters are retained so public codes are never reused. Physical directories,
if any exist, are NEVER removed by this operation.
"""
from __future__ import annotations

from pathlib import Path
import re


def delete_empty_numbered(registry, entity_type: str, identity: str, parent_id: str | None = None) -> str:
    if entity_type not in ("project", "specimen", "session"):
        raise ValueError("UNSUPPORTED_DELETE_KIND")
    if not isinstance(identity, str) or not re.fullmatch(r"[A-Za-z0-9_-]{1,128}", identity):
        raise ValueError("INVALID_ENTITY_ID")
    if parent_id is not None and (not isinstance(parent_id, str) or
                                  not re.fullmatch(r"[A-Za-z0-9_-]{1,128}", parent_id)):
        raise ValueError("INVALID_PARENT_ID")

    config = {
        "project": ("projects", "storage_projects", "project_id", None),
        "specimen": ("specimens", "storage_specimens", "specimen_id", "project_id"),
        "session": ("scan_sessions", "storage_sessions", "session_id", "specimen_id"),
    }
    table, map_table, pk, fk = config[entity_type]
    with registry._connect() as db:
        db.execute("BEGIN IMMEDIATE")
        try:
            parent_select = f", {fk}" if fk else ""
            row = db.execute(f"SELECT {pk}{parent_select} FROM {table} WHERE {pk}=?", (identity,)).fetchone()
            if row is None:
                raise LookupError("ENTITY_NOT_FOUND")
            if fk and row[fk] != parent_id:
                raise ValueError("ENTITY_PARENT_MISMATCH")
            if entity_type == "project":
                query, params = "SELECT 1 FROM specimens WHERE project_id=? LIMIT 1", (identity,)
                children = db.execute(query, params).fetchone()
            elif entity_type == "specimen":
                children = db.execute("SELECT 1 FROM scan_sessions WHERE specimen_id=? LIMIT 1", (identity,)).fetchone()
            else:
                children = any(db.execute(
                    f"SELECT 1 FROM {child_table} WHERE session_id=? LIMIT 1", (identity,)
                ).fetchone() is not None for child_table in (
                    "captures", "processing_runs", "storage_capture_reservations"
                ))
            if children:
                raise ValueError("ENTITY_HAS_CHILDREN")
            mapped = db.execute(f"SELECT relative_path FROM {map_table} WHERE {pk}=?", (identity,)).fetchone()
            if mapped is not None:
                # Do not leave an orphaned directory or silently delete user files.
                from scantopath.storage.numbered_contracts import _safe_path
                target = _safe_path(registry.root, mapped["relative_path"], require_exists=False)
                if target.exists():
                    raise ValueError("ENTITY_HAS_MATERIALIZED_FILES")
                db.execute(f"DELETE FROM {map_table} WHERE {pk}=?", (identity,))
            db.execute(f"DELETE FROM {table} WHERE {pk}=?", (identity,))
            db.execute("COMMIT")
        except BaseException:
            db.execute("ROLLBACK")
            raise
    return identity
