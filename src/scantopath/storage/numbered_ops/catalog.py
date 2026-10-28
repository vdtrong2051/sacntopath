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
class _CatalogExport(_Part):
    @staticmethod
    def _safe_cell(value: object) -> str:
        text = str(value)
        return "'" + text if text.lstrip().startswith(("=", "+", "-", "@", "\t", "\r")) else text

    def export_catalog(self) -> Path:
        """Atomic disposable CSV snapshot; SQL mappings stay authoritative."""
        dest = self.root / "00_INDEX" / "catalog.csv"
        dest.parent.mkdir(parents=True, exist_ok=True)
        rows = []
        with self._connect() as db:
            db.execute("BEGIN")
            try:
                for kind in _TABLES:
                    numbered, pk = _TABLES[kind][2:4]
                    for record in db.execute(f"SELECT * FROM {numbered} ORDER BY {pk}"):
                        path = self._registry._path_chain(db, kind, record)
                        layout = record["layout_version"] if kind == "capture" else 2
                        rows.append((kind, record[pk], path, record["relative_path"], layout,
                                     "legacy" if kind == "capture" and layout == 1 else "mapped"))
                db.execute("COMMIT")
            except BaseException:
                db.execute("ROLLBACK")
                raise
        fd, filename = tempfile.mkstemp(prefix=".catalog-", suffix=".tmp", dir=dest.parent)
        try:
            with os.fdopen(fd, "w", encoding="utf-8-sig", newline="") as out:
                csvout = csv.writer(out)
                csvout.writerow(("entity_type", "internal_id", "public_path", "storage_relative_path", "layout_version", "state"))
                for row in rows:
                    csvout.writerow(tuple(self._safe_cell(v) for v in row))
                out.flush()
                os.fsync(out.fileno())
            os.replace(filename, dest)
        finally:
            if os.path.exists(filename):
                os.unlink(filename)
        return dest
