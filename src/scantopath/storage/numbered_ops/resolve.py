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
class _StorageResolver(_Part):
    @staticmethod
    def _path_chain(db: sqlite3.Connection, kind: str, record: sqlite3.Row) -> str:
        result = [record["code"]]
        while kind != "project":
            kind = _PARENT[kind]
            # Actual parent identifier is the parent FK column for this row.
            if kind == "session":
                parent_id = record["session_id"]
            elif kind == "specimen":
                parent_id = record["specimen_id"]
            else:
                parent_id = record["project_id"]
            tab = _TABLES[kind]
            record = db.execute(f"SELECT * FROM {tab[2]} WHERE {tab[3]}=?", (parent_id,)).fetchone()
            if record is None:
                raise RuntimeError("Broken numbered parent chain")
            result.append(record["code"])
        return "/".join(reversed(result))

    def resolve_id(self, entity_type: Kind, internal_id: str, *, verify: bool = False) -> StorageLocation:
        if entity_type not in _TABLES:
            raise ValueError("Unknown entity type")
        _safe_id(internal_id)
        numbered, pk = _TABLES[entity_type][2:4]
        with self._connect() as db:
            record = db.execute(f"SELECT * FROM {numbered} WHERE {pk}=?", (internal_id,)).fetchone()
            if record is None:
                raise LookupError("No numbered mapping for entity: assign() first")
            public = self._path_chain(db, entity_type, record)
            if entity_type == "capture":
                relative = record["relative_path"]
                layout = record["layout_version"]
            else:
                relative = record["relative_path"]
                layout = 2
        path = _safe_path(self.root, relative, require_exists=False)
        present = path.exists()
        state = "not_checked" if present else ("missing" if entity_type == "capture" else "not_materialized")
        if verify and entity_type == "capture":
            if not present:
                raise FileNotFoundError(path)
            store = SessionStore(self.root)
            if layout == 1:
                packet = store.read_capture(path)
            elif layout == 2:
                # 07.7 preserves both RAW generations byte-for-byte. A numbered
                # v1 capture contains historical .npy arrays (no SHA manifest).
                with self._connect() as db:
                    record = db.execute("SELECT session_id,specimen_id,schema_version FROM captures WHERE capture_id=?",
                                        (internal_id,)).fetchone()
                if record is None:
                    raise LookupError("Capture not registered")
                if record["schema_version"] == 1:
                    packet = store.read(path)
                    metadata = packet[0]
                    if (metadata.capture_id != internal_id or
                            metadata.session_id != record["session_id"] or
                            metadata.specimen_id != record["specimen_id"]):
                        raise ValueError("Numbered v1 RAW identity mismatch")
                elif record["schema_version"] == 2:
                    packet = store.read_raw_numbered(path, expected_capture_id=internal_id,
                                                     expected_session_id=record["session_id"])
                else:
                    raise ValueError("Unknown RAW schema version")
            else:
                raise ValueError("Unknown storage layout")
            if packet is None:  # unreachable; defensive
                raise ValueError("RAW verification failed")
            state = "verified"
        return StorageLocation(entity_type, internal_id, public, relative, layout, present, state)

    def _get_capture_session(self, capture_id: str) -> str:
        with self._connect() as db:
            row = db.execute("SELECT session_id FROM captures WHERE capture_id=?", (capture_id,)).fetchone()
            if row is None:
                raise LookupError("Capture not registered")
            return row[0]

    def resolve_public_path(self, public_path: str, *, verify: bool = False) -> StorageLocation:
        if not isinstance(public_path, str) or not _HIERARCHY.fullmatch(public_path):
            raise ValueError("Expected P0001/S0001/T0001/C0001 or R0001 hierarchical codes")
        codes = public_path.split("/")
        kinds = ["project", "specimen", "session"][:min(len(codes), 3)]
        if len(codes) == 4:
            kinds.append("capture" if codes[3].startswith("C") else "run")
        with self._connect() as db:
            parent_id = None
            identity = None
            for kind, code in zip(kinds, codes):
                numbered, pk = _TABLES[kind][2:4]
                parent_key = _TABLES[kind][5]
                if parent_id is None:
                    row = db.execute(f"SELECT * FROM {numbered} WHERE code=?", (code,)).fetchone()
                else:
                    row = db.execute(f"SELECT * FROM {numbered} WHERE code=? AND {parent_key}=?",
                                     (code, parent_id)).fetchone()
                if row is None:
                    raise LookupError("Public path does not exist in registry")
                identity = row[pk]
                parent_id = identity
        return self.resolve_id(kinds[-1], identity, verify=verify)
