"""07.3: real SQLite-backed Project Workspace service (no Qt, hardware, or RAW migration)."""
from __future__ import annotations

from dataclasses import FrozenInstanceError
from pathlib import Path
import json
import sqlite3
import subprocess
import sys

import pytest

from scantopath.application.contracts import UiDataState
from scantopath.application.projects import (
    NumberedSchemaRequiredError, NumberingPendingError,
    ProjectWorkspaceService, StoreNotOpenError,
)
from scantopath.metadata.store import MetadataStore
from scantopath.storage.numbered import NumberedStorageRegistry
from scantopath.storage.session_store import SessionStore
from scantopath.acquisition.sources import SyntheticSource


def build_v1(root: Path) -> None:
    with MetadataStore(root) as store:
        store.create_project('old-prj', 'Dự án cũ')
        store.create_specimen('old-spec', 'old-prj', 'Chi tiết cũ')
        store.create_scan_session('old-ses', 'old-spec', 'Phiên quét cũ')


def build_v2(root: Path) -> ProjectWorkspaceService:
    build_v1(root)
    NumberedStorageRegistry.migrate_database(root)
    return ProjectWorkspaceService(root)


def test_import_does_not_open_db_or_import_ui(tmp_path):
    code = ('import sys; from scantopath.application.projects import ProjectWorkspaceService; '
            'assert "PySide6" not in sys.modules; '
            'assert "scantopath.ui.main" not in sys.modules; '
            'print("import_isolated")')
    proc = subprocess.run([sys.executable, '-c', code], cwd=tmp_path,
                          capture_output=True, text=True, timeout=20)
    assert proc.returncode == 0, proc.stderr
    assert 'import_isolated' in proc.stdout
    assert list(tmp_path.iterdir()) == []


def test_missing_root_refuses_to_create_database(tmp_path):
    root = tmp_path / 'nonexistent'
    with pytest.raises(StoreNotOpenError):
        ProjectWorkspaceService(root)
    assert not root.exists()
    root.mkdir()
    with pytest.raises(StoreNotOpenError):
        ProjectWorkspaceService(root)
    assert not (root / 'metadata.sqlite3').exists()


def test_v1_opt_in_read_only_and_no_automatic_migration(tmp_path):
    build_v1(tmp_path)
    before = (tmp_path / 'metadata.sqlite3').read_bytes()
    service = ProjectWorkspaceService(tmp_path)
    assert service.info.schema_version == 1
    assert not service.info.writable_with_codes
    assert service.list_projects()[0].storage.public_code is None
    assert service.get_project_tree('old-prj').specimens[0].sessions[0].label == 'Phiên quét cũ'
    assert (tmp_path / 'metadata.sqlite3').read_bytes() == before
    with pytest.raises(NumberedSchemaRequiredError):
        service.create_project('Cannot write on v1')
    with pytest.raises(NumberedSchemaRequiredError):
        service.assign_existing_codes()
    assert list((tmp_path / 'sessions').glob('**/*')) == [] if (tmp_path / 'sessions').exists() else True


def test_numbered_existing_legacy_is_not_auto_assigned(tmp_path):
    service = build_v2(tmp_path)
    assert service.info.numbered_available
    assert service.get_project_tree('old-prj').project.storage.state == 'unmapped'
    assert service.list_projects()[0].storage.public_code is None
    # A pure read cannot secretly allocate a code.
    with sqlite3.connect(tmp_path / 'metadata.sqlite3') as db:
        assert db.execute('SELECT count(*) FROM storage_projects').fetchone()[0] == 0


def test_explicit_assign_all_is_idempotent_and_survives_reopen(tmp_path):
    service = build_v2(tmp_path)
    first = dict(service.assign_existing_codes().assigned)
    assert first['project'] == first['specimen'] == first['session'] == 1
    assert first['capture'] == first['run'] == 0
    assert dict(service.assign_existing_codes().assigned) == dict.fromkeys(first, 0)
    new = ProjectWorkspaceService(tmp_path).get_project_tree('old-prj')
    assert new.project.storage.public_path == 'P0001'
    assert new.specimens[0].specimen.storage.public_path == 'P0001/S0001'
    assert new.specimens[0].sessions[0].storage.public_path == 'P0001/S0001/T0001'
    assert not (tmp_path / '01_PROJECTS').exists()


def test_create_project_issues_code_and_returns_immutable_dto(tmp_path):
    service = build_v2(tmp_path)
    obj = service.create_project('Dự án mới', 'Mô tả', project_id='prj-new')
    assert obj.project_id == 'prj-new' and obj.name == 'Dự án mới'
    assert obj.storage.public_code == 'P0001'
    assert obj.storage.relative_path == '01_PROJECTS/P0001'
    assert obj.storage.state == 'not_materialized'
    with pytest.raises(FrozenInstanceError):
        obj.name = 'Hacked'
    assert service.get_project_tree('prj-new').project == obj


def test_create_project_generates_unique_internal_ids(tmp_path):
    service = build_v2(tmp_path)
    a = service.create_project('A')
    b = service.create_project('B')
    assert a.project_id != b.project_id
    assert a.storage.public_code == 'P0001' and b.storage.public_code == 'P0002'
    assert len(a.project_id) == 32


def test_project_update_keeps_code_and_slug_stable(tmp_path):
    service = build_v2(tmp_path)
    p = service.create_project('Trước', project_id='p1')
    changed = service.update_project('p1', name='Tên mới')
    assert changed.name == 'Tên mới'
    assert changed.storage == p.storage
    assert ProjectWorkspaceService(tmp_path).list_projects()[-1].name == 'Tên mới'


def test_specimen_session_crud_tree_and_parent_scoped_codes(tmp_path):
    service = build_v2(tmp_path)
    p1 = service.create_project('P1', project_id='p1')
    p2 = service.create_project('P2', project_id='p2')
    s1 = service.create_specimen(p1.project_id, 'Trục', specimen_id='s1')
    s2 = service.create_specimen(p2.project_id, 'Trục thứ 2', specimen_id='s2')
    assert s1.storage.public_path == 'P0001/S0001'
    assert s2.storage.public_path == 'P0002/S0001'
    t1 = service.create_session('s1', 'Quét 1', session_id='t1')
    assert t1.storage.public_path == 'P0001/S0001/T0001'
    assert service.get_project_tree('p1').specimens[0].sessions[0].session_id == 't1'
    with pytest.raises(LookupError):
        service.create_specimen('absent', 'Orphan')
    assert service.close_session('s1', 't1').state == 'closed'
    with pytest.raises(ValueError):
        service.close_session('s1', 't1')


def test_update_specimen_rejects_wrong_owner_before_mutation(tmp_path):
    service = build_v2(tmp_path)
    service.create_project('P1', project_id='p1')
    service.create_project('P2', project_id='p2')
    service.create_specimen('p1', 'Original', specimen_id='s1')
    with pytest.raises(LookupError):
        service.update_specimen('p2', 's1', label='Must not commit')
    assert service.get_project_tree('p1').specimens[0].specimen.label == 'Original'
    updated = service.update_specimen('p1', 's1', label='Updated')
    assert updated.label == 'Updated' and updated.storage.public_code == 'S0001'


def test_close_session_wrong_parent_no_state_change(tmp_path):
    service = build_v2(tmp_path)
    service.create_project('P', project_id='p')
    service.create_specimen('p', 'A', specimen_id='s1')
    service.create_specimen('p', 'B', specimen_id='s2')
    service.create_session('s1', 'Scan', session_id='t1')
    with pytest.raises(LookupError):
        service.close_session('s2', 't1')
    assert service.get_project_tree('p').specimens[0].sessions[0].state == 'open'


def test_invalid_create_does_not_leave_phantom_code(tmp_path):
    service = build_v2(tmp_path)
    with pytest.raises(ValueError):
        service.create_project('  ', project_id='invalid')
    with sqlite3.connect(tmp_path / 'metadata.sqlite3') as db:
        assert db.execute('SELECT count(*) FROM storage_projects').fetchone()[0] == 0
    with pytest.raises(ValueError):
        service.create_project('X', project_id='../unsafe')


def test_failed_code_assign_surfaces_recoverable_persisted_identity(tmp_path, monkeypatch):
    service = build_v2(tmp_path)
    def fail(*_args):
        raise OSError('simulated numbering outage')
    monkeypatch.setattr(service._numbered, 'assign', fail)
    with pytest.raises(NumberingPendingError) as raised:
        service.create_project('Persistent', project_id='pending')
    assert raised.value.entity_type == 'project'
    assert raised.value.internal_id == 'pending'
    assert service.get_project_tree('pending').project.storage.state == 'unmapped'
    with pytest.raises(ValueError):
        service.create_project('Do not repeat', project_id='pending')
    recovered = ProjectWorkspaceService(tmp_path).assign_code('project', 'pending')
    assert recovered.public_code == 'P0001'


def test_explicit_assign_code_rejects_unknown_and_unknown_kind(tmp_path):
    service = build_v2(tmp_path)
    with pytest.raises(LookupError):
        service.assign_code('project', 'does-not-exist')
    with pytest.raises(ValueError):
        service.assign_code('bad', 'some')


def test_list_events_are_immutable_json_snapshots(tmp_path):
    service = build_v2(tmp_path)
    service.create_project('Event', project_id='eventp')
    events = service.list_events(limit=20)
    assert any(x.action == 'project.created' for x in events)
    assert any(x.action == 'storage.code.assigned' for x in events)
    for x in events:
        assert isinstance(json.loads(x.details_json), dict)
    with pytest.raises(ValueError):
        service.list_events(limit=0)


def test_legacy_capture_is_readable_and_checksum_explicit(tmp_path):
    build_v1(tmp_path)
    path = SessionStore(tmp_path).commit(SyntheticSource().capture(), 'old-ses', 'old-spec')
    with MetadataStore(tmp_path) as db:
        c = db.register_capture(path)
    old_bytes = (path / 'metadata.json').read_bytes()
    service = ProjectWorkspaceService(tmp_path)
    got = service.get_capture(c['capture_id'])
    assert got.data_state == UiDataState.FIXTURE
    assert got.storage.state == 'legacy_unmapped'
    assert got.storage.relative_path == c['relative_path']
    assert service.get_capture(c['capture_id'], verify_raw=True).storage.state == 'verified'
    assert (path / 'metadata.json').read_bytes() == old_bytes
    assert service.get_project_tree('old-prj').specimens[0].sessions[0].captures[0].capture_id == c['capture_id']


def test_numbered_legacy_capture_display_and_integrity(tmp_path):
    build_v1(tmp_path)
    path = SessionStore(tmp_path).commit(SyntheticSource().capture(), 'old-ses', 'old-spec')
    with MetadataStore(tmp_path) as db:
        c = db.register_capture(path)
    NumberedStorageRegistry.migrate_database(tmp_path)
    service = ProjectWorkspaceService(tmp_path)
    service.assign_existing_codes()
    capture = service.get_capture(c['capture_id'])
    assert capture.storage.public_path == 'P0001/S0001/T0001/C0001'
    assert capture.storage.layout_version == 1
    assert capture.storage.state == 'not_checked'
    assert service.get_capture(c['capture_id'], verify_raw=True).storage.state == 'verified'
    assert path.exists()


def test_capture_corruption_is_not_reported_as_valid(tmp_path):
    build_v1(tmp_path)
    path = SessionStore(tmp_path).commit(SyntheticSource().capture(), 'old-ses', 'old-spec')
    with MetadataStore(tmp_path) as db:
        c = db.register_capture(path)
    (path / 'depth.npy').write_bytes(b'broken')
    service = ProjectWorkspaceService(tmp_path)
    with pytest.raises(Exception):
        service.get_capture(c['capture_id'], verify_raw=True)
    assert service.get_capture(c['capture_id']).data_state == UiDataState.FIXTURE


def test_processing_run_is_metadata_reference_not_generated_artifact(tmp_path):
    build_v1(tmp_path)
    path = SessionStore(tmp_path).commit(SyntheticSource().capture(), 'old-ses', 'old-spec')
    with MetadataStore(tmp_path) as db:
        cap = db.register_capture(path)
        run = db.create_processing_run(run_id='run1', session_id='old-ses', stage='filter',
                                        algorithm='fixture', version='v1',
                                        input_capture_ids=[cap['capture_id']],
                                        parameters={'dry_run': True})
        db.start_processing_run('run1')
        db.finish_processing_run('run1', state='succeeded', output_files=['not-created.ply'])
    NumberedStorageRegistry.migrate_database(tmp_path)
    service = ProjectWorkspaceService(tmp_path)
    service.assign_existing_codes()
    result = service.get_processing_run('run1')
    assert result.storage.public_path == 'P0001/S0001/T0001/R0001'
    assert result.output_files == ('not-created.ply',)
    assert not (tmp_path / 'not-created.ply').exists()
    assert json.loads(result.parameters_json) == {'dry_run': True}
    assert service.get_project_tree('old-prj').specimens[0].sessions[0].processing_runs[0] == result


def test_unrecognized_database_schema_is_rejected(tmp_path):
    build_v1(tmp_path)
    with sqlite3.connect(tmp_path / 'metadata.sqlite3') as db:
        db.execute('PRAGMA user_version=999')
    with pytest.raises(RuntimeError):
        ProjectWorkspaceService(tmp_path)


def test_service_read_only_navigation_never_materializes_numbered_directories(tmp_path):
    service = build_v2(tmp_path)
    for _ in range(3):
        service.list_projects()
        service.get_project_tree('old-prj')
    assert not (tmp_path / '01_PROJECTS').exists()
    assert not (tmp_path / '00_INDEX' / 'catalog.csv').exists()


def test_numbered_raw_v2_is_checked_without_claiming_metric_accuracy(tmp_path):
    from tests.support.raw_fixture import raw
    service = build_v2(tmp_path)
    numbered = NumberedStorageRegistry(tmp_path)
    packet = raw(session='old-ses', specimen='old-spec', capture_id='new-packet')
    numbered.reserve_capture('new-packet', 'old-ses', 'old-spec')
    physical = numbered.write_reserved_capture(packet)
    numbered.register_reserved_capture('new-packet')
    original = (physical / 'metadata.json').read_bytes()
    captured = service.get_capture('new-packet', verify_raw=True)
    assert captured.storage.public_path == 'P0001/S0001/T0001/C0001'
    assert captured.storage.layout_version == 2
    assert captured.storage.state == 'verified'
    assert captured.data_state == UiDataState.FIXTURE
    assert (physical / 'metadata.json').read_bytes() == original
    assert service.get_project_tree('old-prj').specimens[0].sessions[0].captures[0] == service.get_capture('new-packet')
    (physical / 'depth.y16').write_bytes(b'corrupted')
    with pytest.raises(ValueError):
        service.get_capture('new-packet', verify_raw=True)
