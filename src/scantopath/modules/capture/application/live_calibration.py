"""FT-02a: immutable per-native-frameset calibration, no RAW ID or SDK pointers.

This module has no Qt/SDK/storage dependencies and can cross multiprocessing.Pipe.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass
from hashlib import sha256
import json
from math import isfinite
from typing import Any


class LiveCalibrationError(ValueError):
    def __init__(self, code: str, detail: str) -> None:
        self.code = code
        super().__init__(detail)


def _finite_number(value: object) -> bool:
    return type(value) in (int, float) and isfinite(value)


@dataclass(frozen=True, slots=True)
class LiveIntrinsics:
    width: int
    height: int
    fx: float
    fy: float
    cx: float
    cy: float

    def __post_init__(self) -> None:
        if (type(self.width) is not int or type(self.height) is not int
                or not 0 < self.width <= 32_000_000
                or not 0 < self.height <= 32_000_000
                or self.width * self.height > 32_000_000
                or not all(_finite_number(v) for v in (self.fx, self.fy, self.cx, self.cy))
                or self.fx <= 0 or self.fy <= 0):
            raise LiveCalibrationError("INTRINSICS_INVALID", "Invalid native-grid intrinsics")


@dataclass(frozen=True, slots=True)
class LiveDistortion:
    sdk_model: int
    k1_k6_p1_p2: tuple[float, ...]

    def __post_init__(self) -> None:
        if type(self.sdk_model) is not int or self.sdk_model not in range(6):
            raise LiveCalibrationError("DISTORTION_MODEL_UNSUPPORTED", "Unknown Orbbec model")
        if (len(self.k1_k6_p1_p2) != 8
                or not all(_finite_number(v) for v in self.k1_k6_p1_p2)):
            raise LiveCalibrationError("DISTORTION_COEFFICIENTS_INVALID", "Invalid distortion")
        if self.sdk_model == 0 and any(v != 0 for v in self.k1_k6_p1_p2):
            raise LiveCalibrationError("DISTORTION_COEFFICIENTS_INVALID", "NONE with nonzero coeffs")


@dataclass(frozen=True, slots=True)
class LiveCalibrationSnapshot:
    depth_intrinsics: LiveIntrinsics
    color_intrinsics: LiveIntrinsics
    depth_distortion: LiveDistortion
    color_distortion: LiveDistortion
    rotation_C_D: tuple[float, ...]
    translation_C_D_m: tuple[float, float, float]
    depth_scale_m_per_unit: float
    alignment_mode: str = "disabled"
    timestamp_domain: str = "sdk_reported_unverified"
    source_kind: str = "NATIVE_SAME_FRAMESET"
    coordinate_frame: str = "depth_optical"
    units: str = "m"

    def __post_init__(self) -> None:
        if (not isinstance(self.depth_intrinsics, LiveIntrinsics)
                or not isinstance(self.color_intrinsics, LiveIntrinsics)
                or not isinstance(self.depth_distortion, LiveDistortion)
                or not isinstance(self.color_distortion, LiveDistortion)):
            raise LiveCalibrationError("LIVE_CALIBRATION_MISSING", "Invalid calibration DTO")
        if (not _finite_number(self.depth_scale_m_per_unit)
                or self.depth_scale_m_per_unit <= 0):
            raise LiveCalibrationError("DEPTH_SCALE_INVALID", "Invalid depth scale")
        if (self.alignment_mode != "disabled" or self.coordinate_frame != "depth_optical"
                or self.units != "m" or self.source_kind != "NATIVE_SAME_FRAMESET"
                or self.timestamp_domain != "sdk_reported_unverified"):
            raise LiveCalibrationError("UNEXPECTED_ALIGNMENT", "Unexpected stream contract")
        r = self.rotation_C_D
        t = self.translation_C_D_m
        if (len(r) != 9 or len(t) != 3
                or not all(_finite_number(v) for v in (*r, *t))):
            raise LiveCalibrationError("EXTRINSICS_INVALID", "Invalid extrinsics shape")
        rows = (r[:3], r[3:6], r[6:9])
        for i in range(3):
            for j in range(3):
                dot = sum(x * y for x, y in zip(rows[i], rows[j]))
                if abs(dot - (1.0 if i == j else 0.0)) > 1e-3:
                    raise LiveCalibrationError("EXTRINSICS_INVALID", "Non-orthonormal rotation")
        det = (r[0]*(r[4]*r[8]-r[5]*r[7])
               - r[1]*(r[3]*r[8]-r[5]*r[6])
               + r[2]*(r[3]*r[7]-r[4]*r[6]))
        if abs(det - 1.0) > 1e-3:
            raise LiveCalibrationError("EXTRINSICS_INVALID", "Improper rotation")

    @property
    def fingerprint(self) -> str:
        canonical = json.dumps(asdict(self), sort_keys=True,
                               separators=(",", ":"), allow_nan=False)
        return sha256(canonical.encode("utf-8")).hexdigest()

    @classmethod
    def from_native_packet(cls, packet: Any) -> "LiveCalibrationSnapshot":
        """Copy all primitives from one native read_next() result; no SDK references."""
        required = ("depth_intrinsics", "color_intrinsics", "depth_distortion",
                    "color_distortion", "depth_to_color", "depth_scale_m_per_unit",
                    "depth", "color", "align_disabled")
        if any(not hasattr(packet, name) for name in required):
            raise LiveCalibrationError("LIVE_CALIBRATION_MISSING", "Native calibration fields missing")
        try:
            def intr(k: Any) -> LiveIntrinsics:
                return LiveIntrinsics(int(k.width), int(k.height), float(k.fx),
                                      float(k.fy), float(k.cx), float(k.cy))

            def dist(d: Any) -> LiveDistortion:
                return LiveDistortion(int(d.sdk_model),
                                      tuple(float(v) for v in d.k1_k6_p1_p2))

            if packet.align_disabled is not True:
                raise LiveCalibrationError("UNEXPECTED_ALIGNMENT", "Alignment enabled")
            snap = cls(
                depth_intrinsics=intr(packet.depth_intrinsics),
                color_intrinsics=intr(packet.color_intrinsics),
                depth_distortion=dist(packet.depth_distortion),
                color_distortion=dist(packet.color_distortion),
                rotation_C_D=tuple(float(v) for v in packet.depth_to_color.rotation),
                translation_C_D_m=tuple(float(v)/1000.0 for v in packet.depth_to_color.translation_mm),
                depth_scale_m_per_unit=float(packet.depth_scale_m_per_unit),
            )
            if ((snap.depth_intrinsics.width, snap.depth_intrinsics.height)
                    != (int(packet.depth.width), int(packet.depth.height))
                    or (snap.color_intrinsics.width, snap.color_intrinsics.height)
                    != (int(packet.color.width), int(packet.color.height))):
                raise LiveCalibrationError("INTRINSICS_INVALID", "Grid mismatch")
            return snap
        except LiveCalibrationError:
            raise
        except (AttributeError, TypeError, ValueError, OverflowError) as exc:
            raise LiveCalibrationError("LIVE_CALIBRATION_MISSING", "Malformed native calibration") from exc
