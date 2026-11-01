"""FT-02b: pure per-frame live Depth to bounded XYZ; not a VTK/Qt/RAW service.

Unprojection matches the verified GD2-10 pinhole reference for supported depth
models. No RAW metadata or synthetic Capture IDs are constructed.
"""
from __future__ import annotations

from dataclasses import dataclass
from math import isfinite

import numpy as np
from .live_denoise import local_depth_support_mask
from scantopath.modules.capture.application.live_calibration import (
    LiveCalibrationSnapshot,
)
from scantopath.modules.capture.application.live_stream import LiveRgbdFrame


class LiveGeometryError(ValueError):
    def __init__(self, code: str, detail: str) -> None:
        self.code = code
        super().__init__(detail)


@dataclass(frozen=True, slots=True)
class LiveCloudStats:
    roi_pixels: int
    missing_depth: int
    below_min_depth: int
    above_max_depth: int
    valid_before_sampling: int
    skipped_for_sampling: int
    output_points: int
    filtered_outliers: int = 0  # FT-05.6 display-only support rejection


@dataclass(frozen=True, slots=True)
class LiveCloudFrame:
    points_xyz_m: np.ndarray           # owned, read-only <f4 (N,3), for FT-01 ABI
    depth_source_uv: np.ndarray        # owned, read-only int32 (N,2), retained in process
    camera_generation: int            # lifecycle-owned token; FT-03 supplies it
    depth_frame_index: int
    color_frame_index: int
    depth_timestamp_us: int
    calibration_fingerprint: str
    statistics: LiveCloudStats
    units: str = "m"
    coordinate_frame: str = "depth_optical"
    source_kind: str = "LIVE_NATIVE_FRAME"
    color_status: str = "XYZ_ONLY"
    metric_validated: bool = False

    def __post_init__(self) -> None:
        xyz = self.points_xyz_m
        uv = self.depth_source_uv
        if (not isinstance(xyz, np.ndarray) or xyz.dtype != np.dtype("<f4")
                or xyz.ndim != 2 or xyz.shape[1] != 3 or not 0 < xyz.shape[0] <= 200_000
                or not isinstance(uv, np.ndarray) or uv.dtype != np.int32
                or uv.shape != (xyz.shape[0], 2)
                or not np.isfinite(xyz).all() or not np.all(xyz[:, 2] > 0)):
            raise LiveGeometryError("CLOUD_ARRAY_INVALID", "Live cloud invalid")
        if (type(self.camera_generation) is not int or self.camera_generation <= 0
                or type(self.depth_frame_index) is not int or self.depth_frame_index < 0
                or type(self.color_frame_index) is not int or self.color_frame_index < 0
                or type(self.depth_timestamp_us) is not int or self.depth_timestamp_us < 0):
            raise LiveGeometryError("LIVE_FRAME_KEY_INVALID", "Invalid frame identity")
        if (self.units != "m" or self.coordinate_frame != "depth_optical"
                or self.source_kind != "LIVE_NATIVE_FRAME" or self.color_status != "XYZ_ONLY"
                or self.metric_validated is not False
                or len(self.calibration_fingerprint) != 64):
            raise LiveGeometryError("CLOUD_CONTEXT_INVALID", "Invalid cloud context")
        owned_xyz = np.array(xyz, dtype="<f4", order="C", copy=True)
        owned_uv = np.array(uv, dtype=np.int32, order="C", copy=True)
        owned_xyz.setflags(write=False)
        owned_uv.setflags(write=False)
        object.__setattr__(self, "points_xyz_m", owned_xyz)
        object.__setattr__(self, "depth_source_uv", owned_uv)


class LiveGeometryService:
    @staticmethod
    def process(
        frame: LiveRgbdFrame,
        *,
        camera_generation: int,
        depth_roi: tuple[int, int, int, int] | None = None,  # x,y,width,height on native depth grid
        min_depth_m: float = 0.0,
        max_depth_m: float | None = None,
        point_budget: int = 200_000,
        denoise_mode: str = "off",  # API parity with FT-02 by default
        object_mask: np.ndarray | None = None,  # FT-05.7 native Depth grid, view-only
    ) -> LiveCloudFrame:
        if denoise_mode not in ("off", "standard") or type(denoise_mode) is not str:
            raise LiveGeometryError("DENOISE_MODE_INVALID", "Expected off or standard")
        if not isinstance(frame, LiveRgbdFrame):
            raise LiveGeometryError("LIVE_FRAME_INVALID", "Expected decoded owned live frame")
        if type(camera_generation) is not int or camera_generation <= 0:
            raise LiveGeometryError("LIVE_FRAME_KEY_INVALID", "Generation required")
        if type(point_budget) is not int or not 1 <= point_budget <= 200_000:
            raise LiveGeometryError("RESOURCE_LIMIT_EXCEEDED", "Point budget must be 1..200000")
        if (type(min_depth_m) not in (int, float) or not isfinite(min_depth_m)
                or min_depth_m < 0 or
                (max_depth_m is not None and (type(max_depth_m) not in (int, float)
                or not isfinite(max_depth_m) or max_depth_m <= min_depth_m))):
            raise LiveGeometryError("DEPTH_RANGE_INVALID", "Invalid Depth range")
        calibration: LiveCalibrationSnapshot | None = frame.source.calibration
        if calibration is None:
            raise LiveGeometryError(frame.source.calibration_error or "LIVE_CALIBRATION_MISSING",
                                    "No valid same-frame calibration")
        k = calibration.depth_intrinsics
        depth = frame.depth_u16
        if (depth.dtype != np.uint16 or depth.ndim != 2
                or depth.shape != (k.height, k.width)):
            raise LiveGeometryError("LIVE_FRAME_CALIBRATION_MISMATCH", "Depth native grid mismatch")
        if calibration.depth_scale_m_per_unit != frame.source.depth_scale_m_per_unit:
            raise LiveGeometryError("DEPTH_SCALE_INVALID", "Same-frame scale mismatch")
        distortion = calibration.depth_distortion
        if distortion.sdk_model not in (0, 4) or any(c != 0.0 for c in distortion.k1_k6_p1_p2):
            raise LiveGeometryError("DISTORTION_MODEL_UNSUPPORTED", "Verified inverse unavailable")
        if object_mask is not None and (
                not isinstance(object_mask, np.ndarray) or object_mask.dtype != np.bool_
                or object_mask.shape != depth.shape):
            raise LiveGeometryError("OBJECT_MASK_INVALID", "Mask must be native Depth bool grid")
        height, width = depth.shape
        if depth_roi is None:
            x, y, rw, rh = 0, 0, width, height
        else:
            if (not isinstance(depth_roi, tuple) or len(depth_roi) != 4
                    or any(type(v) is not int for v in depth_roi)):
                raise LiveGeometryError("ROI_INVALID", "ROI must be (x,y,width,height) ints")
            x, y, rw, rh = depth_roi
            if x < 0 or y < 0 or rw <= 0 or rh <= 0 or x+rw > width or y+rh > height:
                raise LiveGeometryError("ROI_INVALID", "ROI outside native depth grid")
        roi = depth[y:y+rh, x:x+rw]
        mask = (roi != 0) & (roi != 65535)
        if object_mask is not None:
            mask &= object_mask[y:y+rh, x:x+rw]
        filtered_outliers = 0
        if denoise_mode == "standard":
            supported = local_depth_support_mask(
                depth, calibration.depth_scale_m_per_unit)
            selected = supported[y:y+rh, x:x+rw]
            filtered_outliers = int(np.count_nonzero(mask & ~selected))
            mask &= selected
        rows, cols = np.nonzero(mask)   # stable native-depth row-major lineage
        total = rw * rh
        missing = int(np.count_nonzero((roi == 0) | (roi == 65535)))
        if rows.size == 0:
            raise LiveGeometryError("EMPTY_VALID_DEPTH", "No valid Depth")
        z = roi[rows, cols].astype(np.float64) * calibration.depth_scale_m_per_unit
        if not np.isfinite(z).all() or np.any(z <= 0):
            raise LiveGeometryError("NONFINITE_PROJECTION", "Depth overflow")
        below = z < min_depth_m
        above = (z > max_depth_m) if max_depth_m is not None else np.zeros(z.shape, dtype=bool)
        keep = ~(below | above)
        count_before = int(np.count_nonzero(keep))
        if count_before == 0:
            raise LiveGeometryError("EMPTY_VALID_DEPTH", "No Depth in configured range")
        rows = rows[keep] + y
        cols = cols[keep] + x
        z = z[keep]
        if count_before > point_budget:
            # Deterministic, ordered, bounded sampling before XYZ allocations.
            selected = (np.arange(point_budget, dtype=np.int64) * count_before) // point_budget
            rows, cols, z = rows[selected], cols[selected], z[selected]
        # Float64 numeric reference, float32 live transport precision only.
        px = ((cols.astype(np.float64) - k.cx) / k.fx) * z
        py = ((rows.astype(np.float64) - k.cy) / k.fy) * z
        xyz64 = np.column_stack((px, py, z))
        if not np.isfinite(xyz64).all() or np.any(xyz64[:, 2] <= 0):
            raise LiveGeometryError("NONFINITE_PROJECTION", "Projection overflow")
        with np.errstate(over="ignore", invalid="ignore"):
            xyz = np.asarray(xyz64, dtype="<f4", order="C")
        if not np.isfinite(xyz).all() or np.any(xyz[:, 2] <= 0):
            raise LiveGeometryError("NONFINITE_PROJECTION", "Projection float32 overflow/underflow")
        uv = np.column_stack((cols, rows)).astype(np.int32, copy=False)
        return LiveCloudFrame(
            points_xyz_m=xyz,
            depth_source_uv=uv,
            camera_generation=camera_generation,
            depth_frame_index=frame.source.depth_frame_index,
            color_frame_index=frame.source.color_frame_index,
            depth_timestamp_us=frame.source.depth_timestamp_us,
            calibration_fingerprint=calibration.fingerprint,
            statistics=LiveCloudStats(
                roi_pixels=total, missing_depth=missing,
                below_min_depth=int(np.count_nonzero(below)),
                above_max_depth=int(np.count_nonzero(above)),
                valid_before_sampling=count_before,
                skipped_for_sampling=count_before-int(z.size),
                output_points=int(z.size),
                filtered_outliers=filtered_outliers,
            ),
        )
