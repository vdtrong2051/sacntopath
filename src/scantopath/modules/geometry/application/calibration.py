
"""GD2-10.01: validated, immutable per-Capture RAW-v2 camera calibration.

No SDK call, storage access, image rectification or point projection.
Coordinates are declared in depth_optical; D->C translation is converted mm -> m.
"""
from __future__ import annotations

from dataclasses import dataclass
from math import isfinite

from scantopath.domain.raw_rgbd import RawRgbdCaptureMetadataV2


class CalibrationError(ValueError):
    def __init__(self, code: str, detail: str) -> None:
        self.code = code
        super().__init__(detail)


@dataclass(frozen=True, slots=True)
class CameraIntrinsics:
    width: int
    height: int
    fx: float
    fy: float
    cx: float
    cy: float


@dataclass(frozen=True, slots=True)
class Distortion:
    sdk_model: int
    # Immutable RAW-v2 / Orbbec field order; NOT the OpenCV coefficient order.
    k1_k6_p1_p2: tuple[float, ...]


@dataclass(frozen=True, slots=True)
class CalibrationContract:
    capture_id: str
    depth_K: CameraIntrinsics
    color_K: CameraIntrinsics
    depth_distortion: Distortion
    color_distortion: Distortion
    rotation_C_D: tuple[float, ...]  # 3x3 row-major, depth optical -> color optical
    translation_C_D_m: tuple[float, float, float]
    depth_scale_m_per_unit: float
    source: str = "RAW_V2_PER_CAPTURE"
    units: str = "m"
    frame: str = "depth_optical"

    @classmethod
    def from_metadata(cls, metadata: RawRgbdCaptureMetadataV2) -> "CalibrationContract":
        if not isinstance(metadata, RawRgbdCaptureMetadataV2):
            raise CalibrationError("CALIBRATION_INVALID", "Expected RAW v2 typed metadata")
        if (metadata.schema_version != 2 or metadata.alignment_mode != "disabled"
                or metadata.coordinate_frame != "depth_optical"
                or metadata.camera_pose is not None):
            raise CalibrationError("CALIBRATION_INVALID", "Unsupported RAW calibration/frame contract")

        def intrinsics(info, stream) -> CameraIntrinsics:
            vals = (info.fx, info.fy, info.cx, info.cy)
            if (info.width != stream.width or info.height != stream.height
                    or info.width <= 0 or info.height <= 0
                    or not all(isfinite(v) for v in vals)
                    or info.fx <= 0 or info.fy <= 0):
                raise CalibrationError("INTRINSICS_INVALID", "Intrinsics disagree with source grid")
            return CameraIntrinsics(info.width, info.height, *vals)

        def distortion(raw) -> Distortion:
            model = raw.sdk_model
            coeff = tuple(raw.k1_k6_p1_p2)
            # Official Orbbec enum 0..5. Recognition is NOT projection support.
            if type(model) is not int or model not in range(6):
                raise CalibrationError("DISTORTION_MODEL_UNSUPPORTED", "Unknown Orbbec distortion ID")
            if len(coeff) != 8 or not all(isfinite(v) for v in coeff):
                raise CalibrationError("DISTORTION_COEFFICIENTS_INVALID", "Invalid distortion coefficients")
            if model == 0 and any(v != 0.0 for v in coeff):
                raise CalibrationError("DISTORTION_COEFFICIENTS_INVALID", "NONE model has nonzero coefficients")
            return Distortion(model, coeff)

        scale = metadata.depth_scale_m_per_unit
        if not isfinite(scale) or scale <= 0:
            raise CalibrationError("DEPTH_SCALE_INVALID", "Depth scale must be positive and finite")

        rotation = tuple(metadata.depth_to_color.rotation)
        translation_mm = tuple(metadata.depth_to_color.translation_mm)
        if (len(rotation) != 9 or len(translation_mm) != 3
                or not all(isfinite(v) for v in (*rotation, *translation_mm))):
            raise CalibrationError("EXTRINSICS_INVALID", "Malformed Depth-to-Color transform")

        rows = (rotation[:3], rotation[3:6], rotation[6:])
        for i in range(3):
            for j in range(3):
                dot = sum(a * b for a, b in zip(rows[i], rows[j]))
                if abs(dot - (1.0 if i == j else 0.0)) > 1e-3:
                    raise CalibrationError("EXTRINSICS_INVALID", "Rotation is not orthonormal")

        r = rotation
        determinant = (r[0] * (r[4] * r[8] - r[5] * r[7])
                       - r[1] * (r[3] * r[8] - r[5] * r[6])
                       + r[2] * (r[3] * r[7] - r[4] * r[6]))
        if abs(determinant - 1.0) > 1e-3:
            raise CalibrationError("EXTRINSICS_INVALID", "Rotation is not right-handed")

        return cls(
            capture_id=metadata.capture_id,
            depth_K=intrinsics(metadata.depth_intrinsics, metadata.depth),
            color_K=intrinsics(metadata.color_intrinsics, metadata.color),
            depth_distortion=distortion(metadata.depth_distortion),
            color_distortion=distortion(metadata.color_distortion),
            rotation_C_D=rotation,
            translation_C_D_m=tuple(v / 1000.0 for v in translation_mm),
            depth_scale_m_per_unit=float(scale),
        )
