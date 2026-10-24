"""Stable application exceptions. Preserve legacy import identities."""

class StoreNotOpenError(RuntimeError):
    """The explicitly selected existing store is unavailable."""


class NumberedSchemaRequiredError(RuntimeError):
    """Numbered write operations require explicit SQLite v2 migration."""


class NumberingPendingError(RuntimeError):
    """Metadata committed; alias allocation failed. Never repeat create()."""
    def __init__(self, entity_type: str, internal_id: str):
        self.entity_type = entity_type
        self.internal_id = internal_id
        super().__init__(f"Metadata committed for {entity_type} {internal_id}; "
                         "numbering pending; retry assign_code(), NOT create().")
