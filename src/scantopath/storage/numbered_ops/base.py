"""Shared resource context, no database ownership or mutations."""
from __future__ import annotations
class _Part:
    def __init__(self, registry):
        self._registry = registry
        self.root = registry.root
        self.db_path = registry.db_path
        self._connect = registry._connect
