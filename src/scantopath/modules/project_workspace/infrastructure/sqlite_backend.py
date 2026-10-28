"""07.11: concrete infrastructure bootstrap, only opened by explicit user action.

Existing SQLite is probed read-only. Neither probe nor adapter construction
creates a database, migrates schema, allocates codes or touches RAW bytes.
"""
from __future__ import annotations
from pathlib import Path
import sqlite3

from scantopath.metadata.store import MetadataStore
from scantopath.storage.numbered import NumberedStorageRegistry, _safe_path
from ..application.errors import StoreNotOpenError


def default_factories():
    return MetadataStore, NumberedStorageRegistry


def safe_raw_path(root: Path, relative: str):
    return _safe_path(root, relative, require_exists=False)


def probe_existing(root: str | Path, metadata_factory):
    if not isinstance(root, (str, Path)) or not str(root).strip():
        raise ValueError("Storage root must be a nonempty local path")
    supplied = Path(root).absolute()
    if supplied.is_symlink() or (hasattr(supplied, "is_junction") and supplied.is_junction()):
        raise ValueError("Storage root must not be a symbolic link or junction")
    if not supplied.is_dir():
        raise StoreNotOpenError("Storage folder does not exist; choose an existing store")
    database = supplied / "metadata.sqlite3"
    if not database.is_file() or database.is_symlink():
        raise StoreNotOpenError("No metadata.sqlite3 in selected folder")
    root = supplied.resolve(strict=True)
    uri = database.resolve(strict=True).as_uri() + "?mode=ro"
    with sqlite3.connect(uri, uri=True) as conn:
        version = conn.execute("PRAGMA user_version").fetchone()[0]
    if version not in (1, 2):
        raise RuntimeError(f"Unsupported SQLite schema version: {version}")
    with metadata_factory(root):
        pass
    return root, version
