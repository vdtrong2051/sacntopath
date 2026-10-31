"""Source-depth pixel -> original XYZ row, independent of VTK and Qt.

The grid is depth_optical, NOT the RGB camera image or the rendered viewport.
Never derive a metric point from the temporary float32 PLY.
"""
from __future__ import annotations

from dataclasses import dataclass
import numpy as np


class DepthPickError(ValueError):
    def __init__(self, code: str) -> None:
        super().__init__(code)
        self.code = code


@dataclass(frozen=True, slots=True)
class DepthPixelHit:
    index: int
    u: int
    v: int
    snapped: bool


class DepthPixelPicker:
    """Explicit depth-pixel lookup to source XYZ indices (not PLY indices)."""

    def __init__(self, view):
        if (getattr(view, 'frame', None) != 'depth_optical'
                or getattr(view, 'units', None) != 'm'
                or getattr(view, 'metric_validated', None) is not False):
            raise DepthPickError('DEPTH_PROVENANCE_INVALID')
        points = view.points_xyz_m
        uv = view.depth_source_uv
        valid = view.depth_valid
        if (not isinstance(points, np.ndarray) or points.dtype != np.float64
                or points.ndim != 2 or points.shape[1] != 3
                or not isinstance(uv, np.ndarray) or uv.dtype != np.int32
                or uv.shape != (len(points), 2)
                or not isinstance(valid, np.ndarray) or valid.dtype != np.bool_
                or valid.ndim != 2 or not points.flags.c_contiguous
                or not uv.flags.c_contiguous or not valid.flags.c_contiguous):
            raise DepthPickError('DEPTH_INPUT_INVALID')
        height, width = valid.shape
        if (height == 0 or width == 0 or len(points) == 0
                or len(points) != np.count_nonzero(valid)
                or len(points) >= np.iinfo(np.int32).max):
            raise DepthPickError('DEPTH_PIXEL_MAPPING_INVALID')
        u = uv[:, 0]
        v = uv[:, 1]
        if (np.any(u < 0) or np.any(u >= width)
                or np.any(v < 0) or np.any(v >= height)
                or not np.all(valid[v, u])):
            raise DepthPickError('DEPTH_PIXEL_MAPPING_INVALID')
        flat = v.astype(np.int64) * width + u
        if np.unique(flat).size != len(points):
            raise DepthPickError('DEPTH_PIXEL_DUPLICATE')
        indices = np.full((height, width), -1, dtype=np.int32)
        indices[v, u] = np.arange(len(points), dtype=np.int32)
        indices.setflags(write=False)
        self._indices = indices
        self._view = view
        self.width = width
        self.height = height

    def hit(self, u: int, v: int, *, radius: int = 3) -> DepthPixelHit | None:
        """Invalid depth has no 3D point. Tiny nearest-valid snap is explicit."""
        if type(u) is not int or type(v) is not int:
            raise DepthPickError('DEPTH_PIXEL_INVALID')
        if not (0 <= u < self.width and 0 <= v < self.height):
            return None
        direct = int(self._indices[v, u])
        if direct >= 0:
            return DepthPixelHit(direct, u, v, False)
        if type(radius) is not int or not 0 <= radius <= 5:
            raise DepthPickError('DEPTH_SNAP_RADIUS_INVALID')
        if radius == 0:
            return None
        u0, u1 = max(0, u-radius), min(self.width, u+radius+1)
        v0, v1 = max(0, v-radius), min(self.height, v+radius+1)
        rows, cols = np.nonzero(self._indices[v0:v1, u0:u1] >= 0)
        if len(rows) == 0:
            return None
        rows = rows + v0
        cols = cols + u0
        distances = (cols-u)**2 + (rows-v)**2
        mask = distances <= radius*radius
        if not np.any(mask):
            return None
        candidates = np.flatnonzero(mask)
        i = int(candidates[np.argmin(distances[mask])])
        uu, vv = int(cols[i]), int(rows[i])
        return DepthPixelHit(int(self._indices[vv, uu]), uu, vv, True)

    def make_rgb_depth_image(self) -> np.ndarray:
        """Visual preview at depth resolution: grayscale Z with real RGB where known.

        The image is a SELECTOR only, never a new metric/color artifact.
        """
        xyz = self._view.points_xyz_m
        uv = self._view.depth_source_uv
        u, v = uv[:, 0], uv[:, 1]
        image = np.zeros((self.height, self.width, 3), dtype=np.uint8)
        z = xyz[:, 2]
        if not np.isfinite(z).all() or np.any(z <= 0):
            raise DepthPickError('DEPTH_COORDINATE_INVALID')
        low, high = float(np.min(z)), float(np.max(z))
        scale = np.clip((z-low)/max(high-low, 1e-9), 0.0, 1.0)
        gray = np.asarray(185.0-115.0*scale, dtype=np.uint8)
        image[v, u] = gray[:, None]
        rgb_indices = self._view.colored_point_indices
        colors = self._view.colors_rgb
        if (not isinstance(rgb_indices, np.ndarray) or rgb_indices.dtype != np.int32
                or rgb_indices.ndim != 1 or not isinstance(colors, np.ndarray)
                or colors.dtype != np.uint8 or colors.shape != (len(rgb_indices), 3)
                or np.any(rgb_indices < 0) or np.any(rgb_indices >= len(xyz))):
            raise DepthPickError('DEPTH_COLOR_MAPPING_INVALID')
        image[v[rgb_indices], u[rgb_indices]] = colors
        return np.ascontiguousarray(image)
