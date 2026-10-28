"""R5.1 read-only VTK scene source loader; native execution in render host only.

Never manufacture mesh faces from a vertex-only cloud; do not load OBJ materials.
"""
from __future__ import annotations

from dataclasses import dataclass
import hashlib
import math
from pathlib import Path
import re

from ..application.scene_contracts import (
    MAX_SOURCE_BYTES, MAX_VERTICES, MAX_FACES, SceneDescriptor, SceneSource,
)
from .ply_header import inspect_ply

MAX_OBJ_LINE_BYTES = 16_384
_SUPPORTED_OBJ = frozenset({'v', 'vt', 'vn', 'f', 'o', 'g', 's'})
_FACE_TOKEN = re.compile(r'^([1-9][0-9]*)(?:/([1-9][0-9]*)?(?:/([1-9][0-9]*))?)?$')


@dataclass(slots=True)
class LoadedScene:
    descriptor: SceneDescriptor
    reader: object
    glyph: object | None
    mapper: object
    poly_data: object
    actor: object


def _digest_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open('rb') as fh:
        for block in iter(lambda: fh.read(1024 * 1024), b''):
            h.update(block)
    return h.hexdigest()


def _basic_stat(source: Path):
    if not source.is_absolute() or source.is_symlink() or source.suffix.lower() not in ('.ply', '.obj'):
        raise ValueError('SOURCE_PATH_REJECTED')
    if not source.is_file():
        raise ValueError('SOURCE_NOT_FOUND')
    info = source.stat()
    if not 1 <= info.st_size <= MAX_SOURCE_BYTES:
        raise ValueError('SOURCE_SIZE_LIMIT')
    return info


def _preflight_obj(path: Path) -> tuple[int, int, str]:
    """Bounded OBJ geometry subset: vertices and polygon faces, no external resources.

    Relative/negative OBJ indices and material/texture paths are intentionally
    rejected until they have their own vetted contract; do not silently repair.
    """
    vertices = faces = texcoords = normals = 0
    with path.open('rb') as stream:
        while True:
            raw = stream.readline(MAX_OBJ_LINE_BYTES + 1)
            if not raw:
                break
            if len(raw) > MAX_OBJ_LINE_BYTES:
                raise ValueError('OBJ_LINE_TOO_LONG')
            try:
                line = raw.decode('utf-8', 'strict').strip()
            except UnicodeDecodeError as exc:
                raise ValueError('OBJ_INVALID_UTF8') from exc
            if not line or line.startswith('#'):
                continue
            fields = line.split()
            op = fields[0]
            if op not in _SUPPORTED_OBJ:
                raise ValueError('OBJ_UNSUPPORTED_DIRECTIVE')
            if op == 'v':
                if len(fields) != 4:
                    raise ValueError('OBJ_VERTEX_XYZ_REQUIRED')
                try:
                    coords = [float(t) for t in fields[1:]]
                except ValueError as exc:
                    raise ValueError('OBJ_INVALID_COORDINATE') from exc
                if not all(math.isfinite(x) for x in coords):
                    raise ValueError('OBJ_NONFINITE_COORDINATE')
                vertices += 1
                if vertices > MAX_VERTICES:
                    raise ValueError('OBJ_VERTEX_LIMIT')
            elif op == 'f':
                if len(fields) < 4:
                    raise ValueError('OBJ_FACE_TOO_SMALL')
                ids = []
                for token in fields[1:]:
                    match = _FACE_TOKEN.fullmatch(token)
                    if match is None:
                        raise ValueError('OBJ_UNSUPPORTED_FACE_INDEX')
                    idx = int(match.group(1))
                    if idx > vertices:
                        raise ValueError('OBJ_FORWARD_VERTEX_REFERENCE')
                    if '/' in token:
                        # Full, positive-only OBJ vt/vn references are validated
                        # against the number of elements defined so far.
                        if match.group(2) is None and match.group(3) is None:
                            raise ValueError('OBJ_UNSUPPORTED_FACE_INDEX')
                        if match.group(2) is not None and int(match.group(2)) > texcoords:
                            raise ValueError('OBJ_INVALID_TEXTURE_INDEX')
                        if match.group(3) is not None and int(match.group(3)) > normals:
                            raise ValueError('OBJ_INVALID_NORMAL_INDEX')
                    ids.append(idx)
                if len(set(ids)) < 3:
                    raise ValueError('OBJ_DEGENERATE_FACE')
                faces += 1
                if faces > MAX_FACES:
                    raise ValueError('OBJ_FACE_LIMIT')
            elif op in ('vt', 'vn'):
                # Texture coordinate/normal indices are not interpreted by this
                # subset; explicitly reject their references in face tokens below.
                if not 2 <= len(fields) <= 4:
                    raise ValueError('OBJ_INVALID_AUXILIARY_DATA')
                try:
                    values = [float(t) for t in fields[1:]]
                except ValueError as exc:
                    raise ValueError('OBJ_INVALID_AUXILIARY_DATA') from exc
                if not all(math.isfinite(x) for x in values):
                    raise ValueError('OBJ_NONFINITE_AUXILIARY_DATA')
                if op == 'vt':
                    texcoords += 1
                else:
                    normals += 1
                if max(texcoords, normals) > MAX_VERTICES:
                    raise ValueError('OBJ_AUXILIARY_LIMIT')
            elif op == 's' and len(fields) != 2:
                raise ValueError('OBJ_INVALID_SMOOTHING')
    if not vertices or not faces:
        raise ValueError('OBJ_REQUIRES_POLYGON_MESH')
    # External material/texture file references remain explicitly unsupported.
    return vertices, faces, _digest_file(path)


def load_scene(source: SceneSource) -> LoadedScene:
    path = Path(source.path)
    before = _basic_stat(path)
    preflight_faces = 0
    if path.suffix.lower() == '.ply':
        header = inspect_ply(path)
        expected_count = header.vertex_count
        pre_sha = header.source_sha256
        from vtkmodules.vtkIOPLY import vtkPLYReader
        reader = vtkPLYReader()
    else:
        expected_count, preflight_faces, pre_sha = _preflight_obj(path)
        from vtkmodules.vtkIOGeometry import vtkOBJReader
        reader = vtkOBJReader()
    if source.expected_sha256 is not None and source.expected_sha256 != pre_sha:
        raise ValueError('SOURCE_FINGERPRINT_MISMATCH')
    errors: list[str] = []
    reader.AddObserver('ErrorEvent', lambda *_: errors.append('VTK_READER_ERROR'))
    reader.SetFileName(str(path))
    reader.Update()
    poly = reader.GetOutput()
    if errors or poly is None or poly.GetNumberOfPoints() != expected_count:
        raise ValueError('VTK_SCENE_READ_FAILED')
    n_points = poly.GetNumberOfPoints()
    n_faces = poly.GetNumberOfPolys()
    if n_faces > MAX_FACES or poly.GetNumberOfLines() or poly.GetNumberOfStrips():
        raise ValueError('UNSUPPORTED_SCENE_PRIMITIVES')
    if path.suffix.lower() == '.obj' and not n_faces:
        raise ValueError('OBJ_FACES_MISSING')
    if path.suffix.lower() == '.obj' and n_faces != preflight_faces:
        raise ValueError('OBJ_FACE_COUNT_MISMATCH')
    for i in range(n_points):
        if not all(math.isfinite(v) for v in poly.GetPoint(i)):
            raise ValueError('NONFINITE_SCENE_POINT')
    for i in range(poly.GetNumberOfCells()):
        cell = poly.GetCell(i)
        if cell is None:
            raise ValueError('INVALID_SCENE_CELL')
        if cell.GetCellDimension() == 2:
            if cell.GetNumberOfPoints() < 3:
                raise ValueError('INVALID_POLYGON')
            if any(not 0 <= cell.GetPointId(j) < n_points for j in range(cell.GetNumberOfPoints())):
                raise ValueError('INVALID_POLYGON_INDEX')
    bounds = tuple(float(x) for x in poly.GetBounds())
    if len(bounds) != 6 or not all(math.isfinite(x) for x in bounds):
        raise ValueError('INVALID_SCENE_BOUNDS')
    from vtkmodules.vtkRenderingCore import vtkActor, vtkPolyDataMapper
    glyph = None
    mapper = vtkPolyDataMapper()
    if n_faces == 0:
        from vtkmodules.vtkFiltersGeneral import vtkVertexGlyphFilter
        glyph = vtkVertexGlyphFilter()
        glyph.SetInputData(poly)
        glyph.Update()
        mapper.SetInputConnection(glyph.GetOutputPort())
    else:
        mapper.SetInputData(poly)
    colors = poly.GetPointData().GetScalars() if poly.GetPointData() else None
    has_rgb = bool(path.suffix.lower() == '.ply' and header.has_rgb and
                   colors is not None and colors.GetNumberOfComponents() >= 3)
    if has_rgb:
        mapper.SetScalarVisibility(True)
        mapper.SetColorModeToDirectScalars()
    else:
        mapper.ScalarVisibilityOff()
    actor = vtkActor()
    actor.SetMapper(mapper)
    if n_faces == 0:
        actor.GetProperty().SetPointSize(4 if n_points > 100_000 else 6)
    if not has_rgb:
        actor.GetProperty().SetColor(.12, .52, .87)
    after = path.stat()
    if (after.st_size != before.st_size or after.st_mtime_ns != before.st_mtime_ns or
            _digest_file(path) != pre_sha):
        raise ValueError('SOURCE_CHANGED_DURING_LOAD')
    desc = SceneDescriptor.from_result({
        'name': path.name, 'source_sha256': pre_sha, 'source_bytes': after.st_size,
        'source_format': path.suffix.lower()[1:],
        'geometry_kind': 'mesh' if n_faces else 'points',
        'point_count': n_points, 'face_count': n_faces, 'bounds': list(bounds),
        'has_rgb': has_rgb, 'units': 'unknown', 'coordinate_frame': 'unknown',
    })
    return LoadedScene(desc, reader, glyph, mapper, poly, actor)
