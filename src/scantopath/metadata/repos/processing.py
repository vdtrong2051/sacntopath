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

class _ProcessingRepository:
    def __init__(self, engine, root: Path):
        self.engine = engine
        self.root = root

    def create_processing_run(self, *, run_id: str | None = None, session_id: str,
                              stage: str, algorithm: str, version: str,
                              input_capture_ids: list[str],
                              parameters: dict[str, int | float | str | bool] | None = None) -> dict:
        run_id = _safe_id(run_id or uuid4().hex, "run_id")
        _safe_id(session_id, "session_id")
        stage = _label(stage, "stage")
        algorithm = _label(algorithm, "algorithm")
        version = _label(version, "version")
        if not isinstance(input_capture_ids, list) or not input_capture_ids:
            raise ValueError("ProcessingRun requires at least one Capture")
        if len(set(input_capture_ids)) != len(input_capture_ids):
            raise ValueError("Duplicate ProcessingRun input Capture")
        for id_ in input_capture_ids:
            _safe_id(id_, "capture_id")
        params = parameters if parameters is not None else {}
        if not isinstance(params, dict) or not all(
            isinstance(key, str) and isinstance(value, (int, float, str, bool))
            and (not isinstance(value, float) or isfinite(value))
            for key, value in params.items()
        ):
            raise ValueError("Parameters must be finite JSON-safe primitive values")
        json.dumps(params, allow_nan=False)
        with Session(self.engine) as db, db.begin():
            _must(db, _ScanSession, session_id, "Session")
            if db.get(_ProcessingRun, run_id):
                raise ValueError(f"ProcessingRun already exists: {run_id}")
            for capture_id in input_capture_ids:
                captured = _must(db, _Capture, capture_id, "Capture")
                if captured.session_id != session_id:
                    raise ValueError("ProcessingRun inputs must belong to the same session")
            obj = _ProcessingRun(run_id=run_id, session_id=session_id,
                                 stage=stage, algorithm=algorithm, version=version,
                                 parameters=dict(params), state="pending",
                                 output_files=[], created_at=_utc())
            db.add(obj)
            db.flush()
            for ordinal, capture_id in enumerate(input_capture_ids):
                db.add(_RunInput(run_id=run_id, capture_id=capture_id, ordinal=ordinal))
            _log(db, "run.created", "processing_run", run_id,
                 {"session_id": session_id, "input_count": len(input_capture_ids)})
            return {**_plain(obj), "input_capture_ids": list(input_capture_ids)}

    def start_processing_run(self, run_id: str) -> dict:
        with Session(self.engine) as db, db.begin():
            obj = _must(db, _ProcessingRun, _safe_id(run_id), "ProcessingRun")
            if obj.state != "pending":
                raise ValueError("Only pending ProcessingRuns may start")
            obj.state = "running"
            obj.started_at = _utc()
            _log(db, "run.started", "processing_run", run_id)
            return self._run_dict(db, obj)

    def finish_processing_run(self, run_id: str, *, state: str,
                              output_files: list[str] | None = None,
                              error_message: str | None = None) -> dict:
        if state not in ("succeeded", "failed"):
            raise ValueError("Run final state must be succeeded or failed")
        paths = output_files if output_files is not None else []
        if (not isinstance(paths, list) or not all(
                isinstance(path, str) and path.strip() and len(path) < 4096
                for path in paths)):
            raise ValueError("Invalid output_files")
        if error_message is not None and (not isinstance(error_message, str) or len(error_message) > 4096):
            raise ValueError("Invalid error_message")
        with Session(self.engine) as db, db.begin():
            obj = _must(db, _ProcessingRun, _safe_id(run_id), "ProcessingRun")
            if obj.state != "running":
                raise ValueError("Only running ProcessingRuns may finish")
            obj.state = state
            obj.output_files = list(paths)
            obj.error_message = error_message if state == "failed" else None
            obj.finished_at = _utc()
            _log(db, "run.finished", "processing_run", run_id, {"state": state})
            return self._run_dict(db, obj)

    @staticmethod
    def _run_dict(db: Session, obj: _ProcessingRun) -> dict:
        inputs = db.scalars(select(_RunInput).where(_RunInput.run_id == obj.run_id)
                            .order_by(_RunInput.ordinal)).all()
        # Pending rows may need a flush before _RunInput becomes queryable.
        return {**_plain(obj), "input_capture_ids": [item.capture_id for item in inputs]}

    def get_processing_run(self, run_id: str) -> dict:
        with Session(self.engine) as db:
            obj = _must(db, _ProcessingRun, _safe_id(run_id), "ProcessingRun")
            return self._run_dict(db, obj)
