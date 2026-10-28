"""Small dependency container for one explicitly selected project store."""
from __future__ import annotations
from dataclasses import dataclass
from pathlib import Path
from typing import Callable
from .models import StoreInfo
from .errors import NumberedSchemaRequiredError


@dataclass(frozen=True, slots=True)
class WorkspaceContext:
    root: Path
    schema_version: int
    metadata_factory: Callable
    numbered: object | None
    safe_raw_path: Callable

    @property
    def info(self) -> StoreInfo:
        available = self.numbered is not None
        return StoreInfo(str(self.root), self.schema_version, available, available)

    def require_numbered(self):
        if self.numbered is None:
            raise NumberedSchemaRequiredError(
                "SQLite schema v1 is readable, but numbering requires an explicit "
                "v1-to-v2 migration using the 07.2 tool; no implicit migration is performed."
            )
        return self.numbered
