"""GD2-UXH-01.3: immutable, resource-free active workflow identity.

Selection is a database identity reference (not display code). This contract
has no Qt, SQLite, RAW, VTK, filesystem or persistence dependencies.
"""
from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from types import MappingProxyType
from typing import Mapping

from scantopath.application.contracts.models import SelectionRef


class WorkflowStatus(str, Enum):
    EMPTY = "empty"
    SUSPENDED = "suspended"
    READY = "ready"


class WorkflowIntent(str, Enum):
    VIEW_RAW = "view_raw"
    VIEW_3D = "view_3d"
    MEASURE_AB = "measure_ab"
    START_CAPTURE = "start_capture"
    OPEN_PROCESSING = "open_processing"


@dataclass(frozen=True, slots=True)
class ActiveWorkflowContext:
    store_root: str | None = None
    selection: SelectionRef | None = None
    project_id: str | None = None
    specimen_id: str | None = None
    session_id: str | None = None
    capture_id: str | None = None
    status: WorkflowStatus = WorkflowStatus.EMPTY
    revision: int = 0

    def __post_init__(self) -> None:
        if type(self.revision) is not int or self.revision < 0:
            raise ValueError("WORKFLOW_REVISION_INVALID")
        if self.store_root is not None and (type(self.store_root) is not str or not self.store_root.strip()):
            raise ValueError("WORKFLOW_STORE_INVALID")
        if self.selection is not None and not isinstance(self.selection, SelectionRef):
            raise TypeError("WORKFLOW_SELECTION_INVALID")
        if type(self.status) is not WorkflowStatus:
            raise TypeError("WORKFLOW_STATUS_INVALID")
        if self.status is WorkflowStatus.EMPTY and self.selection is not None:
            raise ValueError("WORKFLOW_EMPTY_WITH_SELECTION")
        if self.status is WorkflowStatus.READY and self.store_root is None:
            raise ValueError("WORKFLOW_READY_WITHOUT_STORE")
        if self.capture_id is not None and (self.session_id is None or self.specimen_id is None or self.project_id is None):
            raise ValueError("WORKFLOW_CAPTURE_LINEAGE_INVALID")
        if self.selection is not None and self.selection.entity_type == "capture" and self.status is WorkflowStatus.READY:
            if self.selection.entity_id != self.capture_id:
                raise ValueError("WORKFLOW_CAPTURE_SELECTION_MISMATCH")

    @property
    def actionable_capture_id(self) -> str | None:
        if self.status is WorkflowStatus.READY and self.selection is not None and self.selection.entity_type == "capture":
            return self.capture_id
        return None


@dataclass(frozen=True, slots=True)
class WorkflowLineage:
    """IDs sourced only from loaded ProjectTree, never guessed from display codes."""
    project_id: str | None
    specimen_id: str | None = None
    session_id: str | None = None
    capture_id: str | None = None


class WorkflowContextModel:
    """Pure state reducer with single revision and fail-closed invalidation."""
    def __init__(self) -> None:
        self._current = ActiveWorkflowContext()
        self._lineage: Mapping[SelectionRef, WorkflowLineage] = MappingProxyType({})
        self._candidate: SelectionRef | None = None

    @property
    def current(self) -> ActiveWorkflowContext:
        return self._current

    @property
    def candidate(self) -> SelectionRef | None:
        return self._candidate

    def begin_load(self, requested_root: str) -> ActiveWorkflowContext:
        if type(requested_root) is not str or not requested_root.strip():
            raise ValueError("WORKFLOW_STORE_INVALID")
        current = self._current
        self._candidate = current.selection if current.store_root == requested_root else None
        self._lineage = MappingProxyType({})
        self._current = ActiveWorkflowContext(store_root=requested_root, status=WorkflowStatus.SUSPENDED,
                                              revision=current.revision + 1)
        return self._current

    def activate(self, root: str, mapping: Mapping[SelectionRef, WorkflowLineage],
                 selected: SelectionRef | None) -> ActiveWorkflowContext:
        if type(root) is not str or not root.strip():
            raise ValueError("WORKFLOW_STORE_INVALID")
        if not isinstance(mapping, Mapping) or not all(isinstance(k, SelectionRef) and isinstance(v, WorkflowLineage)
                                                        for k, v in mapping.items()):
            raise TypeError("WORKFLOW_LINEAGE_INVALID")
        if selected is not None and selected not in mapping:
            selected = None
        self._lineage = MappingProxyType(dict(mapping))
        self._candidate = None
        self._current = self._make(root, selected, self._current.revision + 1)
        return self._current

    def select(self, selection: SelectionRef | None) -> ActiveWorkflowContext:
        current = self._current
        if current.status is not WorkflowStatus.READY:
            return current
        if selection is not None and selection not in self._lineage:
            selection = None  # fail closed for orphan/mismatched entity
        if current.selection == selection:
            return current
        self._current = self._make(current.store_root, selection, current.revision + 1)
        return self._current

    def invalidate(self) -> ActiveWorkflowContext:
        self._candidate = None
        self._lineage = MappingProxyType({})
        self._current = ActiveWorkflowContext(revision=self._current.revision + 1)
        return self._current

    def _make(self, root: str, selection: SelectionRef | None, revision: int) -> ActiveWorkflowContext:
        lineage = self._lineage[selection] if selection is not None else WorkflowLineage(None)
        return ActiveWorkflowContext(store_root=root, selection=selection, project_id=lineage.project_id,
                                     specimen_id=lineage.specimen_id, session_id=lineage.session_id,
                                     capture_id=lineage.capture_id, status=WorkflowStatus.READY, revision=revision)


def lineage_from_project_trees(trees) -> Mapping[SelectionRef, WorkflowLineage]:
    """ProjectReadBundle trees -> identity map, no inferred IDs or I/O."""
    mapping: dict[SelectionRef, WorkflowLineage] = {}
    for tree in trees:
        project = tree.project.project_id
        mapping[SelectionRef("project", project)] = WorkflowLineage(project)
        for node in tree.specimens:
            specimen = node.specimen.specimen_id
            mapping[SelectionRef("specimen", specimen)] = WorkflowLineage(project, specimen)
            for session in node.sessions:
                sid = session.session_id
                mapping[SelectionRef("scan_session", sid)] = WorkflowLineage(project, specimen, sid)
                for capture in session.captures:
                    cid = capture.capture_id
                    mapping[SelectionRef("capture", cid)] = WorkflowLineage(project, specimen, sid, cid)
                for run in getattr(session, "processing_runs", ()):
                    mapping[SelectionRef("processing_run", run.run_id)] = WorkflowLineage(project, specimen, sid)
    return MappingProxyType(mapping)
