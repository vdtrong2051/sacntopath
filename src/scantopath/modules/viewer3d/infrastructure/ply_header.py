"""Bounded header preflight for file-based PLY, no Qt/VTK imports.

The complete geometry is still parsed in the isolated VTK process. The header
is only an early failure/limit check, not a trustworthy metric provenance source.
"""
from __future__ import annotations
from dataclasses import dataclass
from pathlib import Path
import hashlib
import os

MAX_PLY_BYTES = 256 * 1024 * 1024
MAX_HEADER_BYTES = 256 * 1024
MAX_POINTS = 1_500_000
SCALAR_TYPES = frozenset(('char', 'uchar', 'short', 'ushort', 'int', 'uint', 'float', 'double',
                          'int8', 'uint8', 'int16', 'uint16', 'int32', 'uint32', 'float32', 'float64'))
FORMATS = frozenset(('ascii', 'binary_little_endian', 'binary_big_endian'))


@dataclass(frozen=True, slots=True)
class PlyHeader:
    vertex_count: int
    ply_format: str
    has_rgb: bool
    source_bytes: int
    source_sha256: str
    source_mtime_ns: int


def inspect_ply(path: Path) -> PlyHeader:
    if not path.is_file() or path.suffix.lower() != '.ply':
        raise ValueError('Chỉ chấp nhận tệp .ply có thật')
    if path.is_symlink():
        raise ValueError('Không đọc PLY qua symbolic link')
    before = path.stat()
    if not 1 <= before.st_size <= MAX_PLY_BYTES:
        raise ValueError('Dung lượng PLY không được vượt 256 MiB')
    if not os.path.isfile(path):
        raise ValueError('Không phải tệp thông thường')
    with path.open('rb') as stream:
        head = stream.read(MAX_HEADER_BYTES + 1)
    # Header always ends with LF (possibly CRLF); avoid decoding binary body.
    marker = b'end_header\n'
    marker_crlf = b'end_header\r\n'
    pos = head.find(marker)
    end = pos + len(marker)
    pos_crlf = head.find(marker_crlf)
    if pos_crlf >= 0 and (pos < 0 or pos_crlf < pos):
        end = pos_crlf + len(marker_crlf)
    if (pos < 0 and pos_crlf < 0) or end > MAX_HEADER_BYTES:
        raise ValueError('Thiếu end_header hoặc header quá lớn')
    try:
        lines = head[:end].decode('ascii').splitlines()
    except UnicodeDecodeError as exc:
        raise ValueError('Header PLY phải dùng ASCII') from exc
    if not lines or lines[0].strip() != 'ply':
        raise ValueError('Không phải PLY')
    fmt = None
    vertex = None
    current = None
    props: set[str] = set()
    for line in lines[1:]:
        tokens = line.strip().split()
        if not tokens or tokens[0] in ('comment', 'obj_info', 'end_header'):
            continue
        if tokens[0] == 'format':
            if fmt is not None or len(tokens) != 3 or tokens[2] != '1.0' or tokens[1] not in FORMATS:
                raise ValueError('Chỉ hỗ trợ định dạng PLY 1.0')
            fmt = tokens[1]
        elif tokens[0] == 'element':
            if len(tokens) != 3 or not tokens[2].isdigit():
                raise ValueError('Invalid element count')
            current = tokens[1]
            if current == 'vertex':
                if vertex is not None:
                    raise ValueError('Repeated vertex element')
                vertex = int(tokens[2])
        elif tokens[0] == 'property':
            if current == 'vertex':
                if len(tokens) != 3 or tokens[1] not in SCALAR_TYPES or tokens[2] in props:
                    raise ValueError('Unsupported or duplicate vertex property')
                props.add(tokens[2])
        else:
            raise ValueError('Malformed PLY header')
    if fmt is None or vertex is None or not 1 <= vertex <= MAX_POINTS:
        raise ValueError('PLY cần 1 đến 1.500.000 đỉnh XYZ')
    if not {'x', 'y', 'z'}.issubset(props):
        raise ValueError('Thiếu tọa độ XYZ')
    digest = hashlib.sha256()
    with path.open('rb') as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b''):
            digest.update(chunk)
    after = path.stat()
    if before.st_size != after.st_size or before.st_mtime_ns != after.st_mtime_ns:
        raise ValueError('Tệp PLY bị thay đổi trong khi đọc')
    return PlyHeader(vertex, fmt, {'red', 'green', 'blue'}.issubset(props),
                     after.st_size, digest.hexdigest(), after.st_mtime_ns)
