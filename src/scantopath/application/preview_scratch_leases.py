"""UXH-01.6: explicit ownership of temporary RAW->PLY Preview directories.

The caller MUST prove its old Render Host has retired before pruning. Merely
leaving a workspace is never proof that a PLY can be deleted. No Qt/VTK/RAW IO
is performed here; only owned TemporaryDirectory.cleanup() is invoked.
"""
from __future__ import annotations

import logging
import os
from pathlib import Path
from typing import Iterable

_LOG = logging.getLogger(__name__)


def _key(path: os.PathLike[str] | str) -> str:
    """Normalize path spelling on the host OS; do not resolve symlinks."""
    return os.path.normcase(os.path.abspath(os.fspath(path)))


class PreviewScratchLeases:
    """Keep a scratch directory until no running/pending/retry scene owns it."""

    def __init__(self) -> None:
        self._items: dict[str, object] = {}

    def __len__(self) -> int:
        return len(self._items)

    def contains(self, path: os.PathLike[str] | str) -> bool:
        return _key(path) in self._items

    def retain(self, path: os.PathLike[str] | str, scratch: object) -> None:
        key = _key(path)
        if key in self._items:
            raise ValueError("DUPLICATE_PREVIEW_LEASE")
        if not hasattr(scratch, "cleanup") or not callable(scratch.cleanup):
            raise TypeError("PREVIEW_SCRATCH_REQUIRES_CLEANUP")
        self._items[key] = scratch

    def release_except(self, protected: Iterable[os.PathLike[str] | str | None],
                       *, renderer_retired: bool) -> int:
        """Delete unreferenced directories only with explicit renderer proof.

        A Windows file lock/PermissionError is not silently forgotten: keep
        ownership and retry on the next poll or application shutdown.
        Returns number of successful cleanup operations.
        """
        if not renderer_retired:
            return 0
        keep = {_key(p) for p in protected if p is not None}
        cleaned = 0
        for key, scratch in tuple(self._items.items()):
            if key in keep:
                continue
            try:
                scratch.cleanup()
            except OSError as exc:
                _LOG.warning("PREVIEW_SCRATCH_CLEANUP_RETRY path=%s error=%s", key, exc)
                continue
            del self._items[key]
            cleaned += 1
        return cleaned

    def release_all(self) -> int:
        """Only call after the parent has stopped workers and Render Host."""
        self.release_except((), renderer_retired=True)
        return len(self._items)
