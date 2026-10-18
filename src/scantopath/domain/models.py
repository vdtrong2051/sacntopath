"""Persisted experiment contracts. Units and coordinate frames are explicit."""
from datetime import datetime, timezone
from enum import Enum
from typing import Literal
from uuid import uuid4

from pydantic import BaseModel, ConfigDict, Field, model_validator


class CaptureKind(str, Enum):
    SYNTHETIC = "synthetic"
    ORBBEC = "orbbec"
    REPLAY = "replay"


class Intrinsics(BaseModel):
    model_config = ConfigDict(extra="forbid")
    fx: float = Field(gt=0)
    fy: float = Field(gt=0)
    cx: float
    cy: float
    width: int = Field(gt=0)
    height: int = Field(gt=0)


class Pose(BaseModel):
    model_config = ConfigDict(extra="forbid")
    theta_deg: float = 0.0
    phi_deg: float = 0.0
    frame: Literal["stage", "manual", "unknown"] = "unknown"
    encoder_verified: bool = False


class CaptureMetadata(BaseModel):
    model_config = ConfigDict(extra="forbid")
    schema_version: Literal[1] = 1
    capture_id: str = Field(default_factory=lambda: uuid4().hex)
    session_id: str
    specimen_id: str
    captured_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    kind: CaptureKind
    camera_model: str
    camera_serial: str | None = None
    sdk_version: str | None = None
    firmware_version: str | None = None
    depth_scale_m_per_unit: float = Field(gt=0)
    intrinsics: Intrinsics
    pose: Pose
    coordinate_frame: Literal["depth_optical"] = "depth_optical"
    depth_unit: Literal["raw_uint16"] = "raw_uint16"
    rgb_registered_to_depth: bool = False
    measured: bool = False
    notes: str = ""

    @model_validator(mode="after")
    def check_provenance(self):
        if self.kind == CaptureKind.SYNTHETIC and self.measured:
            raise ValueError("Synthetic frame must not be flagged as measured")
        if self.kind == CaptureKind.ORBBEC and not self.measured:
            raise ValueError("Orbbec capture must be marked as measured")
        return self


class ProcessingRun(BaseModel):
    model_config = ConfigDict(extra="forbid")
    run_id: str = Field(default_factory=lambda: uuid4().hex)
    session_id: str
    stage: str
    algorithm: str
    version: str
    input_capture_ids: list[str]
    parameters: dict[str, int | float | str | bool]
    output_files: list[str] = Field(default_factory=list)
    finished_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
