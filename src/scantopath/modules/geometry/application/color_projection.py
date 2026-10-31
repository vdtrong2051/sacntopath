
"""GD2-10.04: depth-optical XYZ -> color pixels, deterministic visibility.

No JPEG decoding, color sampling, SDK calls, SQLite or hardware access.
Color projection uses nearest pixel center (floor(u + 0.5)), with a
per-color-pixel z-buffer. The z-buffer handles only collisions among supplied
Depth points, not unknown RGB-only occluders or frame-timing errors.
"""
from __future__ import annotations

from dataclasses import dataclass
from math import isfinite

import numpy as np

from .calibration import CalibrationContract
from .validity import ValidGeometry


class ColorProjectionError(ValueError):
    def __init__(self, code: str, message: str) -> None:
        self.code = code
        super().__init__(message)


@dataclass(frozen=True, slots=True)
class ColorProjection:
    source_capture_id: str
    color_uv: np.ndarray
    color_pixel_uv: np.ndarray
    color_valid: np.ndarray
    in_color_bounds: np.ndarray
    occluded: np.ndarray
    color_z_m: np.ndarray
    occlusion_tolerance_m: float
    sampling: str = "nearest_half_up"
    frame: str = "color_optical"


def project_to_color(
    geometry: ValidGeometry,
    *,
    calibration: CalibrationContract,
    occlusion_tolerance_m: float = 0.003,
) -> ColorProjection:
    """Project metric XYZ into the original Color pixel grid.

    Supports Orbbec NONE=0 and BROWN_CONRADY=3.
    Other Color distortion models fail closed, including K6=4.
    """
    if not isinstance(geometry, ValidGeometry):
        raise ColorProjectionError(
            "GEOMETRY_INVALID", "Expected ValidGeometry"
        )

    if not isinstance(calibration, CalibrationContract):
        raise ColorProjectionError(
            "CALIBRATION_INVALID", "Expected CalibrationContract"
        )

    if (
        not geometry.source_capture_id
        or geometry.source_capture_id != calibration.capture_id
    ):
        raise ColorProjectionError(
            "CAPTURE_CONTEXT_MISMATCH", "Capture IDs differ"
        )

    if (
        (
            geometry.units,
            geometry.frame,
            calibration.units,
            calibration.frame,
        )
        != ("m", "depth_optical", "m", "depth_optical")
        or geometry.provenance != "RAW_V2_PER_CAPTURE"
    ):
        raise ColorProjectionError(
            "GEOMETRY_INVALID", "Invalid units, frame or provenance"
        )

    if (
        type(occlusion_tolerance_m) not in (int, float)
        or not isfinite(occlusion_tolerance_m)
        or occlusion_tolerance_m < 0
    ):
        raise ColorProjectionError(
            "OCCLUSION_POLICY_INVALID",
            "Tolerance must be nonnegative, finite metres",
        )

    xyz = geometry.points_xyz_m
    uv_source = geometry.depth_source_uv
    mask_source = geometry.depth_valid

    dk = calibration.depth_K
    ck = calibration.color_K

    if (
        not isinstance(xyz, np.ndarray)
        or xyz.dtype != np.float64
        or xyz.ndim != 2
        or xyz.shape[1] != 3
        or xyz.shape[0] == 0
        or not isinstance(uv_source, np.ndarray)
        or uv_source.dtype != np.int32
        or uv_source.shape != (xyz.shape[0], 2)
        or not isinstance(mask_source, np.ndarray)
        or mask_source.dtype != np.bool_
        or mask_source.shape != (dk.height, dk.width)
    ):
        raise ColorProjectionError(
            "GEOMETRY_INVALID", "Invalid geometry arrays"
        )

    if (
        xyz.shape[0] > 10_000_000
        or ck.width * ck.height > 32_000_000
    ):
        raise ColorProjectionError(
            "RESOURCE_LIMIT_EXCEEDED",
            "Point or Color grid limit exceeded",
        )

    if (
        int(np.count_nonzero(mask_source)) != xyz.shape[0]
        or not np.isfinite(xyz).all()
        or not (xyz[:, 2] > 0).all()
        or np.any(uv_source[:, 0] < 0)
        or np.any(uv_source[:, 0] >= dk.width)
        or np.any(uv_source[:, 1] < 0)
        or np.any(uv_source[:, 1] >= dk.height)
        or not mask_source[
            uv_source[:, 1], uv_source[:, 0]
        ].all()
    ):
        raise ColorProjectionError(
            "GEOMETRY_INVALID",
            "Invalid points or Depth pixel lineage",
        )

    if (
        ck.width <= 0
        or ck.height <= 0
        or ck.width >= 2**31
        or ck.height >= 2**31
        or not all(
            isfinite(v)
            for v in (ck.fx, ck.fy, ck.cx, ck.cy)
        )
        or ck.fx <= 0
        or ck.fy <= 0
    ):
        raise ColorProjectionError(
            "CALIBRATION_INVALID", "Invalid Color intrinsics"
        )

    distortion = calibration.color_distortion

    if distortion.sdk_model not in (0, 3):
        raise ColorProjectionError(
            "DISTORTION_MODEL_UNSUPPORTED",
            "Unsupported Color distortion model",
        )

    coeff = distortion.k1_k6_p1_p2

    if len(coeff) != 8 or not all(isfinite(c) for c in coeff):
        raise ColorProjectionError(
            "DISTORTION_COEFFICIENTS_INVALID",
            "Invalid distortion coefficients",
        )

    if (
        distortion.sdk_model == 0
        and any(c != 0 for c in coeff)
    ) or (
        distortion.sdk_model == 3
        and any(c != 0 for c in coeff[3:6])
    ):
        raise ColorProjectionError(
            "DISTORTION_COEFFICIENTS_INVALID",
            "Coefficients incompatible with model",
        )

    rotation = np.asarray(
        calibration.rotation_C_D, dtype=np.float64
    )
    translation = np.asarray(
        calibration.translation_C_D_m, dtype=np.float64
    )

    if (
        rotation.shape != (9,)
        or translation.shape != (3,)
        or not np.isfinite(rotation).all()
        or not np.isfinite(translation).all()
    ):
        raise ColorProjectionError(
            "EXTRINSICS_INVALID", "Invalid D2C transform"
        )

    rotation = rotation.reshape(3, 3)

    if (
        not np.allclose(
            rotation @ rotation.T,
            np.eye(3),
            rtol=0,
            atol=1e-3,
        )
        or abs(np.linalg.det(rotation) - 1.0) > 1e-3
    ):
        raise ColorProjectionError(
            "EXTRINSICS_INVALID",
            "D2C rotation is not in SO(3)",
        )

    # XYZ uses metres. Translation was converted in GD2-10.01.
    color_xyz = xyz @ rotation.T + translation

    z = color_xyz[:, 2].copy()
    count = xyz.shape[0]

    color_uv = np.full(
        (count, 2), np.nan, dtype=np.float64
    )
    pixel_uv = np.full(
        (count, 2), -1, dtype=np.int32
    )
    inside = np.zeros(count, dtype=np.bool_)
    occluded = np.zeros(count, dtype=np.bool_)

    front = np.isfinite(color_xyz).all(axis=1) & (z > 0)
    rows = np.flatnonzero(front)

    if rows.size:
        with np.errstate(
            divide="ignore",
            over="ignore",
            invalid="ignore",
        ):
            x = color_xyz[rows, 0] / z[rows]
            y = color_xyz[rows, 1] / z[rows]

            if distortion.sdk_model == 3:
                # Orbbec RAW order:
                # k1,k2,k3,k4,k5,k6,p1,p2
                k1, k2, k3, _, _, _, p1, p2 = coeff

                r2 = x * x + y * y
                radial = (
                    1
                    + k1 * r2
                    + k2 * r2**2
                    + k3 * r2**3
                )

                x_new = (
                    x * radial
                    + 2 * p1 * x * y
                    + p2 * (r2 + 2 * x * x)
                )
                y_new = (
                    y * radial
                    + p1 * (r2 + 2 * y * y)
                    + 2 * p2 * x * y
                )

                x, y = x_new, y_new

            u = ck.fx * x + ck.cx
            v = ck.fy * y + ck.cy

        finite = np.isfinite(u) & np.isfinite(v)

        color_uv[rows[finite], 0] = u[finite]
        color_uv[rows[finite], 1] = v[finite]

        in_frame = (
            finite
            & (u >= 0)
            & (u < ck.width)
            & (v >= 0)
            & (v < ck.height)
        )

        eligible = rows[in_frame]

        if eligible.size:
            # Nearest center, with ties rounded upward.
            px = np.minimum(
                np.floor(u[in_frame] + 0.5).astype(np.int32),
                ck.width - 1,
            )
            py = np.minimum(
                np.floor(v[in_frame] + 0.5).astype(np.int32),
                ck.height - 1,
            )

            pixel_uv[eligible, 0] = px
            pixel_uv[eligible, 1] = py
            inside[eligible] = True

            # Self-occlusion: nearest Zc for each sampled Color pixel.
            linear_index = (
                py.astype(np.int64) * ck.width + px
            )

            nearest_z = np.full(
                ck.width * ck.height,
                np.inf,
                dtype=np.float64,
            )

            np.minimum.at(
                nearest_z,
                linear_index,
                z[eligible],
            )

            occluded[eligible] = (
                z[eligible]
                > nearest_z[linear_index]
                + occlusion_tolerance_m
            )

    valid = inside & ~occluded

    for array in (
        color_uv,
        pixel_uv,
        inside,
        occluded,
        valid,
        z,
    ):
        array.setflags(write=False)

    return ColorProjection(
        source_capture_id=geometry.source_capture_id,
        color_uv=color_uv,
        color_pixel_uv=pixel_uv,
        color_valid=valid,
        in_color_bounds=inside,
        occluded=occluded,
        color_z_m=z,
        occlusion_tolerance_m=float(
            occlusion_tolerance_m
        ),
    )
