"""07.12: concrete behavior, API identity, immutability and architecture guard."""
from __future__ import annotations
import inspect
import json
from pathlib import Path
import sqlite3
import subprocess
import sys
import pytest
from scantopath.metadata.store import MetadataStore
from scantopath.metadata.schema import _Base
from scantopath.metadata.repos import (_ProjectRepository,_CaptureRepository,
                                      _ProcessingRepository,_AuditRepository)
from scantopath.storage.numbered import NumberedStorageRegistry, StorageLocation, CaptureReservation, _safe_path
from scantopath.storage.numbered_ops import (_CodeAssignments,_StorageResolver,
                                              _CaptureReservations,_SchemaMigration,_CatalogExport)

ROOT=Path(__file__).resolve().parents[1]


def test_metadata_facade_owns_one_engine_and_independent_repositories(tmp_path):
    with MetadataStore(tmp_path) as store:
        assert isinstance(store._projects,_ProjectRepository)
        assert isinstance(store._captures,_CaptureRepository)
        assert isinstance(store._runs,_ProcessingRepository)
        assert isinstance(store._audit,_AuditRepository)
        engines={id(x.engine) for x in (store._projects,store._captures,store._runs,store._audit)}
        assert engines=={id(store.engine)}
        store.create_project('x','Dự án')
        store.create_specimen('y','x','Mẫu')
        store.create_scan_session('z','y')
        assert store.get_project_tree('x')['specimens'][0]['sessions'][0]['session_id']=='z'
        assert store.list_projects()[0]['project_id']=='x'
        store.record_event(level='INFO',action='test.0712',entity_type='project',entity_id='x')
        assert store.list_events(limit=1)[0]['action']=='test.0712'


def test_metadata_v1_read_does_not_implicitly_migrate(tmp_path):
    with MetadataStore(tmp_path) as store:
        store.create_project('project-1','Mẫu')
    db=tmp_path/'metadata.sqlite3'
    with sqlite3.connect(db) as con:
        before=con.execute('PRAGMA user_version').fetchone()[0]
    with MetadataStore(tmp_path) as store:
        assert store.list_projects()[0]['name']=='Mẫu'
    with sqlite3.connect(db) as con:
        assert before==con.execute('PRAGMA user_version').fetchone()[0]==1
        assert 'storage_counters' not in {r[0] for r in con.execute("SELECT name FROM sqlite_master WHERE type='table'")}


def test_numbered_registry_composes_ops_without_auto_migrate(tmp_path):
    with MetadataStore(tmp_path) as store:
        store.create_project('p','Tên')
    with pytest.raises(RuntimeError,match='schema v2'):
        NumberedStorageRegistry(tmp_path)
    with sqlite3.connect(tmp_path/'metadata.sqlite3') as con:
        assert con.execute('PRAGMA user_version').fetchone()[0]==1
    backup=NumberedStorageRegistry.migrate_database(tmp_path)
    assert backup.is_file()
    registry=NumberedStorageRegistry(tmp_path)
    assert isinstance(registry._codes,_CodeAssignments)
    assert isinstance(registry._resolver,_StorageResolver)
    assert isinstance(registry._capturing,_CaptureReservations)
    assert isinstance(registry._catalog,_CatalogExport)
    assert all(part._registry is registry for part in (registry._codes,registry._resolver,registry._capturing,registry._catalog))
    loc=registry.assign('project','p')
    assert loc.public_path=='P0001'
    assert registry.resolve_id('project','p')==loc
    assert registry.assign('project','p')==loc
    assert NumberedStorageRegistry(tmp_path).resolve_public_path('P0001')==loc
    assert registry.export_catalog().is_file()


def test_public_types_and_old_metadata_seam():
    import scantopath.metadata.store as facade
    import scantopath.metadata.schema as schema
    import scantopath.storage.numbered_contracts as contracts
    from scantopath import metadata
    assert facade._Base is schema._Base
    assert facade._AuditEvent is schema._AuditEvent
    assert StorageLocation is contracts.StorageLocation
    assert CaptureReservation is contracts.CaptureReservation
    assert '_log' in facade.__dict__  # transactional audit fault injection is preserved
    assert hasattr(MetadataStore,'_run_dict')
    for method in ('assign','assign_all','resolve_id','resolve_public_path','reserve_capture',
                   'write_reserved_capture','register_reserved_capture','pending_reservations','export_catalog'):
        assert callable(getattr(NumberedStorageRegistry,method))


def test_static_quality_gate(tmp_path):
    sys.path.insert(0,str(ROOT/'scripts'))
    try:
        from check_07_12_quality import audit
        report=audit(ROOT)
    finally:
        sys.path.remove(str(ROOT/'scripts'))
    assert report['errors']==[]
    assert report['facades']['MetadataStore']['lines'] < 170
    assert report['facades']['NumberedStorageRegistry']['lines'] < 145
    assert report['facades']['ProjectWorkspaceController']['lines'] < 140


def test_v1_migration_error_does_not_edit_existing_database(tmp_path):
    with MetadataStore(tmp_path):pass
    NumberedStorageRegistry.migrate_database(tmp_path)
    with sqlite3.connect(tmp_path/'metadata.sqlite3') as con:
        assert con.execute('PRAGMA user_version').fetchone()[0]==2
    with pytest.raises(RuntimeError,match='Expected SQLite schema 1'):
        NumberedStorageRegistry.migrate_database(tmp_path)
    with sqlite3.connect(tmp_path/'metadata.sqlite3') as con:
        assert con.execute('PRAGMA user_version').fetchone()[0]==2


def test_qt_reader_presenter_relative_import_resolves():
    import importlib.util
    module='scantopath.modules.project_workspace.presentation.workflows.reading'
    assert importlib.util.resolve_name('..presenter',module.rsplit('.',1)[0]) == 'scantopath.modules.project_workspace.presentation.presenter'
    text=(ROOT/'src/scantopath/modules/project_workspace/presentation/workflows/reading.py').read_text()
    assert 'from ..presenter import project_rows' in text
