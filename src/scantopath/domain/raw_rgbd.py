"""PRE-02: strict, storage-independent RAW RGB-D metadata contract (schema v2).

This describes source images in their original pixel grids. It does NOT align
frames, determine moving-camera pose, or certify geometric accuracy.
Existing CaptureMetadata schema v1 is deliberately unchanged.
"""
from datetime import datetime, timezone
from enum import Enum
from typing import Literal
from uuid import uuid4

from pydantic import BaseModel, ConfigDict, Field, model_validator

from scantopath.domain.models import CaptureKind


class RawPixelEncoding(str, Enum):
    MJPEG = "MJPEG"
    Y16 = "Y16"


class _StrictFrozenModel(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)


class RawStreamInfo(_StrictFrozenModel):
    """Per-frame SDK metadata; timestamps are SDK-reported microseconds."""

    encoding: RawPixelEncoding
    width: int = Field(gt=0)
    height: int = Field(gt=0)
    frame_index: int = Field(ge=0)
    timestamp_us: int = Field(gt=0)
    payload_size_bytes: int = Field(gt=0)


class RawIntrinsics(_StrictFrozenModel):
    width: int = Field(gt=0)
    height: int = Field(gt=0)
    fx: float = Field(gt=0, allow_inf_nan=False)
    fy: float = Field(gt=0, allow_inf_nan=False)
    cx: float = Field(allow_inf_nan=False)
    cy: float = Field(allow_inf_nan=False)


class RawDistortion(_StrictFrozenModel):
    """Keep SDK model identifier; don't silently reinterpret distortion."""

    sdk_model: int
    # k1,k2,k3,k4,k5,k6,p1,p2, in EXACT SDK/bridge order.
    k1_k6_p1_p2: tuple[float, float, float, float, float, float, float, float]

    @model_validator(mode="after")
    def finite_coefficients(self) -> "RawDistortion":
        from math import isfinite

        if not all(isfinite(value) for value in self.k1_k6_p1_p2):
            raise ValueError("Distortion coefficients must be finite")
        return self


class RawDepthToColorExtrinsics(_StrictFrozenModel):
    """Depth optical -> Color optical, row-major 3x3; SDK translation in mm."""

    rotation: tuple[float, float, float, float, float, float, float, float, float]
    translation_mm: tuple[float, float, float]

    @model_validator(mode="after")
    def finite_values(self) -> "RawDepthToColorExtrinsics":
        from math import isfinite

        if not all(isfinite(value) for value in (*self.rotation, *self.translation_mm)):
            raise ValueError("Extrinsic components must be finite")
        return self


class RawDeviceInfo(_StrictFrozenModel):
    name: str = Field(min_length=1)
    firmware_version: str | None = None
    usb_connection: str | None = None
    pid: int | None = Field(default=None, ge=0)
    sdk_version: str | None = None  # No assumed version when runtime doesn't expose it.
    serial: str | None = None  # Optional; never print/export by default.


class RawRgbdCaptureMetadataV2(_StrictFrozenModel):
    """Unaligned RAW captures; v1 synthetic capture metadata remains separate.

    A capture marked as sourced from Orbbec is a sensor measurement, NOT a
    declaration of dimensional accuracy. For handheld mode, camera pose is
    unknown until an independently validated estimation stage provides it.
    """

    schema_version: Literal[2] = 2
    capture_id: str = Field(default_factory=lambda: uuid4().hex,
                            pattern=r"^[A-Za-z0-9_-]+$")
    session_id: str = Field(min_length=1, pattern=r"^[A-Za-z0-9_-]+$")
    specimen_id: str = Field(min_length=1, pattern=r"^[A-Za-z0-9_-]+$")
    captured_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    kind: Literal[CaptureKind.ORBBEC, CaptureKind.SYNTHETIC]
    measured: bool
    device: RawDeviceInfo
    color: RawStreamInfo
    depth: RawStreamInfo
    color_intrinsics: RawIntrinsics
    depth_intrinsics: RawIntrinsics
    color_distortion: RawDistortion
    depth_distortion: RawDistortion
    depth_to_color: RawDepthToColorExtrinsics
    depth_scale_m_per_unit: float = Field(gt=0, allow_inf_nan=False)
    alignment_mode: Literal["disabled"] = "disabled"
    frame_sync_requested: bool = False
    timestamp_domain: Literal["sdk_reported_unverified"] = "sdk_reported_unverified"
    coordinate_frame: Literal["depth_optical"] = "depth_optical"
    camera_pose: None = None  # Handheld and NOT estimated at PRE-02.

    @model_validator(mode="after")
    def check_contract(self) -> "RawRgbdCaptureMetadataV2":
        if self.captured_at.utcoffset() is None:
            raise ValueError("captured_at must include a timezone")
        if self.color.encoding != RawPixelEncoding.MJPEG:
            raise ValueError("RAW color must be MJPEG")
        if self.depth.encoding != RawPixelEncoding.Y16:
            raise ValueError("RAW depth must be Y16")
        if (self.color.width, self.color.height) != (
            self.color_intrinsics.width, self.color_intrinsics.height
        ):
            raise ValueError("Color intrinsics do not match color frame")
        if (self.depth.width, self.depth.height) != (
            self.depth_intrinsics.width, self.depth_intrinsics.height
        ):
            raise ValueError("Depth intrinsics do not match depth frame")
        if self.depth.payload_size_bytes != self.depth.width * self.depth.height * 2:
            raise ValueError("Y16 must use exactly two bytes per depth pixel")
        if self.kind == CaptureKind.SYNTHETIC and self.measured:
            raise ValueError("Synthetic RAW fixture must not be marked measured")
        if self.kind == CaptureKind.ORBBEC and not self.measured:
            raise ValueError("Orbbec source must declare measured provenance")
        return self

    @property
    def observed_timestamp_delta_us(self) -> int:
        """Diagnostic only; not proof of synchronization or common clock domain."""
        return abs(self.color.timestamp_us - self.depth.timestamp_us)
