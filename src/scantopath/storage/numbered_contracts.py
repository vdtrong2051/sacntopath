"""Typed numbered-storage identifiers, safe paths and mapping contracts."""
from __future__ import annotations
from dataclasses import dataclass
from datetime import datetime, timezone
import os
from pathlib import Path, PurePosixPath
import re
from typing import Literal

Kind = Literal["project", "specimen", "session", "capture", "run"]
_TABLES = {
    "project": ("projects", "project_id", "storage_projects", "project_id", "P", ""),
    "specimen": ("specimens", "specimen_id", "storage_specimens", "specimen_id", "S", "project_id"),
    "session": ("scan_sessions", "session_id", "storage_sessions", "session_id", "T", "specimen_id"),
    "capture": ("captures", "capture_id", "storage_captures", "capture_id", "C", "session_id"),
    "run": ("processing_runs", "run_id", "storage_runs", "run_id", "R", "session_id"),
}
_PARENT = {"specimen": "project", "session": "specimen", "capture": "session", "run": "session"}
_CODE = re.compile(r"^[PSTCR][0-9]{4,}$", re.ASCII)
_HIERARCHY = re.compile(r"^P[0-9]{4,}(?:/S[0-9]{4,}(?:/T[0-9]{4,}(?:/[CR][0-9]{4,})?)?)?$", re.ASCII)


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="microseconds")


def _safe_id(value: str) -> str:
    if (not isinstance(value, str) or not 1 <= len(value) <= 128
            or not value.isascii() or not all(c.isalnum() or c in "-_" for c in value)):
        raise ValueError("Internal ID must be 1..128 ASCII letters/digits/_/-")
    return value


def _relative(raw: str) -> PurePosixPath:
    if (not isinstance(raw, str) or not raw or "\\" in raw or "\x00" in raw
            or re.match(r"^[A-Za-z]:", raw) or raw.startswith("/")):
        raise ValueError("Invalid storage-relative path")
    pure = PurePosixPath(raw)
    if any(part in (".", "..", "") for part in raw.split("/")) or pure.is_absolute():
        raise ValueError("Unsafe storage-relative path")
    return pure


def _safe_path(root: Path, relative: str, *, require_exists: bool) -> Path:
    parts = _relative(relative).parts
    parent = root
    if parent.is_symlink() or (hasattr(parent, "is_junction") and parent.is_junction()):
        raise ValueError("Storage root cannot be a link/junction")
    for part in parts:
        parent = parent / part
        if parent.is_symlink() or (hasattr(parent, "is_junction") and parent.is_junction()):
            raise ValueError("Storage path contains link/junction")
    resolved_root = root.resolve(strict=True)
    if require_exists:
        out = parent.resolve(strict=True)
        if out != parent.absolute():
            raise ValueError("Storage path alias or traversal")
    else:
        out = parent.resolve(strict=False)
    if not out.is_relative_to(resolved_root):
        raise ValueError("Storage path escapes root")
    if os.name == "nt" and len(str(out)) >= 240:
        raise ValueError("Storage path too long for portable Windows usage")
    return out


@dataclass(frozen=True, slots=True)
class StorageLocation:
    entity_type: str
    internal_id: str
    public_path: str
    relative_path: str
    layout_version: int
    exists: bool
    integrity_state: str  # not_checked, verified, missing, not_materialized


@dataclass(frozen=True, slots=True)
class CaptureReservation:
    capture_id: str
    session_id: str
    public_path: str
    relative_path: str
