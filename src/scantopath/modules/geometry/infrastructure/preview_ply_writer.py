"""UXH-01.1: binary RGB-subset Preview PLY writer (not a certified artifact)."""
from __future__ import annotations

from hashlib import sha256
from pathlib import Path

import numpy as np

from scantopath.application.contracts.preview import GeometryPreviewError, PreviewReceipt
from scantopath.modules.geometry.application.service import SingleViewXYZRGB

MAX_PREVIEW_VERTICES = 1_500_000
MAX_PREVIEW_BYTES = 256 * 1024 * 1024
_VERTEX_DTYPE = np.dtype([
    ("x", "<f4"), ("y", "<f4"), ("z", "<f4"),
    ("red", "u1"), ("green", "u1"), ("blue", "u1"),
])


def write_preview_ply(view: SingleViewXYZRGB, path: Path) -> PreviewReceipt:
    """Export only real RGB points; VTK point IDs are not source XYZ row IDs."""
    if not isinstance(view, SingleViewXYZRGB):
        raise GeometryPreviewError("PREVIEW_INPUT_INVALID")
    if view.frame != "depth_optical" or view.units != "m" or view.metric_validated:
        raise GeometryPreviewError("PREVIEW_PROVENANCE_INVALID")
    xyz = view.points_xyz_m
    ix = view.colored_point_indices
    rgb = view.colors_rgb
    if (not isinstance(xyz, np.ndarray) or xyz.dtype != np.float64 or
            xyz.ndim != 2 or xyz.shape[1] != 3 or
            not isinstance(ix, np.ndarray) or ix.dtype != np.int32 or ix.ndim != 1 or
            not isinstance(rgb, np.ndarray) or rgb.dtype != np.uint8 or
            rgb.shape != (ix.size, 3) or
            not 1 <= ix.size <= min(xyz.shape[0], MAX_PREVIEW_VERTICES) or
            np.any(ix < 0) or np.any(ix >= xyz.shape[0]) or
            np.unique(ix).size != ix.size):
        raise GeometryPreviewError("PREVIEW_POINT_MAPPING_INVALID")
    selected = xyz[ix]
    if not np.isfinite(selected).all() or np.any(selected[:, 2] <= 0):
        raise GeometryPreviewError("PREVIEW_COORDINATES_INVALID")
    vertices = np.empty(ix.size, dtype=_VERTEX_DTYPE)
    for key, j in (("x", 0), ("y", 1), ("z", 2)):
        vertices[key] = selected[:, j]
    for key, j in (("red", 0), ("green", 1), ("blue", 2)):
        vertices[key] = rgb[:, j]
    if not all(np.isfinite(vertices[key]).all() for key in ("x", "y", "z")):
        raise GeometryPreviewError("PREVIEW_FLOAT32_OVERFLOW")
    header = (
        "ply\nformat binary_little_endian 1.0\n"
        "comment ScanToPath GD2-10.08.1 temporary visual preview only\n"
        "comment not a validated metric artifact or a source point-index map\n"
        f"element vertex {ix.size}\n"
        "property float x\nproperty float y\nproperty float z\n"
        "property uchar red\nproperty uchar green\nproperty uchar blue\n"
        "end_header\n"
    ).encode("ascii")
    if len(header) + vertices.nbytes > MAX_PREVIEW_BYTES:
        raise GeometryPreviewError("PREVIEW_SIZE_LIMIT")
    path = Path(path)
    if path.suffix.lower() != ".ply" or not path.parent.is_dir() or path.exists():
        raise GeometryPreviewError("PREVIEW_DESTINATION_INVALID")
    with path.open("xb") as stream:
        stream.write(header)
        stream.write(vertices.tobytes(order="C"))
    digest = sha256(path.read_bytes()).hexdigest()
    return PreviewReceipt(
        path=path, capture_id=view.source_capture_id,
        xyz_points=int(xyz.shape[0]), colored_points=int(ix.size),
        ply_sha256=digest,
    )
