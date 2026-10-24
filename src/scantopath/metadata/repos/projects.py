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

from .processing import _ProcessingRepository
from .shared import _log

class _ProjectRepository:
    def __init__(self, engine, root: Path):
        self.engine = engine
        self.root = root

    def create_project(self, project_id: str, name: str, description: str = "") -> dict:
        _safe_id(project_id, "project_id")
        name = _label(name)
        now = _utc()
        with Session(self.engine) as db, db.begin():
            if db.get(_Project, project_id):
                raise ValueError(f"Project already exists: {project_id}")
            model = _Project(project_id=project_id, name=name, description=description,
                             created_at=now, updated_at=now)
            db.add(model)
            _log(db, "project.created", "project", project_id)
            return _plain(model)

    def update_project(self, project_id: str, *, name: str | None = None,
                       description: str | None = None) -> dict:
        _safe_id(project_id)
        if name is None and description is None:
            raise ValueError("No project changes supplied")
        with Session(self.engine) as db, db.begin():
            item = _must(db, _Project, project_id, "Project")
            if name is not None:
                item.name = _label(name)
            if description is not None:
                item.description = description
            item.updated_at = _utc()
            _log(db, "project.updated", "project", project_id)
            return _plain(item)

    def get_project(self, project_id: str) -> dict:
        with Session(self.engine) as db:
            return _plain(_must(db, _Project, _safe_id(project_id), "Project"))

    def list_projects(self) -> list[dict]:
        with Session(self.engine) as db:
            return [_plain(x) for x in db.scalars(select(_Project).order_by(_Project.project_id))]

    def create_specimen(self, specimen_id: str, project_id: str, label: str,
                        description: str = "") -> dict:
        _safe_id(specimen_id, "specimen_id")
        _safe_id(project_id, "project_id")
        label = _label(label)
        now = _utc()
        with Session(self.engine) as db, db.begin():
            _must(db, _Project, project_id, "Project")
            if db.get(_Specimen, specimen_id):
                raise ValueError(f"Specimen already exists: {specimen_id}")
            obj = _Specimen(specimen_id=specimen_id, project_id=project_id,
                            label=label, description=description,
                            created_at=now, updated_at=now)
            db.add(obj)
            _log(db, "specimen.created", "specimen", specimen_id, {"project_id": project_id})
            return _plain(obj)

    def update_specimen(self, specimen_id: str, *, label: str | None = None,
                        description: str | None = None) -> dict:
        if label is None and description is None:
            raise ValueError("No specimen changes supplied")
        with Session(self.engine) as db, db.begin():
            obj = _must(db, _Specimen, _safe_id(specimen_id), "Specimen")
            if label is not None:
                obj.label = _label(label)
            if description is not None:
                obj.description = description
            obj.updated_at = _utc()
            _log(db, "specimen.updated", "specimen", specimen_id)
            return _plain(obj)

    def create_scan_session(self, session_id: str, specimen_id: str, label: str = "Scan") -> dict:
        _safe_id(session_id, "session_id")
        _safe_id(specimen_id, "specimen_id")
        label = _label(label)
        with Session(self.engine) as db, db.begin():
            _must(db, _Specimen, specimen_id, "Specimen")
            if db.get(_ScanSession, session_id):
                raise ValueError(f"Session already exists: {session_id}")
            obj = _ScanSession(session_id=session_id, specimen_id=specimen_id,
                               label=label, state="open", created_at=_utc())
            db.add(obj)
            _log(db, "session.created", "session", session_id, {"specimen_id": specimen_id})
            return _plain(obj)

    def update_scan_session(self, session_id: str, *, label: str) -> dict:
        """Edit the visible name only; identity, parent and open/closed state are immutable."""
        _safe_id(session_id, "session_id")
        clean = _label(label, "label")
        with Session(self.engine) as db, db.begin():
            item = _must(db, _ScanSession, session_id, "ScanSession")
            item.label = clean
            _log(db, "session.updated", "session", session_id)
            return _plain(item)

    def close_scan_session(self, session_id: str) -> dict:
        with Session(self.engine) as db, db.begin():
            obj = _must(db, _ScanSession, _safe_id(session_id), "Session")
            if obj.state != "open":
                raise ValueError("ScanSession is already closed")
            obj.state = "closed"
            obj.closed_at = _utc()
            _log(db, "session.closed", "session", session_id)
            return _plain(obj)

    def get_project_tree(self, project_id: str) -> dict:
        """Read a stable hierarchical view without opening camera/RAW bytes."""
        with Session(self.engine) as db:
            proj = _plain(_must(db, _Project, _safe_id(project_id), "Project"))
            specimen_list = db.scalars(select(_Specimen).where(_Specimen.project_id == project_id)
                                       .order_by(_Specimen.specimen_id)).all()
            result = {**proj, "specimens": []}
            for specimen in specimen_list:
                spec = {**_plain(specimen), "sessions": []}
                sessions = db.scalars(select(_ScanSession).where(
                    _ScanSession.specimen_id == specimen.specimen_id
                ).order_by(_ScanSession.session_id)).all()
                for session in sessions:
                    captures = db.scalars(select(_Capture).where(
                        _Capture.session_id == session.session_id
                    ).order_by(_Capture.capture_id)).all()
                    runs = db.scalars(select(_ProcessingRun).where(
                        _ProcessingRun.session_id == session.session_id
                    ).order_by(_ProcessingRun.run_id)).all()
                    spec["sessions"].append({**_plain(session),
                        "captures": [_plain(c) for c in captures],
                        "processing_runs": [_ProcessingRepository._run_dict(db, run) for run in runs]})
                result["specimens"].append(spec)
            return result
