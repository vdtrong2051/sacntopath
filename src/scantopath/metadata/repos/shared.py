"""Legacy audit test seam: keep transaction-hook instrumentation intact."""
from __future__ import annotations
def _log(*args, **kwargs):
    from .. import store
    return store._log(*args, **kwargs)
