"""Immutable, JSON-compatible UI DTOs. Nothing in this module opens resources.

Data-origin labels describe provenance/validation, NEVER geometric truth by
implication. In particular 'measured' is not synonymous with metric-validated.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
import json
import re
from types import MappingProxyType
from typing import Any, Mapping


class WorkspaceId(str, Enum):
    PROJECTS = "projects"
    CAPTURE = "capture"
    INSPECT3D = "inspect3d"
    PROCESSING = "processing"


class UiDataState(str, Enum):
    NOT_IMPLEMENTED = "not_implemented"
    FIXTURE = "fixture"
    MEASURED = "measured"
    ESTIMATED = "estimated"
    VALIDATED = "validated"
    INSUFFICIENT_EVIDENCE = "insufficient_evidence"


class CommandStatus(str, Enum):
    SUCCEEDED = "succeeded"
    FAILED = "failed"
    CANCELLED = "cancelled"
    NOT_IMPLEMENTED = "not_implemented"


class TaskState(str, Enum):
    QUEUED = "queued"
    RUNNING = "running"
    SUCCEEDED = "succeeded"
    FAILED = "failed"
    CANCELLED = "cancelled"


def _nonempty(value: str, field_name: str, max_length: int = 128) -> str:
    if not isinstance(value, str) or not value.strip() or len(value) > max_length:
        raise ValueError(f"{field_name} must be nonempty and at most {max_length} characters")
    return value


def _freeze_json(value: Any) -> Any:
    """Reject unsupported values (NaN, native pointers, arbitrary Python objects).

    JSON is deliberately the shared transport across UI, later worker/service
    boundaries and tests. Freeze nested containers so caller mutations cannot
    change an already-issued command/outcome.
    """
    if value is None or isinstance(value, (str, bool, int)):
        return value
    if isinstance(value, float):
        if not (-float("inf") < value < float("inf")):
            raise ValueError("JSON numeric values must be finite")
        return value
    if isinstance(value, (list, tuple)):
        return tuple(_freeze_json(v) for v in value)
    if isinstance(value, Mapping):
        if not all(isinstance(k, str) for k in value):
            raise ValueError("JSON mapping keys must be strings")
        return MappingProxyType({k: _freeze_json(v) for k, v in value.items()})
    raise ValueError(f"Unsupported JSON value: {type(value).__name__}")


def _thaw_json(value: Any) -> Any:
    if isinstance(value, Mapping):
        return {key: _thaw_json(v) for key, v in value.items()}
    if isinstance(value, tuple):
        return [_thaw_json(v) for v in value]
    return value


@dataclass(frozen=True, slots=True)
class SourceContext:
    """Provenance hint, not an estimate of handheld camera pose."""
    data_state: UiDataState = UiDataState.NOT_IMPLEMENTED
    source_ids: tuple[str, ...] = ()
    frame_id: str | None = None
    units: str | None = None

    def __post_init__(self) -> None:
        object.__setattr__(self, "data_state", UiDataState(self.data_state))
        if isinstance(self.source_ids, (str, bytes)):
            raise ValueError("source_ids must be a sequence of source identifiers")
        ids = tuple(self.source_ids)
        for item in ids:
            _nonempty(item, "source_id")
        object.__setattr__(self, "source_ids", ids)
        for name in ("frame_id", "units"):
            value = getattr(self, name)
            if value is not None:
                _nonempty(value, name)


@dataclass(frozen=True, slots=True)
class SelectionRef:
    entity_type: str
    entity_id: str
    source_id: str | None = None

    def __post_init__(self) -> None:
        _nonempty(self.entity_type, "entity_type")
        if not re.fullmatch(r"[a-z][a-z0-9_]*", self.entity_type):
            raise ValueError("entity_type must be a lowercase identifier")
        _nonempty(self.entity_id, "entity_id")
        if self.source_id is not None:
            _nonempty(self.source_id, "source_id")


@dataclass(frozen=True, slots=True)
class CommandRequest:
    request_id: str
    command: str
    parameters: Mapping[str, Any] = field(default_factory=dict)
    source_context: SourceContext = field(default_factory=SourceContext)

    def __post_init__(self) -> None:
        _nonempty(self.request_id, "request_id")
        _nonempty(self.command, "command")
        if not re.fullmatch(r"[a-z][a-z0-9_.]*", self.command):
            raise ValueError("command must use lowercase dot-separated identifiers")
        if not isinstance(self.parameters, Mapping):
            raise ValueError("parameters must be a JSON mapping")
        object.__setattr__(self, "parameters", _freeze_json(self.parameters))
        if not isinstance(self.source_context, SourceContext):
            raise TypeError("source_context must be SourceContext")


@dataclass(frozen=True, slots=True)
class CommandOutcome:
    request_id: str
    status: CommandStatus
    value: Mapping[str, Any] | None = None
    error_code: str | None = None
    message: str | None = None

    def __post_init__(self) -> None:
        _nonempty(self.request_id, "request_id")
        object.__setattr__(self, "status", CommandStatus(self.status))
        if self.value is not None:
            if not isinstance(self.value, Mapping):
                raise ValueError("value must be a JSON mapping or None")
            object.__setattr__(self, "value", _freeze_json(self.value))
        if self.status == CommandStatus.SUCCEEDED:
            if self.error_code is not None:
                raise ValueError("successful commands cannot carry error_code")
        else:
            _nonempty(self.error_code, "error_code")
        if self.message is not None:
            _nonempty(self.message, "message", 512)

    def as_dict(self) -> dict[str, Any]:
        """Serializable snapshot for UI diagnostics; no framework objects."""
        result = {
            "request_id": self.request_id, "status": self.status.value,
            "value": _thaw_json(self.value), "error_code": self.error_code,
            "message": self.message,
        }
        json.dumps(result, allow_nan=False)  # Defensive serialization gate.
        return result


@dataclass(frozen=True, slots=True)
class TaskSnapshot:
    """UI task record ONLY; not a persisted GĐ0 ProcessingRun."""
    task_id: str
    title: str
    state: TaskState = TaskState.QUEUED
    progress: float | None = None
    can_cancel: bool = False
    error: str | None = None

    def __post_init__(self) -> None:
        _nonempty(self.task_id, "task_id")
        _nonempty(self.title, "title", 256)
        object.__setattr__(self, "state", TaskState(self.state))
        if self.progress is not None:
            if isinstance(self.progress, bool) or not isinstance(self.progress, (float, int)):
                raise ValueError("progress must be a number between 0 and 100 or None")
            if not (0 <= self.progress <= 100):
                raise ValueError("progress must be between 0 and 100")
        terminal = self.state in (TaskState.SUCCEEDED, TaskState.FAILED, TaskState.CANCELLED)
        if terminal and self.can_cancel:
            raise ValueError("terminal tasks cannot be cancellable")
        if self.error is not None:
            _nonempty(self.error, "error", 512)
            if self.state != TaskState.FAILED:
                raise ValueError("error is only valid on failed tasks")
