"""07.11 cross-boundary acceptance: same contracts, smaller responsibilities."""
from __future__ import annotations
import importlib
from pathlib import Path
import inspect
import sqlite3
import subprocess
import sys

import pytest
from scantopath.application.projects import (
    ProjectWorkspaceService, NumberingPendingError,
    NumberedSchemaRequiredError, StoreNotOpenError,
)
from scantopath.metadata.store import MetadataStore
from scantopath.storage.numbered import NumberedStorageRegistry
from scantopath.modules.project_workspace.application import service as feature_service
from scantopath.modules.project_workspace.application.commands import ProjectCommands
from scantopath.modules.project_workspace.application.queries import ProjectQueries
from scantopath.modules.project_workspace.application.inspection import CaptureIntegrityChecker
from scantopath.modules.project_workspace.application.records import ProjectRecordMapper
from scantopath.modules.project_workspace.application.context import WorkspaceContext
from scantopath.modules.project_workspace.application.errors import NumberingPendingError as FeatureNumberingPendingError


ROOT = Path(__file__).resolve().parents[3]


def test_original_compatibility_facade_class_and_error_identical():
    assert ProjectWorkspaceService is feature_service.ProjectWorkspaceService
    assert NumberingPendingError is FeatureNumberingPendingError
    assert NumberedSchemaRequiredError is feature_service.NumberedSchemaRequiredError
    assert StoreNotOpenError is feature_service.StoreNotOpenError


def test_public_contract_preserved():
    methods = ('list_projects', 'get_project_tree', 'get_capture', 'inspect_capture',
               'get_processing_run', 'list_events', 'assign_code',
               'assign_existing_codes', 'create_project', 'update_project',
               'create_specimen', 'update_specimen', 'create_session',
               'update_session', 'close_session')
    assert all(callable(getattr(ProjectWorkspaceService, name)) for name in methods)
    assert str(inspect.signature(ProjectWorkspaceService.create_project)).find('project_id') > 0
    assert str(inspect.signature(ProjectWorkspaceService.get_capture)).find('verify_raw') > 0


def test_service_is_composed_not_a_legacy_giant_class(tmp_path):
    with MetadataStore(tmp_path):
        pass
    s = ProjectWorkspaceService(tmp_path)
    assert isinstance(s._context, WorkspaceContext)
    assert isinstance(s._mapper, ProjectRecordMapper)
    assert isinstance(s._queries, ProjectQueries)
    assert isinstance(s._commands, ProjectCommands)
    assert isinstance(s._inspection, CaptureIntegrityChecker)
    assert s.info.schema_version == 1
    assert s._context.root == tmp_path.resolve()


def test_read_v1_does_not_allocate_numbers_or_mutate_store(tmp_path):
    with MetadataStore(tmp_path) as db:
        db.create_project('existing', 'Tên dự án')
    original = (tmp_path / 'metadata.sqlite3').read_bytes()
    s = ProjectWorkspaceService(tmp_path)
    assert s.list_projects()[0].name == 'Tên dự án'
    assert s.get_project_tree('existing').project.storage.public_code is None
    assert (tmp_path / 'metadata.sqlite3').read_bytes() == original
    assert not (tmp_path / '01_PROJECTS').exists()
    with pytest.raises(NumberedSchemaRequiredError):
        s.create_project('not allowed')


def test_v2_mutations_delegate_without_renumber_on_update(tmp_path):
    with MetadataStore(tmp_path):
        pass
    NumberedStorageRegistry.migrate_database(tmp_path)
    s=ProjectWorkspaceService(tmp_path)
    p=s.create_project('Dự án', project_id='p1')
    spec=s.create_specimen('p1','Chi tiết',specimen_id='s1')
    session=s.create_session('s1','Lần 1',session_id='t1')
    assert [p.storage.public_code, spec.storage.public_code, session.storage.public_code] == ['P0001','S0001','T0001']
    assert s.update_project('p1',name='Dự án sau sửa').storage.public_code == 'P0001'
    assert s.update_specimen('p1','s1',label='Chi tiết mới').storage.public_code == 'S0001'
    assert s.update_session('s1','t1',label='Quét đổi tên').storage.public_code == 'T0001'
    assert s.close_session('s1','t1').state == 'closed'
    assert ProjectWorkspaceService(tmp_path).get_project_tree('p1').specimens[0].sessions[0].state == 'closed'


def test_bootstrap_rejects_missing_store_without_creating_db(tmp_path):
    with pytest.raises(StoreNotOpenError):
        ProjectWorkspaceService(tmp_path)
    assert not (tmp_path/'metadata.sqlite3').exists()


def test_module_import_never_eagerly_opens_database_or_qt(tmp_path):
    source = ('import sys; from scantopath.modules.project_workspace.application.service '
              'import ProjectWorkspaceService; '
              'assert "scantopath.metadata.store" not in sys.modules; '
              'assert "PySide6" not in sys.modules; print("isolated")')
    env={**__import__('os').environ,'PYTHONPATH':str(ROOT/'src')}
    output = subprocess.run([sys.executable,'-c',source],cwd=tmp_path,
                            env=env,capture_output=True,text=True,timeout=20,check=True)
    assert 'isolated' in output.stdout
    assert list(tmp_path.iterdir()) == []


def test_arch_guard_supports_relative_imports_and_nested_functions(tmp_path):
    sys.path.insert(0,str(ROOT/'scripts'))
    try:
        from check_architecture_boundaries import scan
        app=tmp_path/'src/scantopath/modules/new_feature/application'
        infra=tmp_path/'src/scantopath/modules/new_feature/infrastructure'
        app.mkdir(parents=True);infra.mkdir(parents=True)
        (app/'bad.py').write_text('def sneak():\n    from ..infrastructure import sqlite_backend\n',encoding='utf8')
        assert ('modules/new_feature/application/bad.py',2,
                'scantopath.modules.new_feature.infrastructure') in scan(tmp_path)
    finally:
        sys.path.remove(str(ROOT/'scripts'))


def test_arch_guard_rejects_direct_storage_and_qt_imports(tmp_path):
    sys.path.insert(0,str(ROOT/'scripts'))
    try:
        from check_architecture_boundaries import scan
        app=tmp_path/'src/scantopath/modules/another/application'
        app.mkdir(parents=True)
        (app/'bad.py').write_text('import sqlite3\nfrom scantopath.storage.numbered import NumberedStorageRegistry\nfrom PySide6.QtCore import QObject\n',encoding='utf8')
        found=scan(tmp_path)
        assert len(found)==3
    finally:
        sys.path.remove(str(ROOT/'scripts'))


def test_existing_repo_import_gate_is_clean():
    sys.path.insert(0,str(ROOT/'scripts'))
    try:
        from check_architecture_boundaries import scan
        assert scan(ROOT)==[]
    finally:
        sys.path.remove(str(ROOT/'scripts'))
