"""PRE-02 RAW payload contract, independent of hardware, storage and UI.

The two owned byte strings contain JPEG-compressed color and little-endian Y16
values. A future adapter (PRE-04) will copy vendor pybind11-owned bytes here.
"""
from dataclasses import dataclass

from scantopath.domain.raw_rgbd import RawRgbdCaptureMetadataV2


@dataclass(frozen=True, slots=True)
class RawRgbdCapture:
    metadata: RawRgbdCaptureMetadataV2
    color_mjpeg: bytes
    depth_y16_le: bytes

    def __post_init__(self) -> None:
        if not isinstance(self.metadata, RawRgbdCaptureMetadataV2):
            raise TypeError("metadata must be RawRgbdCaptureMetadataV2")
        # Reject mutable bytearray/memoryview so a producer cannot mutate data
        # after contract validation. No direct vendor SDK pointers are stored.
        if type(self.color_mjpeg) is not bytes or type(self.depth_y16_le) is not bytes:
            raise TypeError("RAW payload must be immutable owned Python bytes")
        if len(self.color_mjpeg) != self.metadata.color.payload_size_bytes:
            raise ValueError("MJPEG payload length mismatch")
        if len(self.depth_y16_le) != self.metadata.depth.payload_size_bytes:
            raise ValueError("Y16 payload length mismatch")
        if not self.color_mjpeg.startswith(b"\xff\xd8"):
            raise ValueError("MJPEG must start with a JPEG SOI marker")

    def depth_u16_copy(self):
        """Optional interpretation as an OWNED NumPy array (height, width).

        This helper is for verification only; it performs no deprojection,
        D2C alignment, spatial transform or metric validation.
        """
        import numpy as np

        h, w = self.metadata.depth.height, self.metadata.depth.width
        return np.frombuffer(self.depth_y16_le, dtype="<u2").reshape(h, w).copy()
