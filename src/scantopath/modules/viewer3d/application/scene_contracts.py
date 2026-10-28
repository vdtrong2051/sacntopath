"""R5.1: renderer-neutral, immutable scene and future picking contracts.

External PLY/OBJ files do not establish units, calibration or a world frame.
"""
from __future__ import annotations

from dataclasses import dataclass
import math

MAX_SOURCE_BYTES = 256 * 1024 * 1024
MAX_VERTICES = 1_500_000
MAX_FACES = 3_000_000


def _sha(value: str) -> bool:
    return type(value) is str and len(value) == 64 and all(c in '0123456789abcdef' for c in value)


@dataclass(frozen=True, slots=True)
class SceneSource:
    path: str
    expected_sha256: str | None = None

    def __post_init__(self):
        if type(self.path) is not str or not 1 <= len(self.path) <= 1024 or '\x00' in self.path:
            raise ValueError('INVALID_SOURCE_PATH')
        if self.expected_sha256 is not None and not _sha(self.expected_sha256):
            raise ValueError('INVALID_SOURCE_SHA256')


@dataclass(frozen=True, slots=True)
class SceneDescriptor:
    name: str
    source_sha256: str
    source_bytes: int
    source_format: str
    geometry_kind: str
    point_count: int
    face_count: int
    bounds: tuple[float, float, float, float, float, float]
    has_rgb: bool
    units: str = 'unknown'
    coordinate_frame: str = 'unknown'

    @classmethod
    def from_result(cls, record: dict) -> 'SceneDescriptor':
        if type(record) is not dict:
            raise ValueError('INVALID_SCENE_RESULT')
        name = record.get('name')
        if (type(name) is not str or not name or len(name) > 256 or
                '/' in name or '\\' in name or name in ('.', '..')):
            raise ValueError('INVALID_SCENE_NAME')
        fmt = record.get('source_format')
        if fmt not in ('ply', 'obj'):
            raise ValueError('INVALID_SOURCE_FORMAT')
        if name.lower().rsplit('.', 1)[-1] != fmt:
            raise ValueError('SOURCE_EXTENSION_MISMATCH')
        kind = record.get('geometry_kind')
        points, faces, size = (record.get(k) for k in ('point_count', 'face_count', 'source_bytes'))
        if (type(points) is not int or not 1 <= points <= MAX_VERTICES or
                type(faces) is not int or not 0 <= faces <= MAX_FACES or
                type(size) is not int or not 1 <= size <= MAX_SOURCE_BYTES or
                kind != ('mesh' if faces else 'points') or
                (fmt == 'obj' and faces == 0)):
            raise ValueError('INVALID_SCENE_GEOMETRY')
        bounds = record.get('bounds')
        if (not isinstance(bounds, (list, tuple)) or len(bounds) != 6 or
                any(type(x) not in (float, int) or not math.isfinite(x) for x in bounds) or
                any(bounds[i] > bounds[i+1] for i in (0, 2, 4))):
            raise ValueError('INVALID_SCENE_BOUNDS')
        if type(record.get('has_rgb')) is not bool:
            raise ValueError('INVALID_RGB_STATUS')
        if record.get('units') != 'unknown' or record.get('coordinate_frame') != 'unknown':
            raise ValueError('UNVERIFIED_METRIC_PROVENANCE')
        if not _sha(record.get('source_sha256')):
            raise ValueError('INVALID_SOURCE_SHA256')
        return cls(name, record['source_sha256'], size, fmt, kind, points, faces,
                   tuple(float(x) for x in bounds), record['has_rgb'])


@dataclass(frozen=True, slots=True)
class SceneSelectionRef:
    """Typed point/face identity for R5.3; not a ray-picking implementation."""
    source_sha256: str
    scene_revision: int
    kind: str
    element_id: int
    xyz: tuple[float, float, float]
    units: str = 'unknown'
    coordinate_frame: str = 'unknown'

    def __post_init__(self):
        if (not _sha(self.source_sha256) or type(self.scene_revision) is not int or
                self.scene_revision < 1 or self.kind not in ('point', 'face') or
                type(self.element_id) is not int or self.element_id < 0):
            raise ValueError('INVALID_SCENE_SELECTION')
        if (not isinstance(self.xyz, (tuple, list)) or len(self.xyz) != 3 or
                any(type(v) not in (float, int) or not math.isfinite(v) for v in self.xyz)):
            raise ValueError('INVALID_SELECTION_XYZ')
        if self.units != 'unknown' or self.coordinate_frame != 'unknown':
            raise ValueError('UNVERIFIED_METRIC_PROVENANCE')
