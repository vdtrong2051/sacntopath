"""07.10 compatibility façade; implementation moved to feature application."""
from scantopath.modules.project_workspace.application.service import (
    ProjectWorkspaceService, StoreNotOpenError, NumberingPendingError,
    NumberedSchemaRequiredError,
)

__all__ = ["ProjectWorkspaceService", "StoreNotOpenError", "NumberingPendingError", "NumberedSchemaRequiredError"]
