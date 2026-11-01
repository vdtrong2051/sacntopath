"""FT-05.7: conservative, single-frame geometric object/background isolation.

No AI, Qt, VTK, RAW, SDK or temporal fusion.  This *view-only* heuristic
requires a dominant planar support surface AND a separated foreground component.
When either is absent it fails closed, rather than silently rendering a floor.
"""
from __future__ import annotations

from dataclasses import dataclass
import math
import numpy as np


@dataclass(frozen=True, slots=True)
class IsolationConfig:
    sample_step: int = 5
    ransac_trials: int = 80
    plane_tolerance_m: float = 0.012
    foreground_clearance_m: float = 0.018
    max_foreground_height_m: float = 0.35
    min_background_fraction: float = 0.35
    min_foreground_fraction: float = 0.003
    max_foreground_fraction: float = 0.40
    min_component_cells: int = 18

    def __post_init__(self):
        if (type(self.sample_step) is not int or not 2 <= self.sample_step <= 16
                or type(self.ransac_trials) is not int or not 8 <= self.ransac_trials <= 256
                or type(self.min_component_cells) is not int or not 4 <= self.min_component_cells <= 4096):
            raise ValueError('ISOLATION_CONFIG_INVALID')
        for name in ('plane_tolerance_m', 'foreground_clearance_m',
                     'max_foreground_height_m', 'min_background_fraction',
                     'min_foreground_fraction', 'max_foreground_fraction'):
            v = getattr(self, name)
            if type(v) not in (float, int) or not math.isfinite(v) or v <= 0:
                raise ValueError('ISOLATION_CONFIG_INVALID')
        if not (self.plane_tolerance_m < self.foreground_clearance_m < self.max_foreground_height_m
                and self.min_foreground_fraction < self.max_foreground_fraction < 1
                and self.min_background_fraction < 1):
            raise ValueError('ISOLATION_CONFIG_INVALID')


@dataclass(frozen=True, slots=True)
class IsolationResult:
    status: str
    object_mask: np.ndarray | None   # native depth grid, immutable owned bool array
    plane_support_fraction: float
    foreground_fraction: float
    selected_pixels: int
    message: str

    @property
    def usable(self) -> bool:
        return self.status == 'OBJECT_FOUND' and self.object_mask is not None


def _failure(code: str, support: float = 0., foreground: float = 0.) -> IsolationResult:
    return IsolationResult(code, None, round(float(support), 4),
                           round(float(foreground), 4), 0, code)


def _largest_component(mask: np.ndarray) -> np.ndarray:
    """Return the largest 8-connected component in a bounded sampled grid."""
    h, w = mask.shape
    visited = np.zeros(mask.shape, dtype=bool)
    best: list[int] = []
    # Work only on foreground coordinates; no recursion or external scipy.
    for seed in np.flatnonzero(mask):
        seed = int(seed)
        y, x = divmod(seed, w)
        if visited[y, x]:
            continue
        visited[y, x] = True
        work = [seed]
        component: list[int] = []
        while work:
            i = work.pop()
            yy, xx = divmod(i, w)
            component.append(i)
            for y2 in range(max(0, yy-1), min(h, yy+2)):
                for x2 in range(max(0, xx-1), min(w, xx+2)):
                    if mask[y2, x2] and not visited[y2, x2]:
                        visited[y2, x2] = True
                        work.append(y2*w+x2)
        if len(component) > len(best):
            best = component
    out = np.zeros(mask.shape, dtype=bool)
    if best:
        out.ravel()[best] = True
    return out


def isolate_object_depth(depth_u16: np.ndarray, depth_scale_m: float,
                         intrinsics: object,
                         *, depth_roi: tuple[int, int, int, int] | None = None,
                         config: IsolationConfig | None = None) -> IsolationResult:
    """Fit local 3D support plane; retain connected camera-side foreground.

    Plane calibration is taken from the SAME RGB-D frame. No object semantics or
    metric accuracy claim. A tight ROI without visible support must fail closed.
    """
    cfg = config or IsolationConfig()
    if (not isinstance(depth_u16, np.ndarray) or depth_u16.dtype != np.uint16
            or depth_u16.ndim != 2 or depth_u16.size == 0 or depth_u16.size > 32_000_000
            or type(depth_scale_m) not in (float, int) or not math.isfinite(depth_scale_m)
            or depth_scale_m <= 0):
        raise ValueError('ISOLATION_INPUT_INVALID')
    height, width = depth_u16.shape
    if depth_roi is None:
        x, y, rw, rh = 0, 0, width, height
    else:
        if (not isinstance(depth_roi, tuple) or len(depth_roi) != 4
                or any(type(v) is not int for v in depth_roi)):
            raise ValueError('ISOLATION_ROI_INVALID')
        x, y, rw, rh = depth_roi
        if x < 0 or y < 0 or rw < 2 or rh < 2 or x+rw > width or y+rh > height:
            raise ValueError('ISOLATION_ROI_INVALID')
    try:
        fx, fy, cx, cy = (float(getattr(intrinsics, k)) for k in ('fx','fy','cx','cy'))
    except (AttributeError, TypeError, ValueError) as exc:
        raise ValueError('ISOLATION_CALIBRATION_INVALID') from exc
    if not all(map(math.isfinite, (fx, fy, cx, cy))) or fx <= 0 or fy <= 0:
        raise ValueError('ISOLATION_CALIBRATION_INVALID')

    step = cfg.sample_step
    roi = depth_u16[y:y+rh, x:x+rw]
    sample = roi[::step, ::step]
    sy, sx = np.nonzero((sample != 0) & (sample != 65535))
    if len(sy) < max(100, cfg.min_component_cells * 4):
        return _failure('ISOLATION_INSUFFICIENT_DEPTH')
    z = sample[sy, sx].astype(np.float64) * depth_scale_m
    # Avoid invalid/noisy extremes but do NOT impose an object-specific height.
    good = np.isfinite(z) & (z >= 0.18) & (z <= 3.0)
    if int(good.sum()) < 100:
        return _failure('ISOLATION_INSUFFICIENT_DEPTH')
    sy, sx, z = sy[good], sx[good], z[good]
    u, v = x + sx.astype(np.float64)*step, y + sy.astype(np.float64)*step
    pts = np.column_stack(((u - cx)/fx*z, (v - cy)/fy*z, z))
    # Deterministic RANSAC over the downsampled cloud, bounded CPU budget.
    rng = np.random.default_rng(5705)
    best = np.zeros(pts.shape[0], dtype=bool)
    best_count = 0
    for _ in range(cfg.ransac_trials):
        ids = rng.choice(pts.shape[0], size=3, replace=False)
        p0, p1, p2 = pts[ids]
        n = np.cross(p1-p0, p2-p0)
        nn = np.linalg.norm(n)
        if nn <= 1e-9:
            continue
        n /= nn
        d = -float(n @ p0)
        matches = np.abs(pts @ n + d) <= cfg.plane_tolerance_m
        c = int(matches.sum())
        if c > best_count:
            best_count, best = c, matches
    fraction = best_count / pts.shape[0]
    if fraction < cfg.min_background_fraction or best_count < 64:
        return _failure('ISOLATION_NO_SUPPORT_PLANE', fraction)
    # Least-squares refit on inliers for improved precision and stability.
    support_pts = pts[best]
    center = support_pts.mean(axis=0)
    _u, _s, vt = np.linalg.svd(support_pts-center, full_matrices=False)
    n = vt[-1]
    d = -float(n @ center)
    if abs(d) < 0.05:
        return _failure('ISOLATION_NO_SUPPORT_PLANE', fraction)
    side = 1.0 if d > 0 else -1.0  # camera origin is on this side
    plane_residual = (pts @ n + d) * side
    front = ((plane_residual > cfg.foreground_clearance_m)
             & (plane_residual < cfg.max_foreground_height_m))
    fg_fraction = float(front.mean())
    if not cfg.min_foreground_fraction <= fg_fraction <= cfg.max_foreground_fraction:
        return _failure('ISOLATION_UNCERTAIN_FOREGROUND', fraction, fg_fraction)

    grid = np.zeros(sample.shape, dtype=bool)
    grid[sy[front], sx[front]] = True
    component = _largest_component(grid)
    count = int(component.sum())
    if count < cfg.min_component_cells:
        return _failure('ISOLATION_NO_CONNECTED_OBJECT', fraction, fg_fraction)
    # Reject scenes with comparably sized competing objects; no silent choice.
    secondary = _largest_component(grid & ~component)
    if int(secondary.sum()) >= max(cfg.min_component_cells, int(count * 0.6)):
        return _failure('ISOLATION_AMBIGUOUS_OBJECTS', fraction, fg_fraction)
    # Preserve native pixel lineage; do not interpolate XYZ or fill holes.
    yy, xx = np.indices((rh, rw), dtype=np.float32)
    depth_roi_metric = roi.astype(np.float32) * np.float32(depth_scale_m)
    # Signed camera-side distance is a linear function of camera-space XYZ.
    plane_dist = ((n[0] * ((x + xx - cx)/fx) +
                   n[1] * ((y + yy - cy)/fy) + n[2]) * depth_roi_metric + d) * side
    valid = ((roi != 0) & (roi != 65535) & np.isfinite(depth_roi_metric)
             & (depth_roi_metric >= 0.18) & (depth_roi_metric <= 3.0))
    height_gate = ((plane_dist > cfg.foreground_clearance_m)
                   & (plane_dist < cfg.max_foreground_height_m))
    # 1 sampled cell corresponds to step x step depth pixels, not nearest rounded pixel.
    expanded = np.repeat(np.repeat(component, step, axis=0), step, axis=1)[:rh, :rw]
    local_mask = valid & height_gate & expanded
    selected = int(local_mask.sum())
    if selected < cfg.min_component_cells * 2:
        return _failure('ISOLATION_NO_CONNECTED_OBJECT', fraction, fg_fraction)
    output = np.zeros(depth_u16.shape, dtype=bool)
    output[y:y+rh, x:x+rw] = local_mask
    output.setflags(write=False)
    return IsolationResult('OBJECT_FOUND', output, round(float(fraction), 4),
                           round(fg_fraction, 4), selected, 'OBJECT_FOUND')
