"""SRP repositories for metadata. Every command preserves its own Session.begin boundary.

Mapping classes are in schema.py; existing MetadataStore remains the stable public API.
"""
from __future__ import annotations
import json
from math import isfinite
from pathlib import Path
from typing import Any
from uuid import uuid4
from sqlalchemy import select
from sqlalchemy.orm import Session
from scantopath.acquisition.raw_rgbd import RawRgbdCapture
from scantopath.storage.session_store import SessionStore
from scantopath.domain.models import CaptureMetadata
from ..schema import (_Base, _Project, _Specimen, _ScanSession, _Capture,
                     _ProcessingRun, _RunInput, _AuditEvent, _utc, _safe_id,
                     _label, _plain, _must, _log as _schema_log)

from .shared import _log

class _CaptureRepository:
    def __init__(self, engine, root: Path):
        self.engine = engine
        self.root = root

    def register_capture(self, capture_path: str | Path) -> dict:
        """Register a *previously* committed RAW v2 or synthetic v1 capture.

        Read/validate storage first, then insert the SQLite reference and audit
        in a single DB transaction. No RAW data is moved or rewritten.
        """
        supplied = Path(capture_path).absolute()
        resolved = supplied.resolve(strict=True)
        if supplied != resolved:
            raise ValueError("Capture registration forbids symlinks and path traversal")
        try:
            relative = resolved.relative_to(self.root)
        except ValueError as exc:
            raise ValueError("Capture must belong to this metadata root") from exc
        if len(relative.parts) != 4 or relative.parts[0] != "sessions" or relative.parts[2] != "captures":
            raise ValueError("Unexpected capture path layout")
        _safe_id(relative.parts[1], "session_id")
        _safe_id(relative.parts[3], "capture_id")
        # Validate v2 SHA-256/metadata/bytes or v1 committed array layout.
        capture = SessionStore(self.root).read_capture(resolved)
        meta: CaptureMetadata = capture.metadata if isinstance(capture, RawRgbdCapture) else capture[0]
        if meta.session_id != relative.parts[1] or meta.capture_id != relative.parts[3]:
            raise ValueError("Capture metadata/path ID mismatch")
        schema = meta.schema_version
        with Session(self.engine) as db, db.begin():
            session = _must(db, _ScanSession, meta.session_id, "Session")
            if session.state != "open":
                raise ValueError("Cannot register a capture into a closed ScanSession")
            if session.specimen_id != meta.specimen_id:
                raise ValueError("Capture specimen ID differs from ScanSession specimen")
            if db.get(_Capture, meta.capture_id):
                raise ValueError(f"Capture already registered: {meta.capture_id}")
            obj = _Capture(capture_id=meta.capture_id, session_id=meta.session_id,
                           specimen_id=meta.specimen_id, schema_version=schema,
                           kind=meta.kind.value, measured=meta.measured,
                           relative_path=relative.as_posix(), registered_at=_utc())
            db.add(obj)
            _log(db, "capture.registered", "capture", meta.capture_id,
                 {"session_id": meta.session_id, "schema_version": schema})
            return _plain(obj)

    def get_capture(self, capture_id: str, *, verify_raw: bool = False) -> dict:
        with Session(self.engine) as db:
            record = _plain(_must(db, _Capture, _safe_id(capture_id), "Capture"))
        if verify_raw:
            # Protect against corrupt/removed files after metadata registration.
            location = self.root.joinpath(*Path(record["relative_path"]).parts)
            if record["relative_path"].startswith("01_PROJECTS/"):
                # The registry contains the authoritative capture ID and mapping.
                from scantopath.storage.numbered import NumberedStorageRegistry
                resolved = NumberedStorageRegistry(self.root).resolve_id(
                    "capture", capture_id, verify=True)
                if resolved.relative_path != record["relative_path"] or resolved.layout_version != 2:
                    raise ValueError("Numbered registry/capture path mismatch")
            else:
                SessionStore(self.root).read_capture(location)
        return record
