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
class _CaptureReservations(_Part):
    def reserve_capture(self, capture_id: str, session_id: str, specimen_id: str) -> CaptureReservation:
        """Durably reserve C-code. Repeated calls for same capture are idempotent."""
        for v in (capture_id, session_id, specimen_id):
            _safe_id(v)
        with self._connect() as db:
            db.execute("BEGIN IMMEDIATE")
            try:
                row = db.execute("SELECT specimen_id,state FROM scan_sessions WHERE session_id=?", (session_id,)).fetchone()
                if row is None or row["specimen_id"] != specimen_id or row["state"] != "open":
                    raise ValueError("Open session / specimen mismatch")
                if db.execute("SELECT 1 FROM captures WHERE capture_id=?", (capture_id,)).fetchone():
                    raise ValueError("Capture already registered")
                parent = self._registry._assign_in_tx(db, "session", session_id)
                record = db.execute("SELECT * FROM storage_capture_reservations WHERE capture_id=?", (capture_id,)).fetchone()
                if record:
                    if record["session_id"] != session_id:
                        raise ValueError("Capture reservation belongs to another session")
                else:
                    ordinal, code = self._registry._allocate(db, "capture", session_id)
                    relative = f"{parent['relative_path']}/01_CAPTURES/{code}"
                    _safe_path(self.root, relative, require_exists=False)
                    db.execute("INSERT INTO storage_capture_reservations VALUES(?,?,?,?,?)",
                               (capture_id, session_id, ordinal, code, relative))
                    db.execute(
                        "INSERT INTO audit_events(occurred_at,action,level,entity_type,entity_id,details) "
                        "VALUES(?,?,?,?,?,?)",
                        (_now(), "storage.capture.reserved", "INFO", "capture", capture_id,
                         json.dumps({"code": code, "session_id": session_id})),
                    )
                    record = db.execute("SELECT * FROM storage_capture_reservations WHERE capture_id=?", (capture_id,)).fetchone()
                public = self._registry._path_chain(db, "session", parent) + "/" + record["code"]
                db.execute("COMMIT")
            except BaseException:
                db.execute("ROLLBACK")
                raise
        return CaptureReservation(capture_id, session_id, public, record["relative_path"])

    def _reservation(self, capture_id: str) -> sqlite3.Row:
        with self._connect() as db:
            row = db.execute("SELECT * FROM storage_capture_reservations WHERE capture_id=?", (capture_id,)).fetchone()
            if row is None:
                raise LookupError("No pending numbered capture reservation")
            return row

    def write_reserved_capture(self, capture: RawRgbdCapture) -> Path:
        if not isinstance(capture, RawRgbdCapture):
            raise TypeError("Expected a RAW v2 capture")
        row = self._reservation(capture.metadata.capture_id)
        if row["session_id"] != capture.metadata.session_id:
            raise ValueError("RAW metadata session mismatch")
        with self._connect() as db:
            session = db.execute("SELECT specimen_id,state FROM scan_sessions WHERE session_id=?",
                                 (row["session_id"],)).fetchone()
            if session is None or session["specimen_id"] != capture.metadata.specimen_id or session["state"] != "open":
                raise ValueError("RAW metadata specimen or session state mismatch")
        return SessionStore(self.root).commit_raw_numbered(capture, row["relative_path"])

    def register_reserved_capture(self, capture_id: str) -> StorageLocation:
        """Validate on-disk v2 RAW before atomically writing SQLite and mapping.

        If registration fails, RAW and its durable reservation are NOT deleted.
        """
        _safe_id(capture_id)
        row = self._reservation(capture_id)
        path = _safe_path(self.root, row["relative_path"], require_exists=True)
        packet = SessionStore(self.root).read_raw_numbered(path, expected_capture_id=capture_id,
                                                          expected_session_id=row["session_id"])
        meta = packet.metadata
        with self._connect() as db:
            db.execute("BEGIN IMMEDIATE")
            try:
                # Reject stale, tampered reservations at the time of DB commit.
                fresh = db.execute("SELECT * FROM storage_capture_reservations WHERE capture_id=?", (capture_id,)).fetchone()
                if fresh is None or dict(fresh) != dict(row):
                    raise RuntimeError("Reservation changed while verifying RAW")
                session = db.execute("SELECT specimen_id,state FROM scan_sessions WHERE session_id=?",
                                     (meta.session_id,)).fetchone()
                if session is None or session["state"] != "open" or session["specimen_id"] != meta.specimen_id:
                    raise ValueError("Session closed or specimen mismatch")
                db.execute("INSERT INTO captures(capture_id,session_id,specimen_id,schema_version,kind,measured,relative_path,registered_at) VALUES(?,?,?,?,?,?,?,?)",
                           (capture_id, meta.session_id, meta.specimen_id, meta.schema_version,
                            meta.kind.value, int(meta.measured), row["relative_path"], _now()))
                db.execute("INSERT INTO storage_captures VALUES(?,?,?,?,?,2)",
                           (capture_id, meta.session_id, row["ordinal"], row["code"], row["relative_path"]))
                db.execute("INSERT INTO audit_events(occurred_at,action,level,entity_type,entity_id,details) VALUES(?,?,?,?,?,?)",
                           (_now(), "capture.registered", "INFO", "capture", capture_id,
                            '{"layout_version":2,"numbered":true}'))
                db.execute("DELETE FROM storage_capture_reservations WHERE capture_id=?", (capture_id,))
                db.execute("COMMIT")
            except BaseException:
                db.execute("ROLLBACK")
                raise
        return self._registry.resolve_id("capture", capture_id, verify=True)

    def pending_reservations(self) -> tuple[CaptureReservation, ...]:
        result = []
        with self._connect() as db:
            for row in db.execute("SELECT * FROM storage_capture_reservations ORDER BY session_id,ordinal"):
                parent = db.execute("SELECT * FROM storage_sessions WHERE session_id=?", (row["session_id"],)).fetchone()
                result.append(CaptureReservation(row["capture_id"], row["session_id"],
                                                 self._registry._path_chain(db, "session", parent) + "/" + row["code"],
                                                 row["relative_path"]))
        return tuple(result)
