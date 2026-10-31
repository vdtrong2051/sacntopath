"""UXH-01.3 HMI integration; real numbered v2 Store, synthetic RAW only."""
from __future__ import annotations

import os
import pytest
os.environ.setdefault('QT_QPA_PLATFORM','offscreen')
pytest.importorskip('PySide6')

from scantopath.application.contracts import SelectionRef, WorkspaceId
from scantopath.application.contracts.workflow_context import WorkflowStatus
from tests.ui.capture.test_gd2_09_09_2_replay_tree import (
    qapp, window, _seed, _load, _capture_item, _until,
)


def test_workspace_switch_twenty_times_preserves_capture_without_replay(qapp, window, tmp_path):
    root=tmp_path/'switch'
    _seed(root, ids=('cap-a', 'cap-b'))
    _load(qapp,window,root)
    window.project_explorer.tree.setCurrentItem(_capture_item(window,'cap-a'))
    qapp.processEvents()
    assert window.workflow_context.current.actionable_capture_id == 'cap-a'
    rev=window.workflow_context.revision
    for index in range(20):
        dest=(WorkspaceId.PROJECTS,WorkspaceId.CAPTURE,WorkspaceId.INSPECT3D,WorkspaceId.PROCESSING)[index%4]
        window._navigate(dest)
        qapp.processEvents()
        assert window.project_explorer.selection == SelectionRef('capture','cap-a')
        assert window.navigation.selection == window.project_explorer.selection
        assert window.workflow_context.revision == rev
    assert window.capture_preview.context.capture_id == 'cap-a'
    assert not window.capture_preview.busy


def test_reloading_same_store_restores_capture_without_replay(qapp,window,tmp_path):
    root=tmp_path/'reload'
    _seed(root,ids=('cap-a',))
    _load(qapp,window,root)
    window.project_explorer.tree.setCurrentItem(_capture_item(window,'cap-a'))
    original=window.workflow_context.revision
    window._reload_project_store()
    _until(qapp,lambda:not window.project_loader.busy)
    assert window.project_explorer.selection == SelectionRef('capture','cap-a')
    assert window.workflow_context.current.status is WorkflowStatus.READY
    assert window.workflow_context.current.actionable_capture_id == 'cap-a'
    assert window.workflow_context.revision>original
    assert not window.capture_preview.busy


def test_switching_store_clears_old_capture_context(qapp,window,tmp_path):
    old=tmp_path/'old';new=tmp_path/'new'
    _seed(old,ids=('cap-a',));_seed(new,ids=('cap-b',))
    _load(qapp,window,old)
    window.project_explorer.tree.setCurrentItem(_capture_item(window,'cap-a'))
    assert window.workflow_context.current.capture_id == 'cap-a'
    _load(qapp,window,new)
    assert window.workflow_context.current.capture_id is None
    assert window.workflow_context.current.selection is None
    assert window.capture_preview.context is None


def test_selecting_parent_invalidates_actionable_capture(qapp,window,tmp_path):
    root=tmp_path/'parent'
    _seed(root,ids=('cap-a',))
    _load(qapp,window,root)
    item=_capture_item(window,'cap-a')
    window.project_explorer.tree.setCurrentItem(item)
    assert window.workflow_context.current.actionable_capture_id == 'cap-a'
    window.project_explorer.tree.setCurrentItem(item.parent())
    assert window.workflow_context.current.actionable_capture_id is None
    assert window.capture_preview.context is None


def test_stale_geometry_result_rejected_after_selection_revision_change(qapp,window,tmp_path):
    root=tmp_path/'stale-geometry'
    _seed(root,ids=('cap-a','cap-b'))
    _load(qapp,window,root)
    explorer=window.project_explorer.tree
    explorer.setCurrentItem(_capture_item(window,'cap-a'))
    request_epoch=window.workflow_context.revision
    window.geometry_preview._workflow_revision_at_request=request_epoch
    explorer.setCurrentItem(_capture_item(window,'cap-b'))
    qapp.processEvents()
    assert window.workflow_context.revision != request_epoch
    class Scratch:
        cleaned=False
        def cleanup(self):
            self.cleaned=True
    scratch=Scratch()
    window.geometry_preview._ready(None,scratch,None,None)
    assert scratch.cleaned
    assert window.viewer3d is None  # no stale Preview navigation
