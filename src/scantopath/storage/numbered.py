"""07.2: numbered storage registry and safe RAW path routing.

No camera, Qt or 3D processing. The only data authority is metadata.sqlite3.
Existing v1 layouts are never moved and GĐ0 immutable identifiers stay intact.
"""
from __future__ import annotations

import csv
import json
from contextlib import contextmanager
from dataclasses import dataclass
from datetime import datetime, timezone
import os
from pathlib import Path, PurePosixPath
import re
import shutil
import sqlite3
import tempfile
from typing import Literal

from scantopath.storage.numbered_schema import DDL, TABLES
from scantopath.storage.session_store import SessionStore
from scantopath.acquisition.raw_rgbd import RawRgbdCapture

Kind = Literal["project", "specimen", "session", "capture", "run"]
_TABLES = {
    "project": ("projects", "project_id", "storage_projects", "project_id", "P", ""),
    "specimen": ("specimens", "specimen_id", "storage_specimens", "specimen_id", "S", "project_id"),
    "session": ("scan_sessions", "session_id", "storage_sessions", "session_id", "T", "specimen_id"),
    "capture": ("captures", "capture_id", "storage_captures", "capture_id", "C", "session_id"),
    "run": ("processing_runs", "run_id", "storage_runs", "run_id", "R", "session_id"),
}
_PARENT = {"specimen": "project", "session": "specimen", "capture": "session", "run": "session"}
_CODE = re.compile(r"^[PSTCR][0-9]{4,}$", re.ASCII)
_HIERARCHY = re.compile(r"^P[0-9]{4,}(?:/S[0-9]{4,}(?:/T[0-9]{4,}(?:/[CR][0-9]{4,})?)?)?$", re.ASCII)


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="microseconds")


def _safe_id(value: str) -> str:
    if (not isinstance(value, str) or not 1 <= len(value) <= 128
            or not value.isascii() or not all(c.isalnum() or c in "-_" for c in value)):
        raise ValueError("Internal ID must be 1..128 ASCII letters/digits/_/-")
    return value


def _relative(raw: str) -> PurePosixPath:
    if (not isinstance(raw, str) or not raw or "\\" in raw or "\x00" in raw
            or re.match(r"^[A-Za-z]:", raw) or raw.startswith("/")):
        raise ValueError("Invalid storage-relative path")
    pure = PurePosixPath(raw)
    if any(part in (".", "..", "") for part in raw.split("/")) or pure.is_absolute():
        raise ValueError("Unsafe storage-relative path")
    return pure


def _safe_path(root: Path, relative: str, *, require_exists: bool) -> Path:
    parts = _relative(relative).parts
    parent = root
    if parent.is_symlink() or (hasattr(parent, "is_junction") and parent.is_junction()):
        raise ValueError("Storage root cannot be a link/junction")
    for part in parts:
        parent = parent / part
        if parent.is_symlink() or (hasattr(parent, "is_junction") and parent.is_junction()):
            raise ValueError("Storage path contains link/junction")
    resolved_root = root.resolve(strict=True)
    if require_exists:
        out = parent.resolve(strict=True)
        if out != parent.absolute():
            raise ValueError("Storage path alias or traversal")
    else:
        out = parent.resolve(strict=False)
    if not out.is_relative_to(resolved_root):
        raise ValueError("Storage path escapes root")
    if os.name == "nt" and len(str(out)) >= 240:
        raise ValueError("Storage path too long for portable Windows usage")
    return out


@dataclass(frozen=True, slots=True)
class StorageLocation:
    entity_type: str
    internal_id: str
    public_path: str
    relative_path: str
    layout_version: int
    exists: bool
    integrity_state: str  # not_checked, verified, missing, not_materialized


@dataclass(frozen=True, slots=True)
class CaptureReservation:
    capture_id: str
    session_id: str
    public_path: str
    relative_path: str


class NumberedStorageRegistry:
    """All writes are guarded with SQLite BEGIN IMMEDIATE and FK constraints."""

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
        return self.resolve_id(entity_type, internal_id)

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
                packet = store.read_raw_numbered(path, expected_capture_id=internal_id,
                                                 expected_session_id=self._get_capture_session(internal_id))
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
                parent = self._assign_in_tx(db, "session", session_id)
                record = db.execute("SELECT * FROM storage_capture_reservations WHERE capture_id=?", (capture_id,)).fetchone()
                if record:
                    if record["session_id"] != session_id:
                        raise ValueError("Capture reservation belongs to another session")
                else:
                    ordinal, code = self._allocate(db, "capture", session_id)
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
                public = self._path_chain(db, "session", parent) + "/" + record["code"]
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
        return self.resolve_id("capture", capture_id, verify=True)

    def pending_reservations(self) -> tuple[CaptureReservation, ...]:
        result = []
        with self._connect() as db:
            for row in db.execute("SELECT * FROM storage_capture_reservations ORDER BY session_id,ordinal"):
                parent = db.execute("SELECT * FROM storage_sessions WHERE session_id=?", (row["session_id"],)).fetchone()
                result.append(CaptureReservation(row["capture_id"], row["session_id"],
                                                 self._path_chain(db, "session", parent) + "/" + row["code"],
                                                 row["relative_path"]))
        return tuple(result)

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
                        path = self._path_chain(db, kind, record)
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
