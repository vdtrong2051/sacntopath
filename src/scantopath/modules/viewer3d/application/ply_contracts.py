"""08.03 typed, untrusted-result PLY contract; Qt/VTK/SQLite independent.

A PLY preview is never evidence of metric accuracy or a calibrated frame.
"""
from __future__ import annotations
from dataclasses import dataclass
import math
from pathlib import Path


@dataclass(frozen=True, slots=True)
class PlySummary:
    name: str
    source_sha256: str
    source_bytes: int
    point_count: int
    bounds: tuple[float, float, float, float, float, float]
    has_rgb: bool
    ply_format: str
    units: str = 'unknown'
    coordinate_frame: str = 'unknown'

    @classmethod
    def from_result(cls, record: dict) -> 'PlySummary':
        if not isinstance(record, dict):
            raise ValueError('PLY result must be a JSON object')
        name = record.get('name')
        if not isinstance(name, str) or not name or len(name) > 256 or name != Path(name).name:
            raise ValueError('Invalid PLY name')
        count = record.get('point_count')
        if isinstance(count, bool) or not isinstance(count, int) or not (1 <= count <= 1_500_000):
            raise ValueError('Invalid point count')
        size = record.get('source_bytes')
        if isinstance(size, bool) or not isinstance(size, int) or not (1 <= size <= 256 * 1024 * 1024):
            raise ValueError('Invalid PLY file size')
        sha = record.get('source_sha256')
        if not isinstance(sha, str) or len(sha) != 64 or any(c not in '0123456789abcdef' for c in sha):
            raise ValueError('Invalid source SHA-256')
        raw_bounds = record.get('bounds')
        if (not isinstance(raw_bounds, list) or len(raw_bounds) != 6
                or any(isinstance(v, bool) or not isinstance(v, (int, float)) or not math.isfinite(v)
                       for v in raw_bounds)):
            raise ValueError('Invalid bounds')
        bounds = tuple(float(v) for v in raw_bounds)
        if any(bounds[i] > bounds[i + 1] for i in (0, 2, 4)):
            raise ValueError('Reversed bounds')
        rgb = record.get('has_rgb')
        if not isinstance(rgb, bool):
            raise ValueError('Invalid RGB flag')
        fmt = record.get('ply_format')
        if fmt not in ('ascii', 'binary_little_endian', 'binary_big_endian'):
            raise ValueError('Unsupported PLY format')
        if record.get('units') != 'unknown' or record.get('coordinate_frame') != 'unknown':
            raise ValueError('08.03 PLY file cannot claim validated units or frame')
        return cls(name, sha, size, count, bounds, rgb, fmt)
