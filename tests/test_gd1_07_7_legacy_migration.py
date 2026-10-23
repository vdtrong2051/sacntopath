"""07.7 acceptance: explicit, reversible RAW byte-copy + SQL pointer switch."""
from __future__ import annotations
import json
from pathlib import Path
import sqlite3
import pytest

from scantopath.metadata.store import MetadataStore
from scantopath.storage.numbered import NumberedStorageRegistry
from scantopath.storage.legacy_migration import LegacyRawMigrator, _files, MIGRATION_DIR
from scantopath.storage.session_store import SessionStore
from scantopath.acquisition.sources import SyntheticSource
from scantopath.application.projects import ProjectWorkspaceService
from test_gd1_07_2_numbered_storage import raw


def seed(root: Path, *, mode='v1', coded=True):
    with MetadataStore(root) as store:
        store.create_project('prj', 'Project')
        store.create_specimen('spec', 'prj', 'Specimen')
        store.create_scan_session('sess', 'spec', 'Session')
    ss = SessionStore(root)
    if mode == 'v1':
        path = ss.commit(SyntheticSource().capture(), 'sess', 'spec')
    else:
        path = ss.commit_raw(raw(session='sess', specimen='spec', capture_id='raw-v2'))
    with MetadataStore(root) as store:
        cap = store.register_capture(path)
    NumberedStorageRegistry.migrate_database(root)
    if coded:
        NumberedStorageRegistry(root).assign_all()
    return cap


def pointers(root: Path, cid: str):
    with sqlite3.connect(root / 'metadata.sqlite3') as db:
        return db.execute('SELECT c.relative_path,n.relative_path,n.layout_version FROM captures c '
                          'JOIN storage_captures n ON n.capture_id=c.capture_id WHERE c.capture_id=?', (cid,)).fetchone()


def test_dry_run_does_not_touch_files_or_database(tmp_path):
    cap = seed(tmp_path, mode='v1')
    before = (tmp_path / 'metadata.sqlite3').read_bytes()
    p = LegacyRawMigrator(tmp_path).plan()
    assert len(p) == 1 and p[0].source == cap['relative_path']
    assert p[0].target.endswith('C0001')
    assert (tmp_path / 'metadata.sqlite3').read_bytes() == before
    assert not (tmp_path / MIGRATION_DIR).exists()
    assert not (tmp_path / '01_PROJECTS').exists()


@pytest.mark.parametrize('mode', ['v1', 'v2'])
def test_migrate_roundtrip_preserves_exact_legacy_bytes(tmp_path, mode):
    cap = seed(tmp_path, mode=mode)
    migrator = LegacyRawMigrator(tmp_path)
    plan = migrator.plan()
    hashes = plan[0].hashes
    result = migrator.apply()
    assert result['status'] == 'applied'
    assert result['legacy_retained']
    dest = plan[0].target
    assert _files(tmp_path, plan[0].source, cap['schema_version']) == hashes
    assert _files(tmp_path, dest, cap['schema_version']) == hashes
    assert pointers(tmp_path, cap['capture_id']) == (dest, dest, 2)
    assert ProjectWorkspaceService(tmp_path).inspect_capture(cap['capture_id']).status == 'verified'
    assert NumberedStorageRegistry(tmp_path).resolve_id('capture', cap['capture_id'], verify=True).layout_version == 2
    backup = Path(result['backup'])
    assert backup.is_file()
    with sqlite3.connect(backup) as db:
        assert db.execute('SELECT relative_path FROM captures').fetchone()[0] == plan[0].source
    assert migrator.plan() == ()
    assert migrator.apply()['status'] == 'nothing_to_migrate'
    result2 = migrator.rollback(result['migration_id'])
    assert result2['status'] == 'rolled_back' and result2['restored'] == 1
    assert migrator.rollback(result['migration_id'])['status'] == 'already_rolled_back'
    assert pointers(tmp_path, cap['capture_id']) == (plan[0].source, plan[0].source, 1)
    assert ProjectWorkspaceService(tmp_path).inspect_capture(cap['capture_id']).status == 'verified'
    assert _files(tmp_path, plan[0].source, cap['schema_version']) == hashes
    with sqlite3.connect(tmp_path / 'metadata.sqlite3') as db:
        assert db.execute('PRAGMA integrity_check').fetchone()[0] == 'ok'
        assert db.execute('PRAGMA foreign_key_check').fetchall() == []
        assert db.execute("SELECT count(*) FROM sqlite_master WHERE type='trigger' AND name IN ('storage_captures_move','storage_captures_immutable')").fetchone()[0] == 2
        assert db.execute("SELECT count(*) FROM audit_events WHERE action='storage.raw.migrated'").fetchone()[0] == 1
        assert db.execute("SELECT count(*) FROM audit_events WHERE action='storage.raw.rolled_back'").fetchone()[0] == 1


def test_v1_sqlite_refused_without_mutation(tmp_path):
    with MetadataStore(tmp_path) as store:
        store.create_project('p', 'V1')
    with pytest.raises(RuntimeError):
        LegacyRawMigrator(tmp_path)
    assert not (tmp_path / MIGRATION_DIR).exists()


def test_code_assignment_is_never_implicit(tmp_path):
    seed(tmp_path, coded=False)
    with pytest.raises(RuntimeError, match='assign-all'):
        LegacyRawMigrator(tmp_path).plan()
    assert not (tmp_path / MIGRATION_DIR).exists()


def test_corrupt_raw_is_refused_without_db_changes(tmp_path):
    cap = seed(tmp_path, mode='v2')
    path = tmp_path / cap['relative_path']
    (path / 'depth.y16').write_bytes(b'corrupted')
    with pytest.raises(ValueError):
        LegacyRawMigrator(tmp_path).plan()
    assert pointers(tmp_path, cap['capture_id'])[2] == 1


def test_missing_raw_is_refused(tmp_path):
    cap = seed(tmp_path)
    (tmp_path / cap['relative_path'] / 'depth.npy').unlink()
    with pytest.raises((ValueError, FileNotFoundError)):
        LegacyRawMigrator(tmp_path).plan()


def test_destination_collision_is_refused(tmp_path):
    seed(tmp_path)
    plan = LegacyRawMigrator(tmp_path).plan()[0]
    (tmp_path / plan.target).mkdir(parents=True)
    with pytest.raises(FileExistsError):
        LegacyRawMigrator(tmp_path).apply()


def test_mismatched_capture_registry_is_refused(tmp_path):
    cap = seed(tmp_path)
    with sqlite3.connect(tmp_path / 'metadata.sqlite3') as db:
        db.execute('DROP TRIGGER storage_captures_immutable')
        db.execute('UPDATE storage_captures SET layout_version=2 WHERE capture_id=?', (cap['capture_id'],))
        # Restore for preflight to detect mismatch rather than a missing trigger.
        db.execute("CREATE TRIGGER storage_captures_immutable BEFORE UPDATE ON storage_captures BEGIN SELECT RAISE(ABORT,'storage capture mapping immutable'); END")
    with pytest.raises(RuntimeError, match='Inconsistent'):
        LegacyRawMigrator(tmp_path).plan()


def test_rollback_rejects_tampered_source_and_keeps_numbered_mapping(tmp_path):
    cap = seed(tmp_path)
    m = LegacyRawMigrator(tmp_path)
    result = m.apply()
    plan = m.plan()
    assert plan == ()
    with sqlite3.connect(tmp_path / 'metadata.sqlite3') as db:
        rel = db.execute('SELECT relative_path FROM captures').fetchone()[0]
    folder = tmp_path / rel
    (folder / 'depth.npy').write_bytes(b'corrupted')
    with pytest.raises(RuntimeError):
        m.rollback(result['migration_id'])
    assert pointers(tmp_path, cap['capture_id'])[2] == 2


def test_explicit_cli_confirm_and_dry_run(tmp_path, capsys):
    from scantopath.storage.legacy_migration_cli import main
    seed(tmp_path)
    assert main(['--root', str(tmp_path), 'dry-run']) == 0
    assert 'dry_run' in capsys.readouterr().out
    with pytest.raises(SystemExit):
        main(['--root', str(tmp_path), 'apply'])
    assert not (tmp_path / MIGRATION_DIR).exists()


def test_no_legacy_returns_nothing(tmp_path):
    with MetadataStore(tmp_path) as store:
        store.create_project('p', 'P')
    NumberedStorageRegistry.migrate_database(tmp_path)
    assert LegacyRawMigrator(tmp_path).plan() == ()
    assert LegacyRawMigrator(tmp_path).apply()['count'] == 0


def test_failed_copy_leaves_original_sql_and_recoverable_prepared_journal(tmp_path, monkeypatch):
    cap = seed(tmp_path)
    from scantopath.storage import legacy_migration as implementation
    original = implementation._validate_raw
    def fail_once(root, row, relative, *, numbered):
        if numbered:
            raise RuntimeError('Simulated I/O interruption after target copy')
        return original(root, row, relative, numbered=numbered)
    monkeypatch.setattr(implementation, '_validate_raw', fail_once)
    migrator = LegacyRawMigrator(tmp_path)
    with pytest.raises(RuntimeError, match='Simulated'):
        migrator.apply()
    assert pointers(tmp_path, cap['capture_id'])[2] == 1
    journal = next((tmp_path / MIGRATION_DIR).glob('*/manifest.json'))
    record = json.loads(journal.read_text(encoding='utf-8'))
    assert record['status'] == 'prepared'
    assert (tmp_path / record['items'][0]['target']).is_dir()  # Never silently delete data.
    monkeypatch.setattr(implementation, '_validate_raw', original)
    assert migrator.rollback(record['migration_id'])['restored'] == 0
    assert pointers(tmp_path, cap['capture_id'])[2] == 1


def test_rollback_rejects_tampered_legacy_source(tmp_path):
    cap = seed(tmp_path)
    migrator = LegacyRawMigrator(tmp_path)
    result = migrator.apply()
    original = next((tmp_path / 'sessions').glob('*/captures/*'))
    (original / 'depth.npy').write_bytes(b'bad')
    with pytest.raises(RuntimeError, match='Legacy backup differs'):
        migrator.rollback(result['migration_id'])
    assert pointers(tmp_path, cap['capture_id'])[2] == 2


def test_sqlite_immutability_guard_survives_apply_and_rollback(tmp_path):
    cap = seed(tmp_path)
    migrator = LegacyRawMigrator(tmp_path)
    result = migrator.apply()
    with sqlite3.connect(tmp_path / 'metadata.sqlite3') as db:
        with pytest.raises(sqlite3.IntegrityError):
            db.execute('UPDATE storage_captures SET code=? WHERE capture_id=?',
                       ('C9999', cap['capture_id']))
    migrator.rollback(result['migration_id'])
    with sqlite3.connect(tmp_path / 'metadata.sqlite3') as db:
        with pytest.raises(sqlite3.IntegrityError):
            db.execute('UPDATE storage_captures SET code=? WHERE capture_id=?',
                       ('C9999', cap['capture_id']))


def test_interrupted_post_commit_journal_is_recoverable(tmp_path, monkeypatch):
    """SQLite commit can succeed before journal status is persisted (e.g. disk full)."""
    cap = seed(tmp_path)
    from scantopath.storage import legacy_migration as module
    original_write = module._write_json

    def fail_after_commit(destination, value):
        if value.get('status') == 'applied':
            raise OSError('Simulated journal disk write failure after SQLite commit')
        return original_write(destination, value)

    monkeypatch.setattr(module, '_write_json', fail_after_commit)
    migrator = LegacyRawMigrator(tmp_path)
    with pytest.raises(OSError, match='journal'):
        migrator.apply()
    assert pointers(tmp_path, cap['capture_id'])[2] == 2
    journal = next((tmp_path / MIGRATION_DIR).glob('*/manifest.json'))
    state = json.loads(journal.read_text(encoding='utf-8'))
    assert state['status'] == 'prepared'
    monkeypatch.setattr(module, '_write_json', original_write)
    result = migrator.rollback(state['migration_id'])
    assert result['status'] == 'rolled_back' and result['restored'] == 1
    assert pointers(tmp_path, cap['capture_id'])[2] == 1
