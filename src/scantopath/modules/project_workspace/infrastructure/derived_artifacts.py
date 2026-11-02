"""FT-07.3: opt-in, session-owned derived snapshot artifacts in metadata.sqlite3.

This is NOT a RAW Capture, and cannot be used as geometry ground truth.
No DB connection/migration at module import. All writes happen only after
explicit Save Snapshot to an already validated active ScanSession, or an
explicit 'Import Snapshot' action. Existing SQLite user_version stays 2.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import shutil
import sqlite3
from uuid import uuid4

REQUIRED = ('cloud.ply', 'snapshot.json', 'selected_points_mask.png')
OPTIONAL = ('inferred_points_mask.png', 'smoothed_points_mask.png')
MAX_TOTAL = 256 * 1024 * 1024


class DerivedArtifactError(RuntimeError):
    pass


@dataclass(frozen=True, slots=True)
class DerivedSnapshot:
    artifact_id: str
    project_id: str
    specimen_id: str
    session_id: str
    relative_dir: str
    created_utc: str
    point_count: int
    reference_mode: str
    estimated: bool
    metadata_sha256: str


SCHEMA = '''CREATE TABLE IF NOT EXISTS ft07_derived_artifacts (
    artifact_id TEXT PRIMARY KEY,
    project_id TEXT NOT NULL,
    specimen_id TEXT NOT NULL,
    session_id TEXT NOT NULL,
    relative_dir TEXT NOT NULL UNIQUE,
    created_utc TEXT NOT NULL,
    point_count INTEGER NOT NULL CHECK(point_count >= 0),
    reference_mode TEXT NOT NULL,
    estimated INTEGER NOT NULL CHECK(estimated IN (0,1)),
    metadata_sha256 TEXT NOT NULL,
    UNIQUE(session_id, metadata_sha256)
)'''


def _sha(path: Path) -> str:
    h = hashlib.sha256()
    with path.open('rb') as f:
        while True:
            chunk = f.read(1024 * 1024)
            if not chunk:
                return h.hexdigest()
            h.update(chunk)


def _root(raw: str | Path) -> Path:
    p = Path(raw).absolute()
    if not p.is_dir() or p.is_symlink() or (hasattr(p, 'is_junction') and p.is_junction()):
        raise DerivedArtifactError('STORE_UNAVAILABLE')
    db = p / 'metadata.sqlite3'
    if not db.is_file() or db.is_symlink():
        raise DerivedArtifactError('STORE_DATABASE_MISSING')
    return p.resolve(strict=True)


def _read_db(db: Path):
    uri = db.as_uri() + '?mode=ro'
    return sqlite3.connect(uri, uri=True, timeout=5.0)


def _has_table(conn: sqlite3.Connection) -> bool:
    return conn.execute("SELECT 1 FROM sqlite_master WHERE type='table' AND name='ft07_derived_artifacts'").fetchone() is not None


def _validate_lineage(root: Path, project_id: str, specimen_id: str, session_id: str):
    # The real authoritative application service validates ownership.
    from scantopath.modules.project_workspace.application.service import ProjectWorkspaceService
    service = ProjectWorkspaceService(root)
    if service.info.schema_version != 2:
        raise DerivedArtifactError('SNAPSHOT_REQUIRES_SQLITE_V2')
    try:
        tree = service.get_project_tree(project_id)
    except (KeyError, ValueError) as exc:
        raise DerivedArtifactError('PROJECT_NOT_FOUND') from exc
    for node in tree.specimens:
        if node.specimen.specimen_id == specimen_id:
            for session in node.sessions:
                if session.session_id == session_id:
                    return
    raise DerivedArtifactError('SNAPSHOT_SESSION_LINEAGE_MISMATCH')


def _validate_source(folder: str | Path):
    p = Path(folder).absolute()
    if not p.is_dir() or p.is_symlink() or (hasattr(p, 'is_junction') and p.is_junction()):
        raise DerivedArtifactError('SNAPSHOT_DIRECTORY_INVALID')
    files = []
    for name in REQUIRED:
        file = p / name
        if not file.is_file() or file.is_symlink():
            raise DerivedArtifactError('SNAPSHOT_REQUIRED_FILE_MISSING_' + name)
        files.append(file)
    for name in OPTIONAL:
        file = p / name
        if file.exists():
            if not file.is_file() or file.is_symlink():
                raise DerivedArtifactError('SNAPSHOT_OPTIONAL_FILE_INVALID_' + name)
            files.append(file)
    if sum(file.stat().st_size for file in files) > MAX_TOTAL:
        raise DerivedArtifactError('SNAPSHOT_TOO_LARGE')
    try:
        doc = json.loads((p / 'snapshot.json').read_text(encoding='utf-8'))
        if (doc.get('schema_version') != 'ft06.snapshot.v1'
                or doc.get('type') != 'processed_single_frame_point_cloud'
                or doc.get('coordinate_frame') != 'depth_optical'
                or doc.get('units') != 'm'
                or type(doc.get('point_count')) is not int
                or doc['point_count'] <= 0):
            raise ValueError('Invalid snapshot contract')
        hashes = [('cloud.ply', 'cloud_ply_sha256'),
                  ('selected_points_mask.png', 'selected_points_mask_sha256'),
                  ('inferred_points_mask.png', 'inferred_points_mask_png_sha256'),
                  ('smoothed_points_mask.png', 'smoothed_points_mask_png_sha256')]
        for name, key in hashes:
            if (p / name).is_file() and doc.get(key) != _sha(p / name):
                raise ValueError('Snapshot checksum mismatch: ' + name)
    except (OSError, UnicodeError, json.JSONDecodeError, ValueError, TypeError) as exc:
        raise DerivedArtifactError('SNAPSHOT_METADATA_INVALID') from exc
    return p, files, doc


def list_snapshots(root: str | Path, session_id: str) -> tuple[DerivedSnapshot, ...]:
    store = _root(root)
    with _read_db(store / 'metadata.sqlite3') as db:
        if not _has_table(db):
            return ()
        rows = db.execute('''SELECT artifact_id,project_id,specimen_id,session_id,relative_dir,
                                    created_utc,point_count,reference_mode,estimated,metadata_sha256
                             FROM ft07_derived_artifacts WHERE session_id=? ORDER BY created_utc DESC''',
                          (session_id,)).fetchall()
    return tuple(DerivedSnapshot(*row) for row in rows)


def resolve_snapshot(root: str | Path, artifact: DerivedSnapshot) -> Path:
    store = _root(root)
    path = (store / artifact.relative_dir).resolve(strict=True)
    if not path.is_relative_to(store / 'derived' / 'snapshots') or not path.is_dir():
        raise DerivedArtifactError('SNAPSHOT_PATH_OUTSIDE_STORE')
    metadata = path / 'snapshot.json'
    ply = path / 'cloud.ply'
    if (metadata.is_symlink() or ply.is_symlink() or not ply.is_file()
            or _sha(metadata) != artifact.metadata_sha256):
        raise DerivedArtifactError('SNAPSHOT_SOURCE_CHANGED')
    _validate_source(path)
    return ply


def attach_snapshot(root: str | Path, project_id: str, specimen_id: str,
                    session_id: str, folder: str | Path) -> DerivedSnapshot:
    store = _root(root)
    _validate_lineage(store, project_id, specimen_id, session_id)
    src, files, doc = _validate_source(folder)
    db = store / 'metadata.sqlite3'
    with _read_db(db) as conn:
        version = int(conn.execute('PRAGMA user_version').fetchone()[0])
    if version != 2:
        raise DerivedArtifactError('STORE_SCHEMA_CHANGED')
    metadata_digest = _sha(src / 'snapshot.json')
    with _read_db(db) as conn:
        if _has_table(conn):
            row = conn.execute('''SELECT artifact_id,project_id,specimen_id,session_id,relative_dir,
                                         created_utc,point_count,reference_mode,estimated,metadata_sha256
                                  FROM ft07_derived_artifacts
                                  WHERE session_id=? AND metadata_sha256=?''',
                               (session_id, metadata_digest)).fetchone()
            if row is not None:
                existing = DerivedSnapshot(*row)
                resolve_snapshot(store, existing)
                return existing
    # The first attachment is a deliberate additive SQLite extension, backed up
    # with SQLite's online backup API, without upgrading unrelated store schema.
    with _read_db(db) as conn:
        needs_extension = not _has_table(conn)
    if needs_extension:
        backups = store / 'backups'
        backups.mkdir(exist_ok=True)
        if backups.is_symlink() or not backups.resolve().is_relative_to(store):
            raise DerivedArtifactError('UNSAFE_BACKUP_DIRECTORY')
        backup = backups / ('metadata.pre-ft07.' + datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S%f') + '.sqlite3')
        with _read_db(db) as origin, sqlite3.connect(backup) as destination:
            origin.backup(destination)
    artifact_id = uuid4().hex
    dest_root = store / 'derived' / 'snapshots'
    dest_root.mkdir(parents=True, exist_ok=True)
    if (dest_root.is_symlink() or (store / 'derived').is_symlink() or
            not dest_root.resolve().is_relative_to(store)):
        raise DerivedArtifactError('UNSAFE_ARTIFACT_DIRECTORY')
    destination = dest_root / artifact_id
    stage = dest_root / ('.partial-' + artifact_id)
    try:
        stage.mkdir()
        for file in files:
            target = stage / file.name
            shutil.copyfile(file, target)
            if _sha(target) != _sha(file):
                raise DerivedArtifactError('SNAPSHOT_COPY_CHECKSUM_MISMATCH')
        stage.rename(destination)
        relative = destination.relative_to(store).as_posix()
        item = DerivedSnapshot(artifact_id, project_id, specimen_id, session_id, relative,
                               datetime.now(timezone.utc).isoformat(), doc['point_count'],
                               str(doc.get('reference_mode') or 'unknown'),
                               bool(doc.get('ply_includes_estimated_or_smoothed_xyz', False)),
                               _sha(destination / 'snapshot.json'))
        with sqlite3.connect(db, timeout=10.0) as conn:
            conn.execute('PRAGMA busy_timeout=10000')
            conn.execute('BEGIN IMMEDIATE')
            if int(conn.execute('PRAGMA user_version').fetchone()[0]) != 2:
                raise DerivedArtifactError('STORE_SCHEMA_CHANGED')
            conn.execute(SCHEMA)
            conn.execute('''CREATE INDEX IF NOT EXISTS ft07_snapshot_by_session
                            ON ft07_derived_artifacts(session_id,created_utc)''')
            conn.execute('''INSERT INTO ft07_derived_artifacts VALUES (?,?,?,?,?,?,?,?,?,?)''',
                         (item.artifact_id, item.project_id, item.specimen_id, item.session_id,
                          item.relative_dir, item.created_utc, item.point_count,
                          item.reference_mode, int(item.estimated), item.metadata_sha256))
        return item
    except Exception:
        if stage.exists():
            shutil.rmtree(stage, ignore_errors=True)
        if destination.exists():
            shutil.rmtree(destination, ignore_errors=True)
        raise
