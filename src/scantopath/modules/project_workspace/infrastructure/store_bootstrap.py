"""GD2-09.09.1 explicit initialization of the named development data workspace.

No implicit startup side effects. No upgrades of existing stores. Migrations
are executed only after an explicit operator request, on a NEW empty folder.
"""
from __future__ import annotations

from pathlib import Path
import sqlite3


def initialize_empty_data_workspace(root: str | Path) -> Path:
    folder = Path(root).absolute()
    if folder.name != "scantopath-data":
        raise ValueError("ONLY_SCANTOPATH_DATA_ALLOWED")
    if folder.parent.is_symlink() or (hasattr(folder.parent, "is_junction") and folder.parent.is_junction()):
        raise ValueError("UNSAFE_STORE_PARENT")
    if folder.is_symlink() or (hasattr(folder, "is_junction") and folder.is_junction()):
        raise ValueError("UNSAFE_STORE_PATH")
    if folder.exists() and not folder.is_dir():
        raise ValueError("STORE_ROOT_IS_NOT_DIRECTORY")

    # Existing v2 store is never reinitialized or overwritten.
    database = folder / "metadata.sqlite3"
    if database.exists():
        if database.is_symlink() or not database.is_file():
            raise ValueError("INVALID_EXISTING_DATABASE")
        from scantopath.storage.numbered import NumberedStorageRegistry
        NumberedStorageRegistry(folder)  # Verify entire v2 schema; no migration.
        return folder.resolve(strict=True)

    if folder.exists() and any(folder.iterdir()):
        raise ValueError("STORE_DIRECTORY_NOT_EMPTY")
    folder.mkdir(parents=False, exist_ok=True)

    from scantopath.metadata.store import MetadataStore
    from scantopath.storage.numbered import NumberedStorageRegistry
    with MetadataStore(folder) as metadata:
        pass  # New database is v1 initially. Close ALL SQLAlchemy handles.
    NumberedStorageRegistry.migrate_database(folder)  # Explicit backup-first v1->v2.
    NumberedStorageRegistry(folder)  # Assert result is a complete numbered v2 store.
    return folder.resolve(strict=True)
