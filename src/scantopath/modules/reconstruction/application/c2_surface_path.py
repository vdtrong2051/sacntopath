"""C2 FT16-18: bounded surface reconstruction and geometry-only XYZ+normal toolpaths.

Every exported path sample lies on a triangle surviving measured-cloud support
checks. The reconstruction is a provisional geometric reference: no robot
motion, no certified metrology, and no fabricated underside coverage claim.
"""
from __future__ import annotations

from dataclasses import dataclass
from math import ceil, isfinite
from collections import defaultdict
import numpy as np

try:
    from scipy.spatial import cKDTree
except ImportError:
    cKDTree = None


class C2Error(ValueError):
    def __init__(self, code: str, detail: str = ''):
        self.code = code
        super().__init__(code + (': ' + detail if detail else ''))


@dataclass(frozen=True)
class C2Config:
    mesh_spacing_m: float = 0.006
    support_radius_m: float = 0.014
    max_edge_m: float = 0.032
    zigzag_step_m: float = 0.009
    contour_step_m: float = 0.009
    path_sample_m: float = 0.004
    max_source_points: int = 40_000
    max_triangles: int = 200_000
    max_path_points: int = 100_000

    def __post_init__(self):
        lengths = (self.mesh_spacing_m, self.support_radius_m, self.max_edge_m,
                   self.zigzag_step_m, self.contour_step_m, self.path_sample_m)
        if (not all(isfinite(x) and 0.0001 <= x <= .1 for x in lengths)
                or self.support_radius_m < self.mesh_spacing_m
                or self.max_edge_m < self.support_radius_m
                or self.max_source_points < 100 or self.max_source_points > 100_000
                or self.max_triangles < 100 or self.max_triangles > 500_000
                or self.max_path_points < 100 or self.max_path_points > 200_000):
            raise C2Error('C2_CONFIG_INVALID')


class Nearest:
    def __init__(self, points):
        self.points = points
        self.tree = cKDTree(points) if cKDTree is not None else None

    def query(self, query):
        query = np.asarray(query, dtype=np.float64).reshape(-1, 3)
        if self.tree is not None:
            d, ix = self.tree.query(query, k=1, workers=1)
            return np.asarray(d, float), np.asarray(ix, int)
        distances = np.empty(len(query), dtype=float)
        indexes = np.empty(len(query), dtype=int)
        # Stable Euclidean differences (not cancellation-prone squared dot products).
        for offset in range(0, len(query), 64):
            chunk = query[offset:offset+64]
            for j, value in enumerate(chunk):
                sq = np.sum(np.square(self.points-value), axis=1)
                ix = int(np.argmin(sq))
                indexes[offset+j] = ix
                distances[offset+j] = float(np.sqrt(sq[ix]))
        return distances, indexes


def validate_cloud(points, normals, cfg: C2Config):
    xyz = np.asarray(points, dtype=np.float64)
    n = np.asarray(normals, dtype=np.float64)
    if (xyz.ndim != 2 or xyz.shape[1] != 3 or not 100 <= len(xyz) <= cfg.max_source_points
            or n.shape != xyz.shape or not np.isfinite(xyz).all()
            or not np.isfinite(n).all()):
        raise C2Error('C2_C1_POINTS_INVALID')
    lengths = np.linalg.norm(n, axis=1)
    if (np.min(lengths) < 0.8 or np.max(lengths) > 1.2
            or np.min(np.ptp(xyz, axis=0)) < 1e-5 and np.max(np.ptp(xyz, axis=0)) < 1e-4):
        raise C2Error('C2_NORMALS_OR_EXTENT_INVALID')
    return xyz, n / lengths[:, None]


def reconstruct_surface(points, normals, cfg: C2Config | None = None):
    """VTK signed-distance surface -> triangle support gate -> measured partial mesh.

    VTK may interpolate an implicit surface. Only triangles near the source cloud
    are exported; 'underside measured' remains false unless source has explicit
    object-centric flip registration evidence (not supplied by C1 v1).
    """
    cfg = cfg or C2Config()
    xyz, n = validate_cloud(points, normals, cfg)
    try:
        from vtkmodules.vtkCommonDataModel import vtkPolyData
        from vtkmodules.vtkCommonCore import vtkPoints
        from vtkmodules.vtkImagingHybrid import vtkSurfaceReconstructionFilter
        from vtkmodules.vtkFiltersCore import vtkContourFilter, vtkTriangleFilter
        from vtkmodules.util.numpy_support import numpy_to_vtk, vtk_to_numpy
    except ImportError as exc:
        raise C2Error('C2_VTK_NOT_INSTALLED') from exc
    points_vtk = vtkPoints()
    points_vtk.SetData(numpy_to_vtk(xyz, deep=True))
    cloud = vtkPolyData()
    cloud.SetPoints(points_vtk)
    surface = vtkSurfaceReconstructionFilter()
    surface.SetInputData(cloud)
    surface.SetNeighborhoodSize(16)
    surface.SetSampleSpacing(cfg.mesh_spacing_m)
    surface.Update()
    contour = vtkContourFilter()
    contour.SetInputConnection(surface.GetOutputPort())
    contour.SetValue(0, 0.0)
    contour.Update()
    tri_filter = vtkTriangleFilter()
    tri_filter.SetInputConnection(contour.GetOutputPort())
    tri_filter.Update()
    poly = tri_filter.GetOutput()
    if poly.GetNumberOfPoints() < 3 or poly.GetNumberOfPolys() < 1:
        raise C2Error('C2_MESH_EMPTY')
    vertices = vtk_to_numpy(poly.GetPoints().GetData()).astype(np.float64, copy=True)
    packed = vtk_to_numpy(poly.GetPolys().GetData())
    if len(packed) % 4 or np.any(packed[::4] != 3):
        raise C2Error('C2_TRIANGLE_LAYOUT_INVALID')
    faces = packed.reshape(-1, 4)[:, 1:].astype(np.int32, copy=True)
    if len(faces) > cfg.max_triangles:
        raise C2Error('C2_MESH_TRIANGLE_BUDGET')
    if len(vertices) > 100_000 or not np.isfinite(vertices).all():
        raise C2Error('C2_MESH_VERTICES_INVALID')
    triangles = vertices[faces]
    edges = np.stack((np.linalg.norm(triangles[:, 1] - triangles[:, 0], axis=1),
                      np.linalg.norm(triangles[:, 2] - triangles[:, 1], axis=1),
                      np.linalg.norm(triangles[:, 0] - triangles[:, 2], axis=1)), axis=1)
    area = np.linalg.norm(np.cross(triangles[:, 1]-triangles[:, 0],
                                   triangles[:, 2]-triangles[:, 0]), axis=1) * 0.5
    centers = np.mean(triangles, axis=1)
    nearest = Nearest(xyz)
    d_center, _ = nearest.query(centers)
    d_verts, _ = nearest.query(triangles.reshape(-1, 3))
    d_verts = d_verts.reshape(-1, 3)
    # Hard geometric support gate; do not bridge unobserved gaps.
    keep = ((d_center <= cfg.support_radius_m)
            & np.all(d_verts <= cfg.support_radius_m, axis=1)
            & (np.max(edges, axis=1) <= cfg.max_edge_m)
            & (area > 1e-11))
    supported = faces[keep]
    if len(supported) < 12:
        raise C2Error('C2_INSUFFICIENT_SUPPORTED_SURFACE',
                      f'{len(supported)} supported triangles of {len(faces)}')
    used, inverse = np.unique(supported.reshape(-1), return_inverse=True)
    out_verts = vertices[used].astype(np.float64)
    out_faces = inverse.reshape(-1, 3).astype(np.int32)
    report = {
        'schema': 'scantopath.c2.surface_quality.v1',
        'source_points': len(xyz), 'candidate_triangles': len(faces),
        'supported_triangles': len(out_faces),
        'rejected_triangles': int(len(faces)-len(out_faces)),
        'supported_fraction_of_candidates': float(len(out_faces)/len(faces)),
        'mesh_vertices': len(out_verts), 'mesh_faces': len(out_faces),
        'support_radius_m': cfg.support_radius_m,
        'max_edge_m': cfg.max_edge_m,
        'measured_support_policy': 'ALL_VERTICES_AND_CENTROID_NEAR_SOURCE_AND_EDGE_LIMIT',
        'method': 'VTK_SURFACE_RECONSTRUCTION_FILTER+CONTOUR+MEASURED_SUPPORT',
        'closed_surface_proven': False,
        'top_coverage_verified': False,
        'side_coverage_verified': False,
        'underside_coverage_verified': False,
        'underside_state': 'UNKNOWN_NO_REGISTERED_FLIPPED_OBJECT_VIEW',
        'interpolated_unsupported_faces_exported': 0,
        'reference_path_only': True,
    }
    return out_verts, out_faces, report


def _segments_for_level(vertices, faces, axis, level):
    """Intersect a plane with every triangle; return finite edge segments."""
    triangles = vertices[faces]
    span = triangles[:, :, axis]
    candidate = (np.min(span, axis=1) < level-1e-11) & (np.max(span, axis=1) > level+1e-11)
    segments = []
    for face in triangles[candidate]:
        hits = []
        for i, j in ((0, 1), (1, 2), (2, 0)):
            a, b = face[i], face[j]
            da, db = a[axis]-level, b[axis]-level
            if (da < -1e-11 and db > 1e-11) or (db < -1e-11 and da > 1e-11):
                t = -da/(db-da)
                hits.append(a + t*(b-a))
            elif abs(da) <= 1e-11 and abs(db) > 1e-11:
                hits.append(a.copy())
        if len(hits) >= 2 and np.linalg.norm(hits[0]-hits[1]) > 1e-6:
            segments.append((hits[0], hits[1]))
    return segments


def _trace_segments(segments, tolerance=5e-5):
    """Build surface-constrained polylines from triangle/plane intersections."""
    node_id = {}
    coords = []
    edge_nodes = []
    adjacency = defaultdict(list)
    for a,b in segments:
        pair = []
        for xyz in (a,b):
            key = tuple(np.round(np.asarray(xyz)/tolerance).astype(np.int64))
            if key not in node_id:
                node_id[key] = len(coords)
                coords.append(np.asarray(xyz, dtype=float))
            pair.append(node_id[key])
        u,v = pair
        if u==v: continue
        e = len(edge_nodes)
        edge_nodes.append((u,v))
        adjacency[u].append(e)
        adjacency[v].append(e)
    visited=set()
    polylines=[]
    starts=sorted(adjacency, key=lambda x:(len(adjacency[x])==2, x))
    for start in starts:
        for edge in adjacency[start]:
            if edge in visited: continue
            path=[start]
            node=start
            while True:
                choices=[e for e in adjacency[node] if e not in visited]
                if not choices: break
                e=choices[0]
                visited.add(e)
                u,v=edge_nodes[e]
                node=v if node==u else u
                path.append(node)
                if node==start: break
            if len(path)>1:
                pts=np.asarray([coords[n] for n in path])
                if np.sum(np.linalg.norm(np.diff(pts, axis=0),axis=1))>0.002:
                    polylines.append(pts)
    return polylines


def _resample_polyline(polyline, gap):
    if len(polyline)<2: return np.empty((0,3))
    seg_lengths=np.linalg.norm(np.diff(polyline,axis=0),axis=1)
    total=float(np.sum(seg_lengths))
    if total<1e-8: return np.empty((0,3))
    steps=max(1, int(ceil(total/gap)))
    cumulative=np.concatenate(([0.],np.cumsum(seg_lengths)))
    distances=np.linspace(0.,total,steps+1)
    loc=np.searchsorted(cumulative,distances,side='right')-1
    loc=np.clip(loc,0,len(seg_lengths)-1)
    alpha=((distances-cumulative[loc]) / np.maximum(seg_lengths[loc],1e-12))[:,None]
    return polyline[loc]+alpha*(polyline[loc+1]-polyline[loc])


def _boundary_lines(vertices, faces):
    """Observable mesh boundary, useful for flat parts with no height contours."""
    all_edges = np.concatenate((faces[:, [0,1]], faces[:, [1,2]], faces[:, [2,0]]), axis=0)
    canonical = np.sort(all_edges, axis=1)
    _, inverse, counts = np.unique(canonical, axis=0, return_inverse=True, return_counts=True)
    edges = all_edges[counts[inverse] == 1]
    return _trace_segments([(vertices[u], vertices[v]) for u,v in edges])


def generate_paths(vertices, faces, source_xyz, source_normals, *, kind, cfg=None):
    cfg = cfg or C2Config()
    if kind not in ('zigzag','contour'):
        raise C2Error('C2_PATH_KIND_INVALID')
    vertices=np.asarray(vertices,dtype=float)
    faces=np.asarray(faces,dtype=int)
    xyz,normals=validate_cloud(source_xyz, source_normals, cfg)
    if vertices.ndim!=2 or vertices.shape[1]!=3 or faces.ndim!=2 or faces.shape[1]!=3:
        raise C2Error('C2_MESH_INVALID')
    if len(vertices)<3 or len(faces)<1 or np.min(faces)<0 or np.max(faces)>=len(vertices):
        raise C2Error('C2_MESH_INVALID')
    axis=1 if kind=='zigzag' else 2
    spacing=cfg.zigzag_step_m if kind=='zigzag' else cfg.contour_step_m
    low,high=float(np.min(vertices[:,axis])),float(np.max(vertices[:,axis]))
    number=int((high-low)/spacing)
    if number < 1 and kind=='zigzag':
        raise C2Error('C2_INSUFFICIENT_PATH_SPAN')
    if number>160:raise C2Error('C2_TOO_MANY_STRIPS')
    reference=Nearest(xyz)
    lines=[]
    total_points=0
    for index in range(number):
        level=low+(index+0.5)*spacing
        segments=_segments_for_level(vertices, faces,axis,level)
        groups=_trace_segments(segments)
        groups.sort(key=lambda p:float(np.mean(p[:,0])))
        if kind=='zigzag' and index%2:
            groups=list(reversed(groups))
        for polyline in groups:
            if kind=='zigzag' and index%2:
                polyline=polyline[::-1]
            sample=_resample_polyline(polyline,cfg.path_sample_m)
            if len(sample)<2:continue
            distances, ids = reference.query(sample)
            if np.any(distances>cfg.support_radius_m):
                continue  # no floating path segments unsupported by measured geometry
            line_normal=normals[ids]
            if not np.isfinite(line_normal).all():raise C2Error('C2_NONFINITE_PATH_NORMAL')
            total_points+=len(sample)
            if total_points>cfg.max_path_points:raise C2Error('C2_PATH_BUDGET')
            lines.append({'strip_index':index,'level_m':float(level),
                          'points':sample,'normals':line_normal,'source_indices':ids})
    if kind=='contour':
        # Physical mesh boundary is a valid contour on near-flat surfaces;
        # this does not fabricate points outside the supported mesh.
        for boundary_index, polyline in enumerate(_boundary_lines(vertices, faces)):
            sample=_resample_polyline(polyline, cfg.path_sample_m)
            if len(sample)<2:continue
            distances,ids=reference.query(sample)
            if np.any(distances>cfg.support_radius_m):continue
            total_points+=len(sample)
            if total_points>cfg.max_path_points:raise C2Error('C2_PATH_BUDGET')
            lines.append({'strip_index':number+boundary_index, 'level_m':None,
                          'points':sample,'normals':normals[ids],'source_indices':ids})
    if not lines:raise C2Error('C2_NO_SUPPORTED_PATH')
    return lines, {'method':kind.upper()+'_SURFACE_TRIANGLE_SLICING',
                   'slice_axis':'Y' if axis==1 else 'Z',
                   'step_m':spacing,'sample_step_m':cfg.path_sample_m,
                   'segment_count':len(lines),
                   'path_points':int(total_points),
                   'measured_support_radius_m':cfg.support_radius_m,
                   'all_points_on_supported_mesh_triangles':True,
                   'surface_reference_only':True,'robot_executable':False}
