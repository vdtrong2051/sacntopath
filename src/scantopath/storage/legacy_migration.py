"""07.7 - opt-in, copy-first and reversible migration of REGISTERED legacy RAW.

No implicit schema upgrades / code assignment / cleanup of original RAW.
Run only with the ScanToPath app, acquisition processes and other writers closed.
The registry schema is unchanged; the immutable triggers are temporarily
recreated inside one EXCLUSIVE SQLite transaction, never left disabled.
"""
from __future__ import annotations

from dataclasses import dataclass, asdict
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import sqlite3
import uuid

from scantopath.storage.numbered import NumberedStorageRegistry, _safe_path
from scantopath.storage.numbered_schema import DDL
from scantopath.storage.session_store import SessionStore
from scantopath.acquisition.raw_rgbd import RawRgbdCapture

MIGRATION_DIR = '00_INDEX/07_07_migrations'
TRIGGERS = ('storage_captures_immutable', 'storage_captures_move')
LEGACY_RE = re.compile(r'^sessions/([A-Za-z0-9_-]+)/captures/([A-Za-z0-9_-]+)$')
NUMBERED_RE = re.compile(r'^01_PROJECTS/P[0-9]{4,}/01_SPECIMENS/S[0-9]{4,}/01_SESSIONS/T[0-9]{4,}/01_CAPTURES/C[0-9]{4,}$')
EXPECTED = {1: frozenset({'depth.npy', 'rgb.npy', 'metadata.json', 'COMMITTED'}),
            2: frozenset({'color.mjpg', 'depth.y16', 'metadata.json', 'manifest.json', 'COMMITTED'})}


def _stamp() -> str:
    return datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S%fZ')


def _digest(path: Path) -> str:
    h = hashlib.sha256()
    with path.open('rb') as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b''):
            h.update(chunk)
    return h.hexdigest()


def _files(root: Path, rel: str, schema: int) -> dict[str, str]:
    folder = _safe_path(root, rel, require_exists=True)
    if not folder.is_dir() or folder.is_symlink():
        raise ValueError('RAW capture folder is not a normal directory')
    names = {entry.name for entry in folder.iterdir()}
    if names != EXPECTED[schema]:
        raise ValueError('RAW directory contains missing/extra files')
    for name in names:
        entry = folder / name
        if not entry.is_file() or entry.is_symlink() or (hasattr(entry, 'is_junction') and entry.is_junction()):
            raise ValueError('RAW contains a link or non-regular entry')
    return {name: _digest(folder / name) for name in sorted(names)}


def _validate_raw(root: Path, row: dict, relative: str, *, numbered: bool) -> None:
    store = SessionStore(root)
    directory = _safe_path(root, relative, require_exists=True)
    schema = row['schema_version']
    if schema == 1:
        # The historical v1 arrays have no SHA-256 manifest. Verify their shape
        # and identity but do not claim cryptographic provenance.
        meta, _, _ = store.read(directory)
    elif schema == 2:
        if numbered:
            packet = store.read_raw_numbered(directory, expected_capture_id=row['capture_id'],
                                             expected_session_id=row['session_id'])
        else:
            packet = store.read_raw(directory)
        meta = packet.metadata
    else:
        raise ValueError('Unsupported legacy RAW schema')
    if (meta.capture_id != row['capture_id'] or meta.session_id != row['session_id']
            or meta.specimen_id != row['specimen_id'] or meta.schema_version != schema):
        raise ValueError('RAW identity/schema mismatch with SQLite')


def _connect(root: Path) -> sqlite3.Connection:
    db = sqlite3.connect(root / 'metadata.sqlite3', timeout=10, isolation_level=None)
    db.row_factory = sqlite3.Row
    db.execute('PRAGMA foreign_keys=ON')
    db.execute('PRAGMA busy_timeout=10000')
    return db


def _path_for_code(row: sqlite3.Row) -> str:
    parent = row['session_path']
    code = row['code']
    dest = f'{parent}/01_CAPTURES/{code}'
    if not NUMBERED_RE.fullmatch(dest):
        raise ValueError('Invalid target path derived from numbered registry')
    return dest


def _triggers(db: sqlite3.Connection) -> dict[str, str]:
    sql = dict(db.execute(
        f"SELECT name,sql FROM sqlite_master WHERE type='trigger' AND name IN ({','.join('?' for _ in TRIGGERS)})",
        TRIGGERS))
    if set(sql) != set(TRIGGERS):
        raise RuntimeError('Numbered immutable triggers missing/altered; refuse migration')
    canonical = lambda value: re.sub(r'\s+', ' ', value.strip().rstrip(';'))
    for name in TRIGGERS:
        expected = re.search(r'CREATE TRIGGER ' + name + r'\b.*?END;', DDL, re.DOTALL)
        if expected is None or canonical(sql[name]) != canonical(expected.group()):
            raise RuntimeError('Immutable storage trigger differs from schema contract: ' + name)
    return sql


def _switch_paths(db: sqlite3.Connection, items: list[dict], *, reverse: bool) -> None:
    """Temporarily suspend exactly two immutable-path triggers INSIDE transaction."""
    original = _triggers(db)
    for name in TRIGGERS:
        db.execute(f'DROP TRIGGER {name}')
    try:
        for row in items:
            a, b = (row['target'], row['source']) if reverse else (row['source'], row['target'])
            previous_layout, new_layout = (2, 1) if reverse else (1, 2)
            first = db.execute('UPDATE captures SET relative_path=? WHERE capture_id=? AND relative_path=?',
                               (b, row['capture_id'], a))
            second = db.execute('UPDATE storage_captures SET relative_path=?, layout_version=? '
                                'WHERE capture_id=? AND relative_path=? AND layout_version=?',
                                (b, new_layout, row['capture_id'], a, previous_layout))
            if first.rowcount != 1 or second.rowcount != 1:
                raise RuntimeError('SQLite capture path changed since migration plan')
    finally:
        # If CREATE fails, caller ROLLBACK restores both triggers and all paths.
        for name in TRIGGERS:
            db.execute(original[name])
    if db.execute('PRAGMA foreign_key_check').fetchone() is not None:
        raise RuntimeError('Broken SQLite foreign keys after path update')
    if set(_triggers(db)) != set(TRIGGERS):
        raise RuntimeError('Failed to restore immutable capture triggers')


def _write_json(destination: Path, obj: dict) -> None:
    tmp = destination.with_name('.' + destination.name + '.' + uuid.uuid4().hex + '.partial')
    try:
        with tmp.open('x', encoding='utf-8') as f:
            json.dump(obj, f, ensure_ascii=False, indent=2, sort_keys=True)
            f.write('\n')
            f.flush()
            os.fsync(f.fileno())
        os.replace(tmp, destination)
    finally:
        if tmp.exists():
            tmp.unlink()


@dataclass(frozen=True, slots=True)
class MigrationItem:
    capture_id: str
    session_id: str
    specimen_id: str
    schema_version: int
    source: str
    target: str
    hashes: dict[str, str]

    def record(self) -> dict:
        return asdict(self)


class LegacyRawMigrator:
    """A separately invoked operator tool. Opening the application never calls it."""

    def __init__(self, root: str | Path):
        self.root = Path(root).absolute()
        # Registry constructor guards missing/v1/incomplete SQLite without writing.
        self.registry = NumberedStorageRegistry(self.root)
        if self.root.is_symlink() or (hasattr(self.root, 'is_junction') and self.root.is_junction()):
            raise ValueError('Refusing linked data root')

    def plan(self, *, capture_id: str | None = None) -> tuple[MigrationItem, ...]:
        """Strict no-write preflight. Mapping codes must already be assigned by 07.2."""
        with _connect(self.root) as db:
            if db.execute('PRAGMA user_version').fetchone()[0] != 2:
                raise RuntimeError('Require explicit SQLite schema v2 before RAW migration')
            _triggers(db)
            sql = '''SELECT c.capture_id,c.session_id,c.specimen_id,c.schema_version,c.relative_path,
                      n.relative_path AS numbered_path,n.layout_version,n.code,
                      s.relative_path AS session_path
                      FROM captures c LEFT JOIN storage_captures n ON n.capture_id=c.capture_id
                      LEFT JOIN storage_sessions s ON s.session_id=c.session_id
                      WHERE (? IS NULL OR c.capture_id=?) ORDER BY c.registered_at,c.capture_id'''
            records = db.execute(sql, (capture_id, capture_id)).fetchall()
        if capture_id is not None and not records:
            raise LookupError('Capture ID not registered')
        items = []
        for r in records:
            if r['layout_version'] == 2 and r['relative_path'] == r['numbered_path']:
                if r['relative_path'] != _path_for_code(r):
                    raise RuntimeError('Inconsistent numbered capture mapping')
                continue  # idempotent, already migrated/new numbered RAW.
            if r['layout_version'] is None or r['session_path'] is None:
                raise RuntimeError('Missing numbered code; run explicit 07.2 assign-all first')
            if r['layout_version'] != 1 or r['relative_path'] != r['numbered_path']:
                raise RuntimeError('Inconsistent numbered capture mapping; manual repair required')
            source = r['relative_path']
            match = LEGACY_RE.fullmatch(source)
            if not match or (match.group(1), match.group(2)) != (r['session_id'], r['capture_id']):
                raise ValueError('Legacy SQLite capture path does not match immutable IDs')
            if r['schema_version'] not in (1, 2):
                raise ValueError('Unsupported RAW version')
            target = _path_for_code(r)
            output = _safe_path(self.root, target, require_exists=False)
            if output.exists() or output.is_symlink():
                raise FileExistsError('Numbered destination already exists; do not overwrite')
            row = dict(r)
            _validate_raw(self.root, row, source, numbered=False)
            checksums = _files(self.root, source, row['schema_version'])
            items.append(MigrationItem(r['capture_id'], r['session_id'], r['specimen_id'],
                                       r['schema_version'], source, target, checksums))
        return tuple(items)

    @staticmethod
    def _snapshot(db: sqlite3.Connection, dest: Path) -> None:
        # Called on a separate reader connection while writer holds EXCLUSIVE.
        backup = sqlite3.connect(dest)
        try:
            db.backup(backup)
            if backup.execute('PRAGMA integrity_check').fetchone()[0] != 'ok':
                raise RuntimeError('Backup integrity check failed')
        finally:
            backup.close()

    def apply(self, *, capture_id: str | None = None) -> dict:
        items = self.plan(capture_id=capture_id)
        if not items:
            return {'status': 'nothing_to_migrate', 'count': 0}
        needed = sum(sum((_safe_path(self.root, i.source, require_exists=True) / name).stat().st_size
                         for name in i.hashes) for i in items)
        estimated_db = (self.root / 'metadata.sqlite3').stat().st_size
        if shutil.disk_usage(self.root).free < needed * 2 + estimated_db * 3 + 1024 * 1024:
            raise OSError('Insufficient free disk space for copy and SQLite backup')
        migration_id = _stamp() + '-' + uuid.uuid4().hex[:8]
        folder = self.root / MIGRATION_DIR / migration_id
        folder.mkdir(parents=True, exist_ok=False)
        manifest = folder / 'manifest.json'
        state = {'format_version': 1, 'migration_id': migration_id,
                 'status': 'prepared', 'items': [x.record() for x in items]}
        _write_json(manifest, state)
        created: list[Path] = []
        db = _connect(self.root)
        committed = False
        try:
            # IMMEDIATE grabs the exclusive *writer* slot BEFORE the snapshot.
            # Unlike EXCLUSIVE in rollback-journal mode, it permits the second
            # connection required by sqlite3.backup() to read without deadlock.
            # No other writer can change the database until our commit/rollback.
            db.execute('BEGIN IMMEDIATE')
            with _connect(self.root) as source_ro:
                self._snapshot(source_ro, folder / 'metadata-before.sqlite3')
            # Detect stale preflight/mapping changes before creating any RAW copy.
            fresh = db.execute('SELECT capture_id,relative_path FROM captures').fetchall()
            locations = {r['capture_id']: r['relative_path'] for r in fresh}
            for item in items:
                if locations.get(item.capture_id) != item.source:
                    raise RuntimeError('SQLite changed since preflight')
                mapping = db.execute('SELECT relative_path,layout_version FROM storage_captures WHERE capture_id=?',
                                     (item.capture_id,)).fetchone()
                if mapping is None or (mapping['relative_path'], mapping['layout_version']) != (item.source, 1):
                    raise RuntimeError('Numbered mapping changed since preflight')
                if _files(self.root, item.source, item.schema_version) != item.hashes:
                    raise RuntimeError('RAW changed since preflight')
            if db.execute('PRAGMA integrity_check').fetchone()[0] != 'ok':
                raise RuntimeError('SQLite integrity check failed')
            for item in items:
                src = _safe_path(self.root, item.source, require_exists=True)
                dst = _safe_path(self.root, item.target, require_exists=False)
                dst.parent.mkdir(parents=True, exist_ok=True)
                staging = dst.parent / ('.' + dst.name + '.' + uuid.uuid4().hex + '.partial')
                staging.mkdir()
                try:
                    for name in item.hashes:
                        shutil.copyfile(src / name, staging / name)
                    # Verify copy bytes BEFORE exposing its final name.
                    copied = {name: _digest(staging / name) for name in item.hashes}
                    if copied != item.hashes:
                        raise RuntimeError('Copied RAW checksum differs from source')
                    if dst.exists() or dst.is_symlink():
                        raise FileExistsError('Destination appeared during migration')
                    staging.rename(dst)
                    created.append(dst)
                finally:
                    if staging.exists():
                        shutil.rmtree(staging)
                if _files(self.root, item.target, item.schema_version) != item.hashes:
                    raise RuntimeError('Destination changed after copy')
                _validate_raw(self.root, item.record(), item.target, numbered=True)
            # Last proof of unchanged legacy backup before publishing the new DB paths.
            for item in items:
                if _files(self.root, item.source, item.schema_version) != item.hashes:
                    raise RuntimeError('Legacy RAW changed during copy; SQLite left intact')
            _switch_paths(db, [x.record() for x in items], reverse=False)
            for item in items:
                db.execute('INSERT INTO audit_events(occurred_at,action,level,entity_type,entity_id,details) VALUES(?,?,?,?,?,?)',
                           (datetime.now(timezone.utc).isoformat(), 'storage.raw.migrated', 'INFO',
                            'capture', item.capture_id,
                            json.dumps({'migration_id': migration_id, 'from': item.source, 'to': item.target})))
            db.execute('COMMIT')
            committed = True
            state['status'] = 'applied'
            _write_json(manifest, state)
            return {'status': 'applied', 'migration_id': migration_id, 'count': len(items),
                    'backup': str(folder / 'metadata-before.sqlite3'), 'legacy_retained': True}
        except BaseException:
            if not committed:
                try:
                    db.execute('ROLLBACK')
                except sqlite3.OperationalError:
                    pass
                # Never delete copies on uncertainty; rollback handles prepared state.
            raise
        finally:
            db.close()

    def rollback(self, migration_id: str) -> dict:
        if not re.fullmatch(r'[0-9]{8}T[0-9]{12}Z-[0-9a-f]{8}', migration_id):
            raise ValueError('Invalid migration identifier')
        folder = self.root / MIGRATION_DIR / migration_id
        manifest = folder / 'manifest.json'
        if not manifest.is_file() or manifest.is_symlink():
            raise FileNotFoundError('Migration journal not found')
        state = json.loads(manifest.read_text(encoding='utf-8'))
        if state.get('migration_id') != migration_id or state.get('format_version') != 1:
            raise ValueError('Invalid migration journal')
        if state.get('status') == 'rolled_back':
            return {'status': 'already_rolled_back', 'migration_id': migration_id}
        if state.get('status') not in ('prepared', 'applied'):
            raise ValueError('Unknown migration state')
        items = state['items']
        if not isinstance(items, list) or not items:
            raise ValueError('Empty migration journal')
        with _connect(self.root) as db:
            db.execute('BEGIN EXCLUSIVE')
            try:
                to_revert = []
                for item in items:
                    for key in ('capture_id','source','target','schema_version','hashes','session_id','specimen_id'):
                        if key not in item:
                            raise ValueError('Incomplete migration journal')
                    if (not LEGACY_RE.fullmatch(item['source']) or
                            not NUMBERED_RE.fullmatch(item['target']) or item['schema_version'] not in (1, 2)):
                        raise ValueError('Unsafe migration journal paths')
                    if _files(self.root, item['source'], item['schema_version']) != item['hashes']:
                        raise RuntimeError('Legacy backup differs; refusing rollback')
                    _validate_raw(self.root, item, item['source'], numbered=False)
                    target = _safe_path(self.root, item['target'], require_exists=False)
                    if target.exists():
                        if _files(self.root, item['target'], item['schema_version']) != item['hashes']:
                            raise RuntimeError('Numbered RAW changed; refusing rollback')
                    recorded = db.execute('SELECT c.relative_path,n.relative_path AS mapped,n.layout_version '
                                          'FROM captures c JOIN storage_captures n ON n.capture_id=c.capture_id '
                                          'WHERE c.capture_id=? AND c.session_id=?',
                                          (item['capture_id'], item['session_id'])).fetchone()
                    if recorded is None:
                        raise RuntimeError('Capture missing while rolling back')
                    current = (recorded['relative_path'], recorded['mapped'], recorded['layout_version'])
                    if current == (item['target'], item['target'], 2):
                        if not target.is_dir():
                            raise RuntimeError('Numbered RAW missing; refusing rollback')
                        to_revert.append(item)
                    elif current != (item['source'], item['source'], 1):
                        raise RuntimeError('Unexpected post-migration SQLite changes')
                if to_revert:
                    _switch_paths(db, to_revert, reverse=True)
                    for item in to_revert:
                        db.execute('INSERT INTO audit_events(occurred_at,action,level,entity_type,entity_id,details) VALUES(?,?,?,?,?,?)',
                                   (datetime.now(timezone.utc).isoformat(), 'storage.raw.rolled_back', 'INFO',
                                    'capture', item['capture_id'], json.dumps({'migration_id': migration_id})))
                db.execute('COMMIT')
            except BaseException:
                db.execute('ROLLBACK')
                raise
        # Keep copied numbered directories intact for manual examination.
        # They can be removed later only through a separately reviewed operation.
        state['status'] = 'rolled_back'
        _write_json(manifest, state)
        return {'status': 'rolled_back', 'migration_id': migration_id,
                'restored': len(to_revert), 'numbered_copies_retained': True}
