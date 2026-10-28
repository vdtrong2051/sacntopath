"""Access owner view/state without allocating additional QObject state."""
from __future__ import annotations
class _Coordinator:
    """Shared view/state is owned by the main feature QObject, not duplicated."""
    def __init__(self, owner):
        object.__setattr__(self, '_owner', owner)

    def __getattr__(self, name):
        return getattr(self._owner, name)

    def __setattr__(self, name, value):
        setattr(self._owner, name, value)
