
"""GD2-10.05: immutable single-view XYZRGB from decoded native grids.

Pure application orchestration. RAW read/checksum and MJPEG decoding are owned
by GD2-09; this module never reads a store, drives a camera or writes output.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass
from hashlib import sha256
import json
import re
from typing import Mapping

import numpy as np

from scantopath.domain.raw_rgbd import RawRgbdCaptureMetadataV2
from .calibration import CalibrationContract
from .unprojection import unproject_depth
from .validity import DepthRangePolicy, ValidGeometry, select_valid_geometry
from .color_projection import project_to_color


class SingleViewError(ValueError):
    def __init__(self, code: str, message: str) -> None:
        self.code = code
        super().__init__(message)


@dataclass(frozen=True, slots=True)
class SingleViewQuality:
    total_depth_pixels: int
    valid_xyz_points: int
    rejected_depth_pixels: int
    projected_in_color_bounds: int
    self_occluded_points: int
    colored_points: int
    uncolored_xyz_points: int
    timestamp_delta_us: int
    timestamp_domain: str = "sdk_reported_unverified"


@dataclass(frozen=True, slots=True)
class SingleViewXYZRGB:
    """XYZ has N rows; RGB has only M valid pixel associations (M <= N).

    No fabricated RGB is stored for points with color_valid=False.
    Colored row j belongs to XYZ row colored_point_indices[j].
    """
    geometry: ValidGeometry
    color_valid: np.ndarray             # (N,) bool
    color_pixel_uv: np.ndarray          # (N,2) int32
    colored_point_indices: np.ndarray   # (M,) int32
    colors_rgb: np.ndarray              # (M,3) uint8
    quality_stats: SingleViewQuality
    calibration_fingerprint: str
    source_raw_sha256: tuple[tuple[str, str], ...]
    algorithm_parameters: tuple[tuple[str, float | None], ...]
    color_status: str
    algorithm_id: str = "scantopath.single_view_xyzrgb"
    algorithm_version: str = "GD2-10.05-v1"
    metric_validated: bool = False
    source_integrity_status: str = "NOT_VERIFIED_BY_GEOMETRY"

    @property
    def source_capture_id(self) -> str:
        return self.geometry.source_capture_id

    @property
    def points_xyz_m(self) -> np.ndarray:
        return self.geometry.points_xyz_m

    @property
    def depth_source_uv(self) -> np.ndarray:
        return self.geometry.depth_source_uv

    @property
    def depth_valid(self) -> np.ndarray:
        return self.geometry.depth_valid

    @property
    def units(self) -> str:
        return self.geometry.units

    @property
    def frame(self) -> str:
        return self.geometry.frame


class GeometryService:
    """GD2-09 decoded arrays -> GD2-10 SingleViewXYZRGB (no I/O)."""

    @staticmethod
    def process(
        *,
        depth_u16: np.ndarray,
        color_rgb: np.ndarray,
        metadata: RawRgbdCaptureMetadataV2,
        capture_id: str,
        depth_policy: DepthRangePolicy | None = None,
        occlusion_tolerance_m: float = 0.003,
        source_raw_sha256: Mapping[str, str] | None = None,
    ) -> SingleViewXYZRGB:
        if not isinstance(metadata, RawRgbdCaptureMetadataV2):
            raise SingleViewError(
                "RAW_METADATA_INVALID", "Expected RAW v2 metadata"
            )
        if capture_id != metadata.capture_id or not isinstance(capture_id, str):
            raise SingleViewError(
                "CAPTURE_CONTEXT_MISMATCH", "Capture IDs differ"
            )
        if (
            not isinstance(color_rgb, np.ndarray)
            or color_rgb.dtype != np.uint8
            or color_rgb.shape != (
                metadata.color.height,
                metadata.color.width,
                3,
            )
            or not color_rgb.flags.c_contiguous
        ):
            raise SingleViewError(
                "RGB_ARRAY_INVALID",
                "Expected native-grid contiguous RGB uint8 HxWx3",
            )

        raw_hashes: tuple[tuple[str, str], ...] = ()
        if source_raw_sha256 is not None:
            if (
                not isinstance(source_raw_sha256, Mapping)
                or set(source_raw_sha256) != {"color.mjpg", "depth.y16"}
                or any(
                    not isinstance(value, str)
                    or re.fullmatch(r"[0-9a-f]{64}", value) is None
                    for value in source_raw_sha256.values()
                )
            ):
                raise SingleViewError(
                    "SOURCE_HASH_INVALID",
                    "Expected two lowercase RAW SHA-256 values",
                )

            # Hash values are caller-provided. GD2-09's verified
            # reader, not this service, establishes RAW integrity.
            raw_hashes = tuple(sorted(source_raw_sha256.items()))

        calibration = CalibrationContract.from_metadata(metadata)

        projection = unproject_depth(
            depth_u16,
            calibration=calibration,
            capture_id=capture_id,
        )

        geometry = select_valid_geometry(
            projection,
            calibration=calibration,
            policy=depth_policy,
        )

        color_map = project_to_color(
            geometry,
            calibration=calibration,
            occlusion_tolerance_m=occlusion_tolerance_m,
        )

        valid = np.array(
            color_map.color_valid,
            dtype=np.bool_,
            copy=True,
        )
        uv = np.array(
            color_map.color_pixel_uv,
            dtype=np.int32,
            order="C",
            copy=True,
        )

        n = geometry.points_xyz_m.shape[0]

        if valid.shape != (n,) or uv.shape != (n, 2):
            raise SingleViewError(
                "COLOR_REGISTRATION_FAILED",
                "Projection/XYZ shapes differ",
            )

        selected = np.flatnonzero(valid).astype(np.int32)

        if selected.size:
            px = uv[selected, 0]
            py = uv[selected, 1]

            if (
                np.any(px < 0)
                or np.any(px >= metadata.color.width)
                or np.any(py < 0)
                or np.any(py >= metadata.color.height)
            ):
                raise SingleViewError(
                    "COLOR_REGISTRATION_FAILED",
                    "Projected pixel outside Color grid",
                )

            colors = np.array(
                color_rgb[py, px],
                dtype=np.uint8,
                order="C",
                copy=True,
            )
        else:
            colors = np.empty((0, 3), dtype=np.uint8)

        if colors.shape != (selected.size, 3):
            raise SingleViewError(
                "COLOR_REGISTRATION_FAILED",
                "RGB selection shape mismatch",
            )

        for array in (valid, uv, selected, colors):
            array.setflags(write=False)

        quality = SingleViewQuality(
            total_depth_pixels=int(geometry.depth_valid.size),
            valid_xyz_points=n,
            rejected_depth_pixels=int(
                geometry.depth_valid.size - n
            ),
            projected_in_color_bounds=int(
                np.count_nonzero(color_map.in_color_bounds)
            ),
            self_occluded_points=int(
                np.count_nonzero(color_map.occluded)
            ),
            colored_points=int(selected.size),
            uncolored_xyz_points=int(n - selected.size),
            timestamp_delta_us=metadata.observed_timestamp_delta_us,
        )

        fingerprint = sha256(
            json.dumps(
                asdict(calibration),
                sort_keys=True,
                separators=(",", ":"),
                allow_nan=False,
            ).encode("utf-8")
        ).hexdigest()

        status = (
            "XYZ_ONLY_NO_VALID_COLOR"
            if selected.size == 0
            else "XYZRGB_ALL_COLORED"
            if selected.size == n
            else "XYZRGB_PARTIAL_COLOR"
        )

        return SingleViewXYZRGB(
            geometry=geometry,
            color_valid=valid,
            color_pixel_uv=uv,
            colored_point_indices=selected,
            colors_rgb=colors,
            quality_stats=quality,
            calibration_fingerprint=fingerprint,
            source_raw_sha256=raw_hashes,
            algorithm_parameters=(
                ("min_depth_m", geometry.depth_policy.min_depth_m),
                ("max_depth_m", geometry.depth_policy.max_depth_m),
                (
                    "occlusion_tolerance_m",
                    float(occlusion_tolerance_m),
                ),
            ),
            color_status=status,
        )
