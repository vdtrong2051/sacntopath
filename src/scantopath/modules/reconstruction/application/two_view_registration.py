"""B-01 two-view, CPU-only, bounded multiscale rigid ICP proof.

No Qt, VTK, Orbbec SDK, RAW writes, AI inference, GPU requirement, or
misleading 6DoF trajectory claims. Designed for nearby, overlapping views.
Target = depth0 (world); moving source = depth1. Output T_world_depth1.

SciPy cKDTree is used if present; a bounded NumPy nearest-neighbor fallback
is included for installations without SciPy. Not a substitute for a future
Open3D C++ production tracker / FPFH global registration / pose graph.
"""
from __future__ import annotations
from math import acos, cos, degrees, radians, sin
import numpy as np
from .contracts import InputCloud, RegistrationConfig, RegistrationError, PairQuality, TwoViewResult

try:
    from scipy.spatial import cKDTree
except ImportError:
    cKDTree = None


BACKEND = "scipy_ckdtree" if cKDTree is not None else "numpy_bounded_bruteforce"


def _voxel_representatives(points: np.ndarray, voxel_m: float, maximum: int) -> np.ndarray:
    """Return existing sensor points (not inferred voxel centroids)."""
    grid = np.floor(points / voxel_m).astype(np.int64)
    _, indices = np.unique(grid, axis=0, return_index=True)
    indices.sort()
    if len(indices) > maximum:
        indices = indices[np.linspace(0, len(indices) - 1, maximum, dtype=np.int64)]
    return np.ascontiguousarray(points[indices], dtype=np.float64)


def _nearest(query: np.ndarray, reference: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    if cKDTree is not None:
        d, idx = cKDTree(reference).query(query, k=1, workers=1)
        return d.astype(np.float64), idx.astype(np.intp)
    # Deliberately capped memory: 96x <=3200 float64 distances, no NxN allocation.
    sq = np.einsum("ij,ij->i", reference, reference)
    ds = np.empty(len(query), dtype=np.float64)
    ix = np.empty(len(query), dtype=np.intp)
    for i in range(0, len(query), 96):
        batch = query[i:i + 96]
        delta = np.maximum(0.0, np.einsum("ij,ij->i", batch, batch)[:, None]
                           + sq[None, :] - 2.0 * batch @ reference.T)
        indices = np.argmin(delta, axis=1)
        ix[i:i + len(batch)] = indices
        ds[i:i + len(batch)] = np.sqrt(delta[np.arange(len(batch)), indices])
    return ds, ix


def _rigid_fit(source: np.ndarray, target: np.ndarray) -> np.ndarray:
    """Kabsch, column-vector convention, enforce proper SE(3) det(R)=+1."""
    a, b = source.mean(axis=0), target.mean(axis=0)
    u, _, vt = np.linalg.svd((source - a).T @ (target - b))
    correction = np.eye(3)
    correction[2, 2] = np.sign(np.linalg.det(vt.T @ u.T))
    R = vt.T @ correction @ u.T
    T = np.eye(4, dtype=np.float64)
    T[:3, :3] = R
    T[:3, 3] = b - R @ a
    return T


def _apply(points: np.ndarray, T: np.ndarray) -> np.ndarray:
    return points @ T[:3, :3].T + T[:3, 3]


def _rotation(axis: int, deg: float) -> np.ndarray:
    r = radians(deg)
    c, s = cos(r), sin(r)
    R = np.eye(3)
    if axis == 0:
        R[1:, 1:] = [[c, -s], [s, c]]
    elif axis == 1:
        R[np.ix_([0, 2], [0, 2])] = [[c, s], [-s, c]]
    else:
        R[:2, :2] = [[c, -s], [s, c]]
    return R


def _seed(R: np.ndarray, target: np.ndarray, source: np.ndarray, *, centroid: bool) -> np.ndarray:
    T = np.eye(4, dtype=np.float64)
    T[:3, :3] = R
    if centroid:
        T[:3, 3] = target.mean(axis=0) - R @ source.mean(axis=0)
    return T


def _step(source: np.ndarray, target: np.ndarray, T: np.ndarray, threshold: float,
          iterations: int, min_count: int) -> np.ndarray:
    transform = T.copy()
    for _ in range(iterations):
        mapped = _apply(source, transform)
        d, idx = _nearest(mapped, target)
        keep = np.flatnonzero(d <= threshold)
        if len(keep) < min_count:
            break
        # Trim worst 20% of tentative matches to resist rim/occlusion artifacts.
        k = max(min_count, int(len(keep) * 0.80))
        keep = keep[np.argsort(d[keep])[:k]]
        delta = _rigid_fit(mapped[keep], target[idx[keep]])
        transform = delta @ transform
        if (np.linalg.norm(delta[:3, 3]) < 0.00005
                and np.linalg.norm(delta[:3, :3] - np.eye(3)) < 0.0003):
            break
    return transform


def _evaluate(target: np.ndarray, source: np.ndarray, T: np.ndarray, threshold: float):
    mapped = _apply(source, T)
    ds, _ = _nearest(mapped, target)
    dt, _ = _nearest(target, mapped)
    good = ds <= threshold
    count = int(np.count_nonzero(good))
    fitness = float(np.mean(good))
    coverage = float(np.mean(dt <= threshold))
    rmse = float(np.sqrt(np.mean(np.square(ds[good])))) if count else None
    return fitness, coverage, min(fitness, coverage), rmse, count


def _condition_ratio(points: np.ndarray) -> float:
    eigs = np.linalg.eigvalsh(np.cov(points.T))
    return float(max(eigs[0], 0.0) / max(eigs[-1], 1e-18))


def _validate_initial(T: np.ndarray) -> np.ndarray:
    t = np.asarray(T, dtype=np.float64)
    if t.shape != (4, 4) or not np.isfinite(t).all() or not np.allclose(t[3], [0, 0, 0, 1]):
        raise RegistrationError("INITIAL_POSE_INVALID", "Initial pose must be finite homogeneous 4x4")
    if not np.allclose(t[:3, :3].T @ t[:3, :3], np.eye(3), atol=1e-5):
        raise RegistrationError("INITIAL_POSE_INVALID", "Initial rotation not orthonormal")
    if not np.isclose(np.linalg.det(t[:3, :3]), 1, atol=1e-5):
        raise RegistrationError("INITIAL_POSE_INVALID", "Initial rotation not proper")
    return t


def register_two_views(target: InputCloud, source: InputCloud,
                       config: RegistrationConfig | None = None,
                       initial_T_world_depth1: np.ndarray | None = None) -> TwoViewResult:
    """Input target depth0, source depth1, return T_world_depth1 (depth1 -> depth0).

    ROI filtering must be performed by the caller; only two static-object views
    with significant geometric overlap are suitable. Pair quality is provisional.
    """
    cfg = config or RegistrationConfig()
    if target.capture_id == source.capture_id:
        raise RegistrationError("DUPLICATE_CAPTURE", "Two different captures required")
    p0 = np.asarray(target.xyz_depth_m, dtype=np.float64)
    p1 = np.asarray(source.xyz_depth_m, dtype=np.float64)
    if min(len(p0), len(p1)) < cfg.min_input_points:
        raise RegistrationError("TOO_FEW_POINTS", "Insufficient measured object points after ROI")

    ratio0, ratio1 = _condition_ratio(p0), _condition_ratio(p1)
    # Bound fallback O(N*M) per nearest-neighbour query when SciPy is absent.
    sample_cap = cfg.max_points_per_scale if cKDTree is not None else min(cfg.max_points_per_scale, 1400)
    coarse0 = _voxel_representatives(p0, cfg.voxel_scales_m[0], sample_cap)
    coarse1 = _voxel_representatives(p1, cfg.voxel_scales_m[0], sample_cap)
    if min(len(coarse0), len(coarse1)) < cfg.min_correspondences:
        raise RegistrationError("TOO_FEW_VOXELS", "Object ROI too small/coarse for registration")

    if initial_T_world_depth1 is not None:
        starts = [_validate_initial(initial_T_world_depth1)]
    else:
        ident = np.eye(3)
        starts = [_seed(ident, coarse0, coarse1, centroid=False),
                  _seed(ident, coarse0, coarse1, centroid=True)]
        # Keep bounded iterations. Narrow-angle seeds, NOT global registration.
        for axis in (0, 1, 2):
            for sign in (-1, 1):
                starts.append(_seed(_rotation(axis, sign * cfg.coarse_seed_deg),
                                    coarse0, coarse1, centroid=True))
        if cKDTree is None:
            starts = starts[:3]

    rank: list[tuple[float, float, np.ndarray]] = []
    for start in starts:
        trial = _step(coarse1, coarse0, start, cfg.correspondences_m[0],
                      min(7, cfg.iterations[0]), cfg.min_correspondences)
        fitness, coverage, overlap, rmse, _ = _evaluate(
            coarse0, coarse1, trial, cfg.correspondences_m[0])
        # Prioritize bidirectional geometric support, not only low residual.
        rank.append((overlap, -(rmse if rmse is not None else 100.0), trial))
    rank.sort(key=lambda x: (x[0], x[1]), reverse=True)
    T = rank[0][2]

    for voxel, cutoff, iteration in zip(cfg.voxel_scales_m,
                                        cfg.correspondences_m, cfg.iterations):
        tgt = _voxel_representatives(p0, voxel, sample_cap)
        src = _voxel_representatives(p1, voxel, sample_cap)
        T = _step(src, tgt, T, cutoff, iteration, cfg.min_correspondences)

    last0 = _voxel_representatives(p0, cfg.voxel_scales_m[-1], sample_cap)
    last1 = _voxel_representatives(p1, cfg.voxel_scales_m[-1], sample_cap)
    f, cov, overlap, rmse, cnt = _evaluate(last0, last1, T, cfg.correspondences_m[-1])
    rotation_deg = degrees(acos(float(np.clip((np.trace(T[:3, :3]) - 1) / 2, -1, 1))))
    translation_m = float(np.linalg.norm(T[:3, 3]))
    reasons = []
    if overlap < cfg.min_overlap: reasons.append("LOW_BIDIRECTIONAL_OVERLAP")
    if rmse is None or rmse > cfg.max_rmse_m: reasons.append("HIGH_REGISTRATION_RMSE")
    if cnt < cfg.min_correspondences: reasons.append("INSUFFICIENT_INLIERS")
    if ratio0 < cfg.min_covariance_ratio or ratio1 < cfg.min_covariance_ratio:
        reasons.append("GEOMETRY_DEGENERATE")
    if translation_m > cfg.max_motion_m or rotation_deg > cfg.max_rotation_deg:
        reasons.append("POSE_STEP_EXCEEDS_PROVISIONAL_LIMIT")
    if (translation_m < cfg.min_distinct_view_translation_m
            and rotation_deg < cfg.min_distinct_view_rotation_deg):
        reasons.append("NO_DISTINCT_VIEW_MOTION")
    accepted = len(reasons) == 0
    quality = PairQuality(fitness_source=f, coverage_target=cov, overlap=overlap,
                          inlier_rmse_m=rmse, inlier_count=cnt,
                          source_points=len(p1), target_points=len(p0),
                          condition_ratio_source=ratio1, condition_ratio_target=ratio0,
                          translation_m=translation_m, rotation_deg=rotation_deg,
                          accepted=accepted, reject_reasons=tuple(reasons))
    T0 = np.eye(4, dtype=np.float64)
    if not accepted:
        return TwoViewResult(quality, T0, None, None, None, BACKEND)
    output0 = _voxel_representatives(p0, cfg.voxel_scales_m[-1],
                                     cfg.max_output_points_per_view)
    output1 = _voxel_representatives(p1, cfg.voxel_scales_m[-1],
                                     cfg.max_output_points_per_view)
    return TwoViewResult(quality, T0, T, output0, _apply(output1, T), BACKEND)
