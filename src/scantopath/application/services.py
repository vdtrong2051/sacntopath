"""Headless command + navigation seam for session 06.3 Qt integration.

06.2 intentionally implements ONLY commands with a present consumer: workspace
navigation. Project/SQLite services belong to 07, worker execution to 06.5.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from scantopath.application.contracts import (
    CommandOutcome, CommandRequest, CommandStatus, WorkspaceId,
)


@dataclass(frozen=True, slots=True)
class NavigationSnapshot:
    workspace: WorkspaceId
    revision: int

    def as_dict(self) -> dict[str, Any]:
        return {"workspace": self.workspace.value, "revision": self.revision}


class NavigationService:
    """Pure state for one desktop window. No Qt, database or hardware imports."""

    def __init__(self, initial: WorkspaceId = WorkspaceId.PROJECTS) -> None:
        self._workspace = WorkspaceId(initial)
        self._revision = 0

    def current(self) -> NavigationSnapshot:
        return NavigationSnapshot(self._workspace, self._revision)

    def select(self, workspace: WorkspaceId) -> NavigationSnapshot:
        target = WorkspaceId(workspace)
        if self._workspace != target:
            self._workspace = target
            self._revision += 1
        return self.current()


class CommandService:
    """Dispatch whitelisted UI commands into application services.

    Unsupported commands are reported as NOT_IMPLEMENTED, never interpreted
    as successful camera, geometry, metric or project operations.
    """

    def __init__(self, navigation: NavigationService | None = None) -> None:
        self.navigation = navigation if navigation is not None else NavigationService()

    def execute(self, request: CommandRequest) -> CommandOutcome:
        if not isinstance(request, CommandRequest):
            raise TypeError("request must be CommandRequest")
        if request.command == "workspace.current":
            if request.parameters:
                return self._bad_request(request, "workspace.current takes no parameters")
            state = self.navigation.current()
        elif request.command == "workspace.select":
            if set(request.parameters) != {"workspace"}:
                return self._bad_request(request, "workspace.select requires only workspace")
            try:
                state = self.navigation.select(WorkspaceId(request.parameters["workspace"]))
            except (ValueError, TypeError):
                return self._bad_request(request, "Unknown workspace")
        else:
            return CommandOutcome(
                request_id=request.request_id, status=CommandStatus.NOT_IMPLEMENTED,
                error_code="NOT_IMPLEMENTED", message="Chức năng chưa triển khai",
            )
        return CommandOutcome(
            request_id=request.request_id, status=CommandStatus.SUCCEEDED,
            value=state.as_dict(),
        )

    @staticmethod
    def _bad_request(request: CommandRequest, message: str) -> CommandOutcome:
        return CommandOutcome(request_id=request.request_id,
                              status=CommandStatus.FAILED,
                              error_code="INVALID_ARGUMENT", message=message)
