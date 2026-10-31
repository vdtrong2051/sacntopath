"""GD2-UXH-01.3: Qt glue for validated workflow identity, not a second Store."""
from __future__ import annotations

from PySide6.QtCore import QObject, Signal, Slot

from scantopath.application.contracts.workflow_context import (
    ActiveWorkflowContext, WorkflowContextModel, WorkflowStatus,
    lineage_from_project_trees,
)
from scantopath.application.contracts.models import SelectionRef


class WorkflowContextController(QObject):
    changed = Signal(object)

    def __init__(self, view):
        super().__init__(view)
        self.view = view
        self.model = WorkflowContextModel()
        view.project_explorer.selection_changed.connect(self._selection_changed)
        # Attached AFTER ProjectReadCoordinator. The Qt loaded slots build the
        # Explorer tree synchronously before we validate the selected identity.
        view.project_loader.loaded.connect(self._loaded)
        view.project_loader.failed.connect(self._failed)

    @property
    def current(self) -> ActiveWorkflowContext:
        return self.model.current

    @property
    def revision(self) -> int:
        return self.model.current.revision

    def begin_store_load(self, root: str) -> None:
        self.changed.emit(self.model.begin_load(root))

    def restore_candidate(self, root: str) -> SelectionRef | None:
        if self.current.status is WorkflowStatus.SUSPENDED and self.current.store_root == root:
            return self.model.candidate
        return None

    @Slot(object)
    def _loaded(self, bundle) -> None:
        root = bundle.info.root
        if self.current.status is not WorkflowStatus.SUSPENDED or self.current.store_root != root:
            return
        selection = self.view.project_explorer.selection
        current = self.model.activate(root, lineage_from_project_trees(bundle.trees), selection)
        if selection is not None and current.selection is None:
            self.view.project_explorer.clear_selection()
        self.changed.emit(current)

    @Slot(str)
    def _failed(self, _message: str) -> None:
        self.changed.emit(self.model.invalidate())

    @Slot(object)
    def _selection_changed(self, selection) -> None:
        if selection is not None and not isinstance(selection, SelectionRef):
            return
        previous = self.model.current
        current = self.model.select(selection)
        if current is not previous:
            self.changed.emit(current)
