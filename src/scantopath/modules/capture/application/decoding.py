"""GD2-09.03: decode verified RAW v2 into RGB and native-grid Y16 arrays.

No Qt, camera, SQLite, D2C alignment, metric deprojection or RAW writes.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol

import numpy as np

from scantopath.acquisition.raw_rgbd import RawRgbdCapture
from scantopath.domain.raw_rgbd import RawRgbdCaptureMetadataV2


class RgbdDecodeError(ValueError):
    """Public, stable error code; never expose raw payloads in UI messages."""

    def __init__(self, code: str, message: str) -> None:
        self.code = code
        super().__init__(message)


class MjpegDecoderPort(Protocol):
    def decode(
        self,
        payload: bytes,
        *,
        width: int,
        height: int,
    ) -> np.ndarray: ...


@dataclass(frozen=True, slots=True)
class DecodedRgbdFrame:
    """Decoded source grids; both arrays are read-only views, not aligned images."""

    color_rgb: np.ndarray
    depth_u16: np.ndarray
    metadata: RawRgbdCaptureMetadataV2

    def __post_init__(self) -> None:
        if not isinstance(self.metadata, RawRgbdCaptureMetadataV2):
            raise TypeError("metadata must be RAW v2 metadata")

        if (
            not isinstance(self.color_rgb, np.ndarray)
            or self.color_rgb.dtype != np.uint8
            or self.color_rgb.shape != (
                self.metadata.color.height,
                self.metadata.color.width,
                3,
            )
            or not self.color_rgb.flags.c_contiguous
        ):
            raise ValueError("color_rgb must be contiguous RGB uint8 HxWx3")

        if (
            not isinstance(self.depth_u16, np.ndarray)
            or self.depth_u16.dtype != np.uint16
            or self.depth_u16.shape != (
                self.metadata.depth.height,
                self.metadata.depth.width,
            )
            or not self.depth_u16.flags.c_contiguous
        ):
            raise ValueError("depth_u16 must be contiguous uint16 HxW")

        self.color_rgb.setflags(write=False)
        self.depth_u16.setflags(write=False)


class RgbdDecoder:
    """Application orchestration; JPEG codec supplied through a port."""

    def __init__(self, mjpeg_decoder: MjpegDecoderPort) -> None:
        self._mjpeg_decoder = mjpeg_decoder

    def decode(self, raw: RawRgbdCapture) -> DecodedRgbdFrame:
        if not isinstance(raw, RawRgbdCapture):
            raise TypeError("raw must be RawRgbdCapture")

        meta = raw.metadata

        try:
            color = self._mjpeg_decoder.decode(
                raw.color_mjpeg,
                width=meta.color.width,
                height=meta.color.height,
            )
        except RgbdDecodeError:
            raise
        except (ValueError, TypeError, OSError) as exc:
            raise RgbdDecodeError(
                "INVALID_MJPEG",
                "Không giải mã được JPEG màu.",
            ) from exc

        if (
            not isinstance(color, np.ndarray)
            or color.dtype != np.uint8
            or color.shape != (
                meta.color.height,
                meta.color.width,
                3,
            )
        ):
            raise RgbdDecodeError(
                "INVALID_RGB_ARRAY",
                "Ảnh màu không đúng định dạng RGB uint8.",
            )

        color = np.ascontiguousarray(color)

        expected_size = meta.depth.width * meta.depth.height * 2

        if len(raw.depth_y16_le) != expected_size:
            raise RgbdDecodeError(
                "INVALID_Y16",
                "Kích thước dữ liệu Y16 không khớp metadata.",
            )

        try:
            # Explicit little-endian; reads directly from immutable Python bytes.
            depth = np.frombuffer(
                raw.depth_y16_le,
                dtype="<u2",
            ).reshape(
                meta.depth.height,
                meta.depth.width,
            )

            if depth.dtype != np.uint16:
                depth = depth.astype(np.uint16, copy=True)

        except (ValueError, TypeError) as exc:
            raise RgbdDecodeError(
                "INVALID_Y16",
                "Dữ liệu độ sâu Y16 không hợp lệ.",
            ) from exc

        return DecodedRgbdFrame(
            color_rgb=color,
            depth_u16=depth,
            metadata=meta,
        )