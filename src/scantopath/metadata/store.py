"""PRE-05: transactional SQLite metadata registry for the ScanToPath GĐ0.

No camera, SDK, Qt, geometry algorithm or RAW bytes are imported here.
Filesystem RAW commits and SQLite transactions are *separate*; registering an
existing committed capture never rewrites or moves its RAW files.
"""
from __future__ import annotations

from datetime import datetime, timezone
import json
from math import isfinite
from pathlib import Path
from typing import Any
from uuid import uuid4

from sqlalchemy import (
    JSON, CheckConstraint, ForeignKey, Integer, String, Text,
    create_engine, event, select, text,
)
from sqlalchemy.orm import DeclarativeBase, Mapped, Session, mapped_column
from sqlalchemy.engine import URL

from scantopath.acquisition.raw_rgbd import RawRgbdCapture
from scantopath.storage.session_store import SessionStore
from scantopath.domain.models import CaptureMetadata


class _Base(DeclarativeBase):
    pass


class _Project(_Base):
    __tablename__ = "projects"
    project_id: Mapped[str] = mapped_column(String(128), primary_key=True)
    name: Mapped[str] = mapped_column(String(256), nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False, default="")
    created_at: Mapped[str] = mapped_column(String(40), nullable=False)
    updated_at: Mapped[str] = mapped_column(String(40), nullable=False)


class _Specimen(_Base):
    __tablename__ = "specimens"
    specimen_id: Mapped[str] = mapped_column(String(128), primary_key=True)
    project_id: Mapped[str] = mapped_column(
        ForeignKey("projects.project_id", ondelete="RESTRICT"), nullable=False, index=True
    )
    label: Mapped[str] = mapped_column(String(256), nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False, default="")
    created_at: Mapped[str] = mapped_column(String(40), nullable=False)
    updated_at: Mapped[str] = mapped_column(String(40), nullable=False)


class _ScanSession(_Base):
    __tablename__ = "scan_sessions"
    session_id: Mapped[str] = mapped_column(String(128), primary_key=True)
    specimen_id: Mapped[str] = mapped_column(
        ForeignKey("specimens.specimen_id", ondelete="RESTRICT"), nullable=False, index=True
    )
    label: Mapped[str] = mapped_column(String(256), nullable=False)
    state: Mapped[str] = mapped_column(String(16), nullable=False, default="open")
    created_at: Mapped[str] = mapped_column(String(40), nullable=False)
    closed_at: Mapped[str | None] = mapped_column(String(40))
    __table_args__ = (CheckConstraint("state IN ('open','closed')", name="session_state"),)


class _Capture(_Base):
    __tablename__ = "captures"
    capture_id: Mapped[str] = mapped_column(String(128), primary_key=True)
    session_id: Mapped[str] = mapped_column(
        ForeignKey("scan_sessions.session_id", ondelete="RESTRICT"), nullable=False, index=True
    )
    specimen_id: Mapped[str] = mapped_column(String(128), nullable=False)
    schema_version: Mapped[int] = mapped_column(Integer, nullable=False)
    kind: Mapped[str] = mapped_column(String(32), nullable=False)
    measured: Mapped[bool] = mapped_column(nullable=False)
    relative_path: Mapped[str] = mapped_column(Text, unique=True, nullable=False)
    registered_at: Mapped[str] = mapped_column(String(40), nullable=False)
    __table_args__ = (CheckConstraint("schema_version IN (1,2)", name="capture_schema"),)


class _ProcessingRun(_Base):
    __tablename__ = "processing_runs"
    run_id: Mapped[str] = mapped_column(String(128), primary_key=True)
    session_id: Mapped[str] = mapped_column(
        ForeignKey("scan_sessions.session_id", ondelete="RESTRICT"), nullable=False, index=True
    )
    stage: Mapped[str] = mapped_column(String(128), nullable=False)
    algorithm: Mapped[str] = mapped_column(String(256), nullable=False)
    version: Mapped[str] = mapped_column(String(128), nullable=False)
    parameters: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False)
    state: Mapped[str] = mapped_column(String(16), nullable=False, default="pending")
    output_files: Mapped[list[str]] = mapped_column(JSON, nullable=False, default=list)
    error_message: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[str] = mapped_column(String(40), nullable=False)
    started_at: Mapped[str | None] = mapped_column(String(40))
    finished_at: Mapped[str | None] = mapped_column(String(40))
    __table_args__ = (
        CheckConstraint("state IN ('pending','running','succeeded','failed')", name="run_state"),
    )


class _RunInput(_Base):
    __tablename__ = "processing_run_inputs"
    run_id: Mapped[str] = mapped_column(
        ForeignKey("processing_runs.run_id", ondelete="RESTRICT"), primary_key=True
    )
    ordinal: Mapped[int] = mapped_column(Integer, primary_key=True)
    capture_id: Mapped[str] = mapped_column(
        ForeignKey("captures.capture_id", ondelete="RESTRICT"), nullable=False, index=True
    )


class _AuditEvent(_Base):
    __tablename__ = "audit_events"
    event_id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    occurred_at: Mapped[str] = mapped_column(String(40), nullable=False)
    action: Mapped[str] = mapped_column(String(64), nullable=False)
    level: Mapped[str] = mapped_column(String(8), nullable=False, default="INFO")
    entity_type: Mapped[str] = mapped_column(String(64), nullable=False)
    entity_id: Mapped[str] = mapped_column(String(128), nullable=False)
    details: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False)
    __table_args__ = (CheckConstraint("level IN ('INFO','WARNING','ERROR')", name="audit_level"),)


def _utc() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="microseconds")


def _safe_id(value: str, name: str = "id") -> str:
    if (not isinstance(value, str) or not value or len(value) > 128 or not value.isascii()
            or not all(ch.isalnum() or ch in "-_" for ch in value)):
        raise ValueError(f"{name} must be 1..128 ASCII letters/digits/_/-")
    return value


def _label(value: str, name: str = "name") -> str:
    if not isinstance(value, str) or not value.strip() or len(value) > 256:
        raise ValueError(f"{name} must contain 1..256 characters")
    return value.strip()


def _plain(model: _Base) -> dict[str, Any]:
    return {column.name: getattr(model, column.name) for column in model.__table__.columns}


def _must(db: Session, cls: type[_Base], identifier: str, label: str) -> Any:
    item = db.get(cls, identifier)
    if item is None:
        raise LookupError(f"{label} does not exist: {identifier}")
    return item


def _log(db: Session, action: str, entity_type: str, entity_id: str,
         details: dict[str, Any] | None = None, *, level: str = "INFO") -> None:
    # No camera serial, RAW payload, secrets or unrestricted exception trace.
    db.add(_AuditEvent(occurred_at=_utc(), action=action, level=level,
                       entity_type=entity_type, entity_id=entity_id,
                       details=details or {}))


class MetadataStore:
    """SQLite registry for capture provenance, lineage and durable audit events.

    The constructor creates metadata.sqlite3 only; it does NOT initialize the
    camera or migrate unknown future SQLite schemas. Dispose with close().
    """

    SCHEMA_VERSION = 1  # New GĐ0 roots stay v1; numbered migration is EXPLICIT.
    SUPPORTED_SCHEMA_VERSIONS = (1, 2)

    def __init__(self, root: str | Path):
        self.root = Path(root).resolve()
        self.root.mkdir(parents=True, exist_ok=True)
        self.db_path = self.root / "metadata.sqlite3"
        url = URL.create("sqlite+pysqlite", database=str(self.db_path))
        self.engine = create_engine(url, connect_args={"timeout": 10})

        @event.listens_for(self.engine, "connect")
        def _sqlite_foreign_keys(dbapi_conn, _):
            cursor = dbapi_conn.cursor()
            cursor.execute("PRAGMA foreign_keys=ON")
            cursor.execute("PRAGMA busy_timeout=10000")
            cursor.close()

        try:
            with self.engine.begin() as conn:
                version = int(conn.execute(text("PRAGMA user_version")).scalar_one())
                if version not in (0, *self.SUPPORTED_SCHEMA_VERSIONS):
                    raise RuntimeError(f"Unsupported metadata schema version {version}")
                if version == 0:
                    # Refuse to take over a pre-existing, unknown database.
                    existing = conn.exec_driver_sql(
                        "SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%'"
                    ).scalars().all()
                    if existing:
                        raise RuntimeError("Unversioned database with existing tables: refusing to migrate")
                    _Base.metadata.create_all(conn)
                    conn.exec_driver_sql(f"PRAGMA user_version={self.SCHEMA_VERSION}")
                else:
                    # create_all cannot upgrade an existing schema: exact version is required.
                    expected = set(_Base.metadata.tables)
                    existing = set(conn.exec_driver_sql(
                        "SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%'"
                    ).scalars())
                    if version == 2:
                        from scantopath.storage.numbered_schema import TABLES
                        expected.update(TABLES)
                    if not expected.issubset(existing):
                        raise RuntimeError("Metadata database is incomplete; manual recovery required")
        except BaseException:
            self.engine.dispose()
            raise

    def close(self) -> None:
        self.engine.dispose()

    def __enter__(self) -> "MetadataStore":
        return self

    def __exit__(self, *_: object) -> None:
        self.close()

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
                        "processing_runs": [self._run_dict(db, run) for run in runs]})
                result["specimens"].append(spec)
            return result

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
