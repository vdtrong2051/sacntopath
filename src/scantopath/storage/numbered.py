"""Stable numbered registry façade; routing, allocation and RAW registration separated.

No schema migration or RAW capture happens during construction.
"""
from __future__ import annotations
from contextlib import contextmanager
from pathlib import Path
import sqlite3
from typing import Literal
from scantopath.acquisition.raw_rgbd import RawRgbdCapture
from scantopath.storage.numbered_schema import TABLES
from .numbered_contracts import (Kind,_TABLES,_PARENT,_CODE,_HIERARCHY,_now,
    _safe_id,_relative,_safe_path,StorageLocation,CaptureReservation)
from .numbered_ops import (_CodeAssignments,_StorageResolver,
    _CaptureReservations,_CatalogExport,_SchemaMigration)

class NumberedStorageRegistry:
    """Backward-compatible API and sole owner of DB connection policy."""

    def __init__(self, root: str | Path):
        self.root = Path(root).absolute()
        self.db_path = self.root / "metadata.sqlite3"
        if not self.db_path.is_file():
            raise FileNotFoundError("Select an existing metadata.sqlite3; no implicit database creation")
        with self._connect() as db:
            if db.execute("PRAGMA user_version").fetchone()[0] != 2:
                raise RuntimeError("Storage schema v2 required: run explicit migration first")
            known = {r[0] for r in db.execute("SELECT name FROM sqlite_master WHERE type='table'")}
            if not set(TABLES).issubset(known):
                raise RuntimeError("Incomplete storage schema v2")
        self._codes = _CodeAssignments(self)
        self._resolver = _StorageResolver(self)
        self._capturing = _CaptureReservations(self)
        self._catalog = _CatalogExport(self)


    @contextmanager
    def _connect(self):
        # sqlite3.Connection.__exit__ alone does not close the connection;
        # explicitly dispose each handle so Windows can lock/backup correctly.
        db = sqlite3.connect(self.db_path, timeout=10, isolation_level=None)
        try:
            db.row_factory = sqlite3.Row
            db.execute("PRAGMA foreign_keys=ON")
            db.execute("PRAGMA busy_timeout=10000")
            yield db
        finally:
            db.close()

    @staticmethod
    def migrate_database(root: str | Path) -> Path:
        return _SchemaMigration.migrate_database(root)

    @staticmethod
    def _allocate(db: sqlite3.Connection, kind: str, scope: str) -> tuple[int,str]:
        return _CodeAssignments._allocate(db,kind,scope)

    @classmethod
    def _assign_in_tx(cls, db: sqlite3.Connection, kind: str, identity: str) -> sqlite3.Row:
        return _CodeAssignments._assign_in_tx(db,kind,identity)

    def assign(self, entity_type: Kind, internal_id: str) -> StorageLocation:
        return self._codes.assign(entity_type, internal_id)

    def assign_all(self) -> dict[str, int]:
        return self._codes.assign_all()

    @staticmethod
    def _path_chain(db: sqlite3.Connection, kind: str, record: sqlite3.Row) -> str:
        return _StorageResolver._path_chain(db,kind,record)

    def resolve_id(self, entity_type: Kind, internal_id: str, *, verify: bool=False) -> StorageLocation:
        return self._resolver.resolve_id(entity_type, internal_id, verify=verify)

    def _get_capture_session(self, capture_id: str) -> str:
        return self._resolver._get_capture_session(capture_id)

    def resolve_public_path(self, public_path: str, *, verify: bool=False) -> StorageLocation:
        return self._resolver.resolve_public_path(public_path, verify=verify)

    def reserve_capture(self, capture_id: str, session_id: str, specimen_id: str) -> CaptureReservation:
        return self._capturing.reserve_capture(capture_id, session_id, specimen_id)

    def _reservation(self, capture_id: str) -> sqlite3.Row:
        return self._capturing._reservation(capture_id)

    def write_reserved_capture(self, capture: RawRgbdCapture) -> Path:
        return self._capturing.write_reserved_capture(capture)

    def register_reserved_capture(self, capture_id: str) -> StorageLocation:
        return self._capturing.register_reserved_capture(capture_id)

    def pending_reservations(self) -> tuple[CaptureReservation, ...]:
        return self._capturing.pending_reservations()

    @staticmethod
    def _safe_cell(value: object) -> str:
        return _CatalogExport._safe_cell(value)

    def export_catalog(self) -> Path:
        return self._catalog.export_catalog()
