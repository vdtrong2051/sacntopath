"""FT-04: ABI v1 for bounded live XYZ ingress (not RAW/PLY).

128-byte little-endian header, two fixed SHM slots. Control-plane IPC is
newline JSON, and its request/response is the publish and acknowledgement barrier.
"""
from __future__ import annotations

from dataclasses import dataclass
from hashlib import sha256
import struct
import zlib

import numpy as np

MAGIC = b"STPCLD01"
MAJOR, MINOR, HEADER_BYTES = 1, 0, 128
MAX_POINTS = 200_000
MAX_PAYLOAD = MAX_POINTS * 12
SLOT_BYTES = HEADER_BYTES + MAX_PAYLOAD
SLOTS = 2
CLOUD_SHM_BYTES = SLOT_BYTES * SLOTS
FORMAT = "<8sHHHHQQQQQIIII32sII16s"
assert struct.calcsize(FORMAT) == HEADER_BYTES


class CloudProtocolError(ValueError):
    def __init__(self, code: str) -> None:
        self.code = code
        super().__init__(code)


def _u64(value: int, name: str, *, allow_zero: bool = False) -> int:
    if type(value) is not int or not (0 if allow_zero else 1) <= value <= (2**64 - 1):
        raise CloudProtocolError("CLOUD_" + name.upper() + "_INVALID")
    return value


@dataclass(frozen=True, slots=True)
class CloudIdentity:
    live_session_token: int
    camera_generation: int
    cloud_sequence: int
    depth_frame_index: int
    depth_timestamp_us: int
    calibration_fingerprint: str

    def __post_init__(self) -> None:
        for name in ("live_session_token", "camera_generation", "cloud_sequence"):
            _u64(getattr(self, name), name)
        for name in ("depth_frame_index", "depth_timestamp_us"):
            _u64(getattr(self, name), name, allow_zero=True)
        f = self.calibration_fingerprint
        if (type(f) is not str or len(f) != 64 or
                any(c not in "0123456789abcdef" for c in f) or f == "0" * 64):
            raise CloudProtocolError("CLOUD_FINGERPRINT_INVALID")


def _validate_xyz(xyz: np.ndarray) -> np.ndarray:
    if (not isinstance(xyz, np.ndarray) or xyz.dtype != np.dtype("<f4") or
            xyz.ndim != 2 or xyz.shape[1] != 3 or not 1 <= len(xyz) <= MAX_POINTS or
            not xyz.flags.c_contiguous or not np.isfinite(xyz).all() or
            not np.all(xyz[:, 2] > 0)):
        raise CloudProtocolError("CLOUD_XYZ_INVALID")
    return xyz


def encode_cloud(identity: CloudIdentity, xyz: np.ndarray) -> bytes:
    """Create a fully validated 128+B blob. Producer sets magic last in SHM."""
    if not isinstance(identity, CloudIdentity):
        raise CloudProtocolError("CLOUD_IDENTITY_INVALID")
    xyz = _validate_xyz(xyz)
    payload = xyz.tobytes(order="C")
    header = struct.pack(
        FORMAT, MAGIC, MAJOR, MINOR, HEADER_BYTES, 0,
        identity.live_session_token, identity.camera_generation,
        identity.cloud_sequence, identity.depth_frame_index,
        identity.depth_timestamp_us, len(xyz), len(payload), 12, 1,
        bytes.fromhex(identity.calibration_fingerprint),
        zlib.crc32(payload) & 0xFFFFFFFF, 1, bytes(16),
    )
    return header + payload


def decode_cloud(blob: bytes | bytearray | memoryview) -> tuple[CloudIdentity, np.ndarray]:
    """Decode and deep-copy. Never expose a view into producer shared memory."""
    if not isinstance(blob, (bytes, bytearray, memoryview)) or len(blob) < HEADER_BYTES:
        raise CloudProtocolError("CLOUD_HEADER_TRUNCATED")
    fields = struct.unpack_from(FORMAT, blob, 0)
    (magic, major, minor, header_bytes, flags, token, generation,
     sequence, index, timestamp, count, payload_bytes, stride, dtype,
     fingerprint, crc, kind, reserved) = fields
    if magic != MAGIC:
        raise CloudProtocolError("CLOUD_MAGIC_INVALID")
    if (major, minor) != (MAJOR, MINOR):
        raise CloudProtocolError("CLOUD_VERSION_UNSUPPORTED")
    if (header_bytes != HEADER_BYTES or flags != 0 or stride != 12 or
            dtype != 1 or kind != 1 or reserved != bytes(16)):
        raise CloudProtocolError("CLOUD_HEADER_INVALID")
    if not 1 <= count <= MAX_POINTS or payload_bytes != count * 12:
        raise CloudProtocolError("CLOUD_POINT_LIMIT")
    if len(blob) != HEADER_BYTES + payload_bytes:
        raise CloudProtocolError("CLOUD_PAYLOAD_LENGTH_INVALID")
    identity = CloudIdentity(token, generation, sequence, index, timestamp, fingerprint.hex())
    payload = memoryview(blob)[HEADER_BYTES:]
    if zlib.crc32(payload) & 0xFFFFFFFF != crc:
        raise CloudProtocolError("CLOUD_CRC_INVALID")
    xyz = np.frombuffer(payload, dtype="<f4").reshape(count, 3).copy(order="C")
    _validate_xyz(xyz)
    xyz.setflags(write=False)
    return identity, xyz


def read_slot(shm, slot: int) -> tuple[CloudIdentity, np.ndarray]:
    if type(slot) is not int or slot not in (0, 1):
        raise CloudProtocolError("CLOUD_SLOT_INVALID")
    if shm is None or shm.size < CLOUD_SHM_BYTES:
        raise CloudProtocolError("CLOUD_SHM_TOO_SMALL")
    offset = slot * SLOT_BYTES
    # Header copied before any payload length derived from untrusted metadata.
    header = bytes(shm.buf[offset:offset + HEADER_BYTES])
    try:
        (_, _, _, _, _, _, _, _, _, _, count, payload_bytes, _, _, _, _, _, _) = struct.unpack(FORMAT, header)
    except struct.error as exc:
        raise CloudProtocolError("CLOUD_HEADER_INVALID") from exc
    if not 1 <= count <= MAX_POINTS or payload_bytes != count * 12:
        raise CloudProtocolError("CLOUD_POINT_LIMIT")
    blob = header + bytes(shm.buf[offset + HEADER_BYTES:offset + HEADER_BYTES + payload_bytes])
    return decode_cloud(blob)


def publish_slot(shm, slot: int, blob: bytes) -> None:
    """Producer only: caller ensures slot free; request issued AFTER this returns."""
    if type(slot) is not int or slot not in (0, 1):
        raise CloudProtocolError("CLOUD_SLOT_INVALID")
    if shm is None or shm.size < CLOUD_SHM_BYTES:
        raise CloudProtocolError("CLOUD_SHM_TOO_SMALL")
    if not isinstance(blob, bytes) or not HEADER_BYTES < len(blob) <= SLOT_BYTES:
        raise CloudProtocolError("CLOUD_PAYLOAD_LENGTH_INVALID")
    # Double validation before SHM writes; invalid inputs do not occupy slots.
    decode_cloud(blob)
    offset = slot * SLOT_BYTES
    shm.buf[offset:offset + 8] = bytes(8)
    shm.buf[offset + 8:offset + len(blob)] = blob[8:]
    shm.buf[offset:offset + 8] = MAGIC
