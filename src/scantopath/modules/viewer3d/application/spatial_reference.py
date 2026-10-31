"""UXH-01.2: renderer-neutral finite reference grids.

All planes are SCENE-COORDINATE VISUAL AIDS; none is a calibrated floor,
robot/world pose, or assertion that an external PLY/OBJ has metric units.
Never transforms input XYZ or includes grid segments in source geometry.
"""
from __future__ import annotations

from dataclasses import dataclass
import math

GRID_MODES = frozenset({"xy", "xz", "yz", "base"})
HALF_LINES = 10  # Hard budget: 42 independent segments at most.


@dataclass(frozen=True, slots=True)
class GridPlan:
    mode: str
    normal_axis: int
    plane_value: float
    step: float
    segments: tuple[
        tuple[tuple[float, float, float], tuple[float, float, float]], ...
    ]


def build_reference_grid(
    bounds: tuple[float, float, float, float, float, float] | list[float],
    mode: str,
) -> GridPlan:
    """Construct a bounded 1-2-5 grid around the source bounding-box center.

    Axis convention is whatever the source scene establishes. For trusted RAW
    depth_optical, X=right, Y=down, Z=forward. For untrusted PLY/OBJ it is
    ONLY the coordinate basis used to draw the file, not verified units.
    """
    if type(mode) is not str or mode not in GRID_MODES:
        raise ValueError("INVALID_REFERENCE_GRID")
    if (not isinstance(bounds, (tuple, list)) or len(bounds) != 6 or
            any(type(v) not in (float, int) or not math.isfinite(v)
                for v in bounds) or
            any(bounds[i] > bounds[i + 1] for i in (0, 2, 4))):
        raise ValueError("INVALID_GRID_BOUNDS")
    if mode in ("xy", "base"):
        a, b, normal = 0, 1, 2
        plane = float(bounds[4]) if mode == "base" else 0.0
    elif mode == "xz":
        a, b, normal = 0, 2, 1
        plane = 0.0
    else:  # yz
        a, b, normal = 1, 2, 0
        plane = 0.0

    extents = [float(bounds[2 * k + 1] - bounds[2 * k]) for k in (a, b)]
    span = max(extents[0], extents[1], 1e-6)
    if not math.isfinite(span):
        raise ValueError("INVALID_GRID_BOUNDS")
    target = span / 12.0
    if not math.isfinite(target) or target <= 0:
        raise ValueError("INVALID_GRID_BOUNDS")
    base = 10.0 ** math.floor(math.log10(target))
    step = min((base, 2 * base, 5 * base, 10 * base),
               key=lambda k: abs(k - target))
    centers = [(float(bounds[2 * k]) / 2.0 +
                float(bounds[2 * k + 1]) / 2.0) for k in (a, b)]
    scaled = [x / step for x in centers]
    if not all(math.isfinite(x) for x in scaled):
        raise ValueError("INVALID_GRID_EXTENT")
    anchors = [round(x) * step for x in scaled]
    if not all(math.isfinite(x) for x in (*anchors, step)) or step <= 0:
        raise ValueError("INVALID_GRID_EXTENT")

    def vertex(x: float, y: float) -> tuple[float, float, float]:
        v = [0.0, 0.0, 0.0]
        v[normal] = plane
        v[a] = x
        v[b] = y
        if not all(math.isfinite(z) for z in v):
            raise ValueError("INVALID_GRID_EXTENT")
        return tuple(v)

    left = anchors[0] - HALF_LINES * step
    right = anchors[0] + HALF_LINES * step
    bottom = anchors[1] - HALF_LINES * step
    top = anchors[1] + HALF_LINES * step
    segments = []
    for i in range(-HALF_LINES, HALF_LINES + 1):
        x, y = anchors[0] + i * step, anchors[1] + i * step
        segments.append((vertex(x, bottom), vertex(x, top)))
        segments.append((vertex(left, y), vertex(right, y)))
    return GridPlan(mode, normal, plane, step, tuple(segments))
