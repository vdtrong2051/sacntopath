"""UXH-01.3 pure model: no Qt, SQLite or VTK runtime."""
from dataclasses import FrozenInstanceError
from types import SimpleNamespace as NS

import pytest

from scantopath.application.contracts.models import SelectionRef
from scantopath.application.contracts.workflow_context import (
    ActiveWorkflowContext, WorkflowContextModel, WorkflowLineage,
    WorkflowIntent, WorkflowStatus, lineage_from_project_trees,
)


def fixture_tree():
    run = NS(run_id="run-1")
    capture = NS(capture_id="cap-a")
    session = NS(session_id="t1", captures=(capture,), processing_runs=(run,))
    specimen = NS(specimen=NS(specimen_id="s1"), sessions=(session,))
    return (NS(project=NS(project_id="p1"), specimens=(specimen,)),)


def test_lineage_is_from_loaded_hierarchy_not_display_codes():
    m = lineage_from_project_trees(fixture_tree())
    assert m[SelectionRef('capture', 'cap-a')] == WorkflowLineage('p1', 's1', 't1', 'cap-a')
    assert m[SelectionRef('processing_run', 'run-1')].session_id == 't1'
    assert len(m) == 5
    with pytest.raises(TypeError):
        m[SelectionRef('capture', 'foreign')] = WorkflowLineage('p2')


def test_context_lifecycle_and_revision_are_monotonic():
    m = WorkflowContextModel()
    assert m.current.status is WorkflowStatus.EMPTY
    a = m.begin_load('store-A')
    assert a.status is WorkflowStatus.SUSPENDED
    ctx = m.activate('store-A', lineage_from_project_trees(fixture_tree()), SelectionRef('capture', 'cap-a'))
    assert ctx.status is WorkflowStatus.READY and ctx.actionable_capture_id == 'cap-a'
    assert ctx.project_id == 'p1' and ctx.specimen_id == 's1' and ctx.session_id == 't1'
    assert m.select(SelectionRef('capture', 'cap-a')) is ctx
    x = m.select(SelectionRef('scan_session','t1'))
    assert x.revision == ctx.revision+1 and x.actionable_capture_id is None
    assert x.capture_id is None
    assert m.select(SelectionRef('capture', 'absent')).selection is None


def test_reload_suspend_restore_and_different_store_fail_closed():
    m = WorkflowContextModel()
    tree = lineage_from_project_trees(fixture_tree())
    m.begin_load('A')
    m.activate('A', tree, SelectionRef('capture','cap-a'))
    epoch = m.current.revision
    suspended = m.begin_load('A')
    assert m.candidate == SelectionRef('capture','cap-a')
    assert suspended.status is WorkflowStatus.SUSPENDED and suspended.actionable_capture_id is None
    assert m.select(SelectionRef('capture','cap-a')) is suspended
    current = m.activate('A', tree, m.candidate)
    assert current.revision > epoch and current.actionable_capture_id == 'cap-a'
    m.begin_load('B')
    assert m.candidate is None
    new = m.activate('B', tree, None)
    assert new.selection is None and new.actionable_capture_id is None


def test_missing_capture_after_reload_cannot_be_restored():
    m = WorkflowContextModel()
    key = SelectionRef('capture','cap-a')
    m.begin_load('A');m.activate('A',lineage_from_project_trees(fixture_tree()),key)
    m.begin_load('A')
    lineage = {SelectionRef('project', 'p1'): WorkflowLineage('p1')}
    ctx = m.activate('A', lineage, m.candidate)
    assert ctx.selection is None and ctx.actionable_capture_id is None


def test_invalid_context_and_no_mutation():
    c = ActiveWorkflowContext(store_root='A',status=WorkflowStatus.READY,revision=1)
    with pytest.raises(FrozenInstanceError):
        c.revision = 2
    with pytest.raises(ValueError,match='LINEAGE'):
        ActiveWorkflowContext(store_root='A',status=WorkflowStatus.READY,capture_id='c')
    with pytest.raises(ValueError,match='REVISION'):
        ActiveWorkflowContext(revision=True)
    assert WorkflowIntent.VIEW_3D.value == 'view_3d'
    assert WorkflowIntent.MEASURE_AB.value == 'measure_ab'


def test_revision_invalidates_pending_work_even_if_capture_id_reused():
    m=WorkflowContextModel();mapping=lineage_from_project_trees(fixture_tree());key=SelectionRef('capture','cap-a')
    m.begin_load('A');c=m.activate('A',mapping,key);saved=c.revision
    m.begin_load('A');m.activate('A',mapping,key)
    assert m.current.capture_id == 'cap-a' and m.current.revision != saved
