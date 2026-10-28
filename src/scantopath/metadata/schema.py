"""SQLAlchemy schema and validated primitives for persisted metadata v1/v2.

Do not migrate schemas by importing this module.
"""
from __future__ import annotations
from datetime import datetime, timezone
from typing import Any
from sqlalchemy import JSON, CheckConstraint, ForeignKey, Integer, String, Text
from sqlalchemy.orm import DeclarativeBase, Mapped, Session, mapped_column

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
