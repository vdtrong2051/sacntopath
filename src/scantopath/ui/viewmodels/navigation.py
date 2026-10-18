"""UI-facing navigation state, without importing Qt or persistence modules."""
from __future__ import annotations

from uuid import uuid4

from scantopath.application.contracts import (
    CommandOutcome, CommandRequest, CommandStatus, SelectionRef, WorkspaceId,
)
from scantopath.application.services import CommandService


class NavigationViewModel:
    """06.3 QMainWindow will call select_workspace and render state/outcome.

    No DB access or implicit I/O. Selection is an ID reference, not a loaded
    specimen, camera pose or a point cloud.
    """

    def __init__(self, commands: CommandService | None = None) -> None:
        self._commands = commands if commands is not None else CommandService()
        self._workspace = self._commands.navigation.current().workspace
        self._selection: SelectionRef | None = None
        self._last_outcome: CommandOutcome | None = None

    @property
    def workspace(self) -> WorkspaceId:
        return self._workspace

    @property
    def selection(self) -> SelectionRef | None:
        return self._selection

    @property
    def last_outcome(self) -> CommandOutcome | None:
        return self._last_outcome

    def select_workspace(self, workspace: WorkspaceId | str) -> CommandOutcome:
        result = self._commands.execute(CommandRequest(
            request_id=uuid4().hex, command="workspace.select",
            parameters={"workspace": workspace},
        ))
        self._last_outcome = result
        if result.status == CommandStatus.SUCCEEDED:
            self._workspace = WorkspaceId(result.value["workspace"])
            self._selection = None
        return result

    def select_entity(self, selection: SelectionRef | None) -> None:
        if selection is not None and not isinstance(selection, SelectionRef):
            raise TypeError("selection must be SelectionRef or None")
        self._selection = selection
