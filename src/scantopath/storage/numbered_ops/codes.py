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


from .base import _Part
class _CodeAssignments(_Part):
    @staticmethod
    def _allocate(db: sqlite3.Connection, kind: str, scope: str) -> tuple[int, str]:
        row = db.execute("SELECT next_ordinal FROM storage_counters WHERE entity_type=? AND scope_key=?",
                         (kind, scope)).fetchone()
        ordinal = row[0] if row else 1
        if row:
            db.execute("UPDATE storage_counters SET next_ordinal=? WHERE entity_type=? AND scope_key=?",
                       (ordinal + 1, kind, scope))
        else:
            db.execute("INSERT INTO storage_counters VALUES(?,?,?)", (kind, scope, 2))
        return ordinal, f"{_TABLES[kind][4]}{ordinal:04d}"

    @classmethod
    def _assign_in_tx(cls, db: sqlite3.Connection, kind: str, identity: str) -> sqlite3.Row:
        base, base_pk, numbered, numbered_pk, _prefix, parent_col = _TABLES[kind]
        existing = db.execute(f"SELECT * FROM {numbered} WHERE {numbered_pk}=?", (identity,)).fetchone()
        if existing:
            return existing
        entity = db.execute(f"SELECT * FROM {base} WHERE {base_pk}=?", (identity,)).fetchone()
        if entity is None:
            raise LookupError(f"{kind} not found: {identity}")
        parent_id = entity[parent_col] if parent_col else "root"
        parent = cls._assign_in_tx(db, _PARENT[kind], parent_id) if parent_col else None
        ordinal, code = cls._allocate(db, kind, parent_id)
        if kind == "project":
            relative = f"01_PROJECTS/{code}"
            db.execute("INSERT INTO storage_projects VALUES(?,?,?,?)", (identity, ordinal, code, relative))
        elif kind == "specimen":
            relative = f"{parent['relative_path']}/01_SPECIMENS/{code}"
            db.execute("INSERT INTO storage_specimens VALUES(?,?,?,?,?)", (identity, parent_id, ordinal, code, relative))
        elif kind == "session":
            relative = f"{parent['relative_path']}/01_SESSIONS/{code}"
            db.execute("INSERT INTO storage_sessions VALUES(?,?,?,?,?)", (identity, parent_id, ordinal, code, relative))
        elif kind == "capture":
            relative = entity["relative_path"]  # Legacy stays at its actual location!
            db.execute("INSERT INTO storage_captures VALUES(?,?,?,?,?,?)",
                       (identity, parent_id, ordinal, code, relative, 1))
        elif kind == "run":
            relative = f"{parent['relative_path']}/02_PROCESSING/{code}"
            db.execute("INSERT INTO storage_runs VALUES(?,?,?,?,?)", (identity, parent_id, ordinal, code, relative))
        db.execute(
            "INSERT INTO audit_events(occurred_at,action,level,entity_type,entity_id,details) "
            "VALUES(?,?,?,?,?,?)",
            (_now(), "storage.code.assigned", "INFO", kind, identity,
             json.dumps({"public_code": code, "layout_version": 1 if kind == "capture" else 2})),
        )
        return db.execute(f"SELECT * FROM {numbered} WHERE {numbered_pk}=?", (identity,)).fetchone()

    def assign(self, entity_type: Kind, internal_id: str) -> StorageLocation:
        if entity_type not in _TABLES:
            raise ValueError("Unknown entity type")
        _safe_id(internal_id)
        with self._connect() as db:
            db.execute("BEGIN IMMEDIATE")
            try:
                self._assign_in_tx(db, entity_type, internal_id)
                db.execute("COMMIT")
            except BaseException:
                db.execute("ROLLBACK")
                raise
        return self._registry.resolve_id(entity_type, internal_id)

    def assign_all(self) -> dict[str, int]:
        """Opt-in mapping for legacy SQLite rows; does NOT move/copy RAW files."""
        counts: dict[str, int] = {}
        with self._connect() as db:
            db.execute("BEGIN IMMEDIATE")
            try:
                for kind in _TABLES:
                    base, pk, numbered, *_ = _TABLES[kind]
                    order_field = "registered_at" if kind == "capture" else "created_at"
                    ids = [r[0] for r in db.execute(f"SELECT {pk} FROM {base} ORDER BY {order_field}, {pk}")]
                    before = db.execute(f"SELECT count(*) FROM {numbered}").fetchone()[0]
                    for identity in ids:
                        self._assign_in_tx(db, kind, identity)
                    counts[kind] = db.execute(f"SELECT count(*) FROM {numbered}").fetchone()[0] - before
                db.execute("COMMIT")
            except BaseException:
                db.execute("ROLLBACK")
                raise
        return counts
