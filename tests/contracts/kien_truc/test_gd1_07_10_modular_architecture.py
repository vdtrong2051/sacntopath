"""07.10 structural+runtime contract tests, no Qt/camera required."""
from pathlib import Path
import ast
import importlib
import sqlite3

import pytest

from scantopath.application.projects import ProjectWorkspaceService as LegacyService
from scantopath.application.projects.models import ProjectTree as LegacyTree
from scantopath.modules.project_workspace.application.models import ProjectTree
from scantopath.modules.project_workspace.application.service import ProjectWorkspaceService
from scantopath.modules.project_workspace.application.ports import (
    ProjectReadPort, ProjectWritePort, AuditReadPort, CaptureInspectionPort,
)
from scantopath.metadata.store import MetadataStore


ROOT = Path(__file__).resolve().parents[3]


def test_legacy_facades_are_identical_not_copied():
    assert LegacyService is ProjectWorkspaceService
    assert LegacyTree is ProjectTree
    from scantopath.ui.projects.forms_contract import ProjectEditCommand
    from scantopath.modules.project_workspace.presentation.forms_contract import ProjectEditCommand as NewCommand
    from scantopath.ui.projects.presentation import ProjectLoadBundle
    from scantopath.modules.project_workspace.presentation.presenter import ProjectLoadBundle as NewBundle
    assert ProjectEditCommand is NewCommand
    assert ProjectLoadBundle is NewBundle


def test_read_write_and_audit_ports_structurally_implemented(tmp_path):
    with MetadataStore(tmp_path):
        pass
    service = ProjectWorkspaceService(tmp_path)
    # Structural Protocol attributes, verified here without forcing runtime inheritance.
    for protocol, operations in (
        (ProjectReadPort, ('list_projects', 'get_project_tree')),
        (ProjectWritePort, ('create_project', 'create_specimen', 'update_project', 'close_session')),
        (AuditReadPort, ('list_events',)),
        (CaptureInspectionPort, ('inspect_capture', 'get_capture')),
    ):
        assert protocol.__module__.startswith('scantopath.modules.project_workspace')
        assert all(callable(getattr(service, m)) for m in operations)
    assert service.info.schema_version == 1


def test_repository_factory_injection_keeps_existing_read_only_db(tmp_path):
    with MetadataStore(tmp_path):
        pass
    before = (tmp_path / 'metadata.sqlite3').read_bytes()
    called = []
    class FakeMetadata:
        def __init__(self, root):
            assert root == tmp_path.resolve()
            called.append('opened')
        def __enter__(self):return self
        def __exit__(self, *args):return False
        def list_projects(self):return []
    def forbidden_registry(_):
        raise AssertionError('Registry should never open for SQLite v1')
    service = ProjectWorkspaceService(tmp_path, metadata_factory=FakeMetadata,
                                      registry_factory=forbidden_registry)
    assert service.list_projects() == ()
    assert called == ['opened', 'opened']
    assert (tmp_path / 'metadata.sqlite3').read_bytes() == before


def test_project_controller_is_feature_owned_and_shell_only_delegates():
    shell = (ROOT/'src/scantopath/ui/shell/main_window.py').read_text(encoding='utf8')
    feature = (ROOT/'src/scantopath/modules/project_workspace/presentation/controller.py').read_text(encoding='utf8')
    shell_ast = ast.parse(shell)
    feature_ast = ast.parse(feature)
    shell_class = next(n for n in shell_ast.body if isinstance(n,ast.ClassDef) and n.name=='ScanToPathMainWindow')
    module_class = next(n for n in feature_ast.body if isinstance(n,ast.ClassDef) and n.name=='ProjectWorkspaceController')
    assert 'ProjectWorkspaceController(self)' in shell
    assert len(shell.splitlines()) < 500
    assert len([n for n in module_class.body if isinstance(n,ast.FunctionDef)]) >= 20
    assert any(n.name == '_on_project_loaded' for n in module_class.body if isinstance(n,ast.FunctionDef))
    assert not any('metadata.store' in line or 'sqlite3' in line for line in shell.splitlines() if line.strip().startswith('from '))


def test_architecture_import_gate_zero_violations():
    import sys
    sys.path.insert(0,str(ROOT/'scripts'))
    try:
        from check_architecture_boundaries import scan
        assert scan(ROOT) == []
    finally:
        sys.path.remove(str(ROOT/'scripts'))


def test_architecture_guard_catches_new_cross_layer_dependency(tmp_path):
    import sys
    sys.path.insert(0,str(ROOT/'scripts'))
    try:
        from check_architecture_boundaries import scan
        folder=tmp_path/'src/scantopath/domain';folder.mkdir(parents=True)
        (folder/'bad.py').write_text('from PySide6.QtWidgets import QWidget\n',encoding='utf8')
        assert ('domain/bad.py',1,'PySide6.QtWidgets') in scan(tmp_path)
    finally:
        sys.path.remove(str(ROOT/'scripts'))


def test_shell_module_import_remains_opt_in_when_pyside_is_installed():
    pytest.importorskip('PySide6')
    import subprocess,sys,os,json
    env=os.environ.copy()
    env['PYTHONPATH']=str(ROOT/'src')
    source='''import importlib,sys,json
importlib.import_module('scantopath.ui.shell.main_window')
print(json.dumps({'sql': 'scantopath.metadata.store' in sys.modules,
  'camera': 'scantopath.acquisition.native' in sys.modules}))'''
    result = subprocess.run([sys.executable,'-c',source],env=env,capture_output=True,text=True,check=True)
    assert json.loads(result.stdout.strip()) == {'sql':False,'camera':False}
