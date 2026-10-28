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

class _AuditRepository:
    def __init__(self, engine, root: Path):
        self.engine = engine
        self.root = root

    def record_event(self, *, level: str, action: str, entity_type: str,
                     entity_id: str, details: dict[str, Any] | None = None) -> dict:
        """Persist a structured INFO/WARNING/ERROR diagnostic without RAW bytes.

        Callers must sanitize details (no camera serial, personal data, tokens,
        binary frames or full exception traces). It is a bounded audit record,
        not a file logger and not a transaction spanning the filesystem.
        """
        if level not in ("INFO", "WARNING", "ERROR"):
            raise ValueError("Invalid event severity")
        if (not isinstance(action, str) or not 1 <= len(action) <= 64
                or not all(c.isascii() and (c.isalnum() or c in "._-") for c in action)):
            raise ValueError("Invalid event action")
        if (not isinstance(entity_type, str) or not 1 <= len(entity_type) <= 64
                or not all(c.isascii() and (c.isalnum() or c in "_-") for c in entity_type)):
            raise ValueError("Invalid event entity type")
        _safe_id(entity_id, "entity_id")
        details = details if details is not None else {}
        if not isinstance(details, dict):
            raise ValueError("Event details must be a JSON object")
        try:
            encoded = json.dumps(details, allow_nan=False)
        except (ValueError, TypeError) as exc:
            raise ValueError("Invalid JSON event details") from exc
        if len(encoded.encode("utf-8")) > 4096:
            raise ValueError("Event details exceed 4096 bytes")
        with Session(self.engine) as db, db.begin():
            obj = _AuditEvent(occurred_at=_utc(), action=action, level=level,
                              entity_type=entity_type, entity_id=entity_id,
                              details=details)
            db.add(obj)
            db.flush()
            return _plain(obj)

    def list_events(self, *, limit: int = 100) -> list[dict]:
        if type(limit) is not int or not 1 <= limit <= 1000:
            raise ValueError("limit must be between 1 and 1000")
        with Session(self.engine) as db:
            events = db.scalars(select(_AuditEvent).order_by(_AuditEvent.event_id.desc())
                                .limit(limit)).all()
            return [_plain(obj) for obj in events]
