"""C1 FT12–15 measured-cloud geometry and provisional registration gates.

No camera, Qt, SQLite, RAW modifications, mesh synthesis or invented points.
SciPy KDTree accelerates neighbourhood operations when installed; for small
clouds, a bounded NumPy fallback is available.
"""
from __future__ import annotations

from dataclasses import dataclass
import numpy as np

try:
    from scipy.spatial import cKDTree
except ImportError:  # SciPy is not a required project dependency
    cKDTree = None


class C1Error(ValueError):
    def __init__(self, code: str, detail: str = ''):
        self.code = code
        super().__init__(code + (': ' + detail if detail else ''))


@dataclass(frozen=True)
class C1Config:
    voxel_m: float = 0.004
    normal_k: int = 16
    sor_k: int = 12
    sor_sigma: float = 2.5
    match_radius_m: float = 0.015
    min_overlap: float = 0.06
    max_rmse_m: float = 0.014
    max_points: int = 200_000
    min_view_points: int = 100

    def __post_init__(self):
        if not (0.001 <= self.voxel_m <= 0.03 and 6 <= self.normal_k <= 64
                and 5 <= self.sor_k <= 48 and 1 <= self.sor_sigma <= 6
                and 0.002 <= self.match_radius_m <= 0.05
                and 0.0 < self.min_overlap <= 1.0
                and 0.001 <= self.max_rmse_m <= 0.05
                and 500 <= self.max_points <= 1_500_000
                and 16 <= self.min_view_points <= 5000):
            raise C1Error('C1_CONFIG_INVALID')


def _points(values, *, cap=1_500_000):
    points = np.asarray(values, dtype=np.float64)
    if (points.ndim != 2 or points.shape[1] != 3 or not 1 <= len(points) <= cap
            or not np.isfinite(points).all()):
        raise C1Error('C1_XYZ_INVALID')
    return points


def neighbours(reference, query, k):
    """Bounded kNN; never allocate an unbounded NxN distance matrix."""
    reference = _points(reference)
    query = _points(query)
    if k < 1 or k > len(reference):
        raise C1Error('C1_KNN_INVALID')
    if cKDTree is not None:
        d, ix = cKDTree(reference).query(query, k=k, workers=1)
        return np.asarray(d).reshape(len(query), k), np.asarray(ix).reshape(len(query), k)
    if len(reference) > 20_000 or len(query) > 20_000:
        raise C1Error('C1_SCIPY_REQUIRED_FOR_LARGE_CLOUD', 'pip install scipy')
    distances = np.empty((len(query), k), dtype=np.float64)
    indices = np.empty((len(query), k), dtype=np.intp)
    for begin in range(0, len(query), 64):
        a = query[begin:begin+64]
        sq = np.maximum(0, np.sum(a*a, axis=1)[:, None]
                        + np.sum(reference*reference, axis=1)[None, :]
                        - 2 * a @ reference.T)
        pick = np.argpartition(sq, k-1, axis=1)[:, :k]
        values = np.take_along_axis(sq, pick, axis=1)
        order = np.argsort(values, axis=1)
        pick = np.take_along_axis(pick, order, axis=1)
        distances[begin:begin+len(a)] = np.linalg.norm(
            a[:, None, :] - reference[pick], axis=2
        )
        indices[begin:begin+len(a)] = pick
    return distances, indices


def measured_voxel(points, origin_indices, cfg: C1Config):
    """First measured point in each cell: no synthetic centroids."""
    points = _points(points)
    origins = np.asarray(origin_indices, dtype=np.int32)
    if origins.shape != (len(points),):
        raise C1Error('C1_ORIGIN_INVALID')
    key = np.floor(points / cfg.voxel_m).astype(np.int64)
    _, keep = np.unique(key, axis=0, return_index=True)
    keep.sort()
    if len(keep) > cfg.max_points:
        raise C1Error('C1_POINT_BUDGET_EXCEEDED', str(len(keep)))
    return points[keep], origins[keep]


def filter_outliers(points, origins, cfg: C1Config):
    points = _points(points)
    origins = np.asarray(origins, dtype=np.int32)
    if origins.shape != (len(points),):
        raise C1Error('C1_ORIGIN_INVALID')
    if len(points) < cfg.sor_k + 2:
        raise C1Error('C1_TOO_FEW_POINTS_FOR_SOR')
    d, _ = neighbours(points, points, cfg.sor_k+1)
    mean_dist = np.mean(d[:, 1:], axis=1)
    cutoff = float(mean_dist.mean() + cfg.sor_sigma * mean_dist.std())
    mask = mean_dist <= cutoff
    if np.count_nonzero(mask) < max(cfg.normal_k+2, 50):
        raise C1Error('C1_SOR_REMOVED_TOO_MUCH')
    return points[mask], origins[mask], {
        'input_points': int(len(points)), 'retained_points': int(mask.sum()),
        'removed_outliers': int(len(points)-mask.sum()),
        'mean_neighbor_distance_m': float(mean_dist.mean()),
        'sor_cutoff_m': cutoff, 'sor_k': cfg.sor_k, 'sor_sigma': cfg.sor_sigma,
        'isolation_source': 'FT05.8_CHARUCO_OBJECT_MASK',
        'background_removed_by_c1_sor': 'outliers_only_not_semantic_segmentation',
    }


def estimate_normals(points, origins, camera_origins: dict[int, np.ndarray], cfg: C1Config):
    points = _points(points)
    origins = np.asarray(origins, dtype=np.int32)
    if len(points) < cfg.normal_k + 2 or origins.shape != (len(points),):
        raise C1Error('C1_NORMALS_INSUFFICIENT_POINTS')
    d, idx = neighbours(points, points, cfg.normal_k + 1)
    normals = np.empty_like(points)
    curvature = np.empty(len(points), dtype=np.float64)
    for begin in range(0, len(points), 1024):
        end = min(begin + 1024, len(points))
        group = points[idx[begin:end, 1:]]
        centered = group - group.mean(axis=1, keepdims=True)
        covariance = np.einsum('nki,nkj->nij', centered, centered) / cfg.normal_k
        values, vectors = np.linalg.eigh(covariance)
        normals[begin:end] = vectors[:, :, 0]
        curvature[begin:end] = np.maximum(values[:,0], 0) / np.maximum(values.sum(axis=1), 1.e-15)
    # Orientation is toward the camera that measured the representative point.
    # This is a view-consistency convention, not proof of globally outward normals.
    for src in np.unique(origins):
        src = int(src)
        if src not in camera_origins:
            raise C1Error('C1_CAMERA_ORIGIN_MISSING', str(src))
        choose = origins == src
        direction = np.asarray(camera_origins[src], dtype=np.float64)[None, :] - points[choose]
        flip = np.sum(normals[choose] * direction, axis=1) < 0
        n = normals[choose]
        n[flip] *= -1
        normals[choose] = n
    finite = bool(np.isfinite(normals).all())
    lengths = np.linalg.norm(normals, axis=1)
    if not finite or not np.allclose(lengths, 1, atol=1e-5):
        raise C1Error('C1_NORMALS_INVALID')
    return normals, {
        'count': int(len(normals)), 'finite_fraction': 1.0,
        'orientation_policy': 'TOWARD_SOURCE_CAMERA_ESTIMATED_POSE',
        'globally_outward_verified': False,
        'curvature_median': float(np.median(curvature)),
        'curvature_p95': float(np.percentile(curvature, 95)),
        'neighbor_distance_p95_m': float(np.percentile(d[:, -1], 95)),
        'normal_k': cfg.normal_k,
    }


def registration_check(reference, candidate, cfg: C1Config):
    """Symmetric NN consistency on FT-09-mapped view, not a new pose solver."""
    ref = _points(reference)
    src = _points(candidate)
    if min(len(ref), len(src)) < cfg.min_view_points:
        return {'state':'REJECTED', 'reason':'TOO_FEW_POINTS', 'overlap':0.0, 'rmse_m':None}
    # Deterministic bounded quality sample; fusion retains full original measurements.
    if len(ref) > 8_000:
        ref = ref[np.linspace(0, len(ref)-1, 8_000, dtype=np.int64)]
    if len(src) > 8_000:
        src = src[np.linspace(0, len(src)-1, 8_000, dtype=np.int64)]
    d_src, _ = neighbours(ref, src, 1)
    d_ref, _ = neighbours(src, ref, 1)
    a = d_src[:,0] <= cfg.match_radius_m
    b = d_ref[:,0] <= cfg.match_radius_m
    overlap = float(min(np.mean(a), np.mean(b)))
    rmse = float(np.sqrt(np.mean(np.square(d_src[a,0])))) if np.any(a) else None
    problems = []
    if overlap < cfg.min_overlap: problems.append('LOW_GEOMETRIC_OVERLAP')
    if rmse is None or rmse > cfg.max_rmse_m: problems.append('HIGH_NEAREST_NEIGHBOR_RESIDUAL')
    return {'state':'REJECTED' if problems else 'ACCEPTED_PROVISIONAL',
            'reason':','.join(problems) if problems else None,
            'overlap':overlap,'rmse_m':rmse,
            'sample_points_source':len(src),'sample_points_reference':len(ref),
            'thresholds':{'min_overlap':cfg.min_overlap, 'max_rmse_m':cfg.max_rmse_m,
                          'match_radius_m':cfg.match_radius_m},
            'pose_adjusted_by_c1':False, 'metric_accuracy_verified':False}


def validate_metric(points, reference: dict | None):
    points = _points(points)
    extent_mm = np.ptp(points, axis=0)*1000.0
    report = {'schema':'scantopath.c1.metric.v1',
              'method':'AXIS_ALIGNED_CLOUD_EXTENT_PROVISIONAL',
              'measured_extents_mm':dict(zip('xyz', [float(v) for v in extent_mm])),
              'metric_accuracy_verified':False,
              'limit_mm':10.0, 'gate':'NOT_TESTED', 'axes':{}}
    if reference is None: return report
    if not isinstance(reference, dict) or set(reference.get('axes_mm', {})) != {'x','y','z'}:
        raise C1Error('C1_REFERENCE_SCHEMA_INVALID')
    method = reference.get('measurement_method')
    instrument = reference.get('reference_instrument')
    aligned = reference.get('axis_alignment_confirmed') is True
    if not (isinstance(method,str) and method.strip() and isinstance(instrument,str)
            and instrument.strip() and aligned):
        raise C1Error('C1_REFERENCE_EVIDENCE_INCOMPLETE', 'axis alignment + measurement method required')
    report['reference_method'] = method
    report['reference_instrument'] = instrument
    report['operator_axis_alignment_confirmed'] = True
    for i,ax in enumerate('xyz'):
        raw = reference['axes_mm'][ax]
        if isinstance(raw,bool) or not isinstance(raw,(float,int)) or not (0 < raw < 100_000):
            raise C1Error('C1_REFERENCE_INVALID',ax)
        diff = abs(float(extent_mm[i])-float(raw))
        report['axes'][ax]={'reference_mm':float(raw), 'cloud_extent_mm':float(extent_mm[i]),
                            'abs_error_mm':float(diff),'relative_error_percent':float(diff/raw*100),
                            'pass_10mm':bool(diff <= 10.0)}
    report['gate']='DEMO_GATE_PASS_PROVISIONAL' if all(x['pass_10mm'] for x in report['axes'].values()) else 'DEMO_GATE_FAIL'
    report['metric_accuracy_verified']=False  # No independently calibrated C1 metrology.
    return report
