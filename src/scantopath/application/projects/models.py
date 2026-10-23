"""07.3: immutable presentation records, independent of SQLite/Qt/camera.

A verified RAW checksum proves stored-byte integrity, not metric accuracy.
None of the typed records asserts a measured world pose or aligned RGB-D.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

from scantopath.application.contracts import UiDataState

StorageState = Literal["unmapped", "legacy_unmapped", "not_materialized", "missing", "not_checked", "verified"]


@dataclass(frozen=True, slots=True)
class StoreInfo:
    root: str
    schema_version: int
    numbered_available: bool
    writable_with_codes: bool


@dataclass(frozen=True, slots=True)
class StorageRef:
    """A numbered alias is separate from the immutable database identifier."""
    public_code: str | None
    public_path: str | None
    relative_path: str | None
    layout_version: int | None
    state: StorageState


@dataclass(frozen=True, slots=True)
class ProjectSummary:
    project_id: str
    name: str
    description: str
    created_at: str
    updated_at: str
    storage: StorageRef


@dataclass(frozen=True, slots=True)
class SpecimenSummary:
    specimen_id: str
    project_id: str
    label: str
    description: str
    created_at: str
    updated_at: str
    storage: StorageRef


@dataclass(frozen=True, slots=True)
class CaptureSummary:
    capture_id: str
    session_id: str
    specimen_id: str
    schema_version: int  # RAW data format v1/v2, NOT database or folder layout.
    kind: str
    data_state: UiDataState  # sensor-sourced != metric validated.
    registered_at: str
    storage: StorageRef


@dataclass(frozen=True, slots=True)
class ProcessingRunSummary:
    run_id: str
    session_id: str
    stage: str
    algorithm: str
    version: str
    state: str
    input_capture_ids: tuple[str, ...]
    output_files: tuple[str, ...]  # references only; existence NOT verified.
    parameters_json: str  # immutable snapshot, rather than leaking mutable ORM JSON.
    error_message: str | None
    created_at: str
    started_at: str | None
    finished_at: str | None
    storage: StorageRef


@dataclass(frozen=True, slots=True)
class SessionSummary:
    session_id: str
    specimen_id: str
    label: str
    state: str
    created_at: str
    closed_at: str | None
    storage: StorageRef
    captures: tuple[CaptureSummary, ...] = ()
    processing_runs: tuple[ProcessingRunSummary, ...] = ()


@dataclass(frozen=True, slots=True)
class SpecimenNode:
    specimen: SpecimenSummary
    sessions: tuple[SessionSummary, ...]


@dataclass(frozen=True, slots=True)
class ProjectTree:
    project: ProjectSummary
    specimens: tuple[SpecimenNode, ...]


@dataclass(frozen=True, slots=True)
class AuditEventSummary:
    event_id: int
    occurred_at: str
    action: str
    level: str
    entity_type: str
    entity_id: str
    details_json: str


@dataclass(frozen=True, slots=True)
class CodeAssignmentSummary:
    """Explicit mapping operation; an empty result means no new codes assigned."""
    assigned: tuple[tuple[str, int], ...]


@dataclass(frozen=True, slots=True)
class CaptureInspection:
    """Read-only integrity outcome; NEVER implies geometric accuracy."""
    capture_id: str
    status: Literal["verified", "missing", "corrupt", "inaccessible"]
    raw_schema_version: int
    message: str
