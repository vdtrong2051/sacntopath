"""GD2-09.03: Pillow-backed MJPEG frame decoder, imported lazily on decode."""
from __future__ import annotations

from io import BytesIO

import numpy as np

from scantopath.modules.capture.application.decoding import RgbdDecodeError


class PillowMjpegDecoder:
    MAX_PIXELS = 32_000_000
    MAX_JPEG_BYTES = 64 * 1024 * 1024

    def decode(
        self,
        payload: bytes,
        *,
        width: int,
        height: int,
    ) -> np.ndarray:

        if type(payload) is not bytes or len(payload) == 0:
            raise RgbdDecodeError(
                "INVALID_MJPEG",
                "JPEG đầu vào phải là bytes hợp lệ.",
            )

        if (
            type(width) is not int
            or type(height) is not int
            or width <= 0
            or height <= 0
            or width * height > self.MAX_PIXELS
            or len(payload) > self.MAX_JPEG_BYTES
        ):
            raise RgbdDecodeError(
                "JPEG_LIMIT_EXCEEDED",
                "JPEG vượt giới hạn đầu vào hỗ trợ.",
            )

        try:
            from PIL import Image
        except ImportError as exc:
            raise RgbdDecodeError(
                "JPEG_DECODER_MISSING",
                "Chưa cài Pillow cho tính năng Capture.",
            ) from exc

        try:
            with Image.open(BytesIO(payload)) as image:
                if image.format != "JPEG":
                    raise RgbdDecodeError(
                        "UNSUPPORTED_COLOR_ENCODING",
                        "Luồng màu không phải JPEG.",
                    )

                if image.size != (width, height):
                    raise RgbdDecodeError(
                        "JPEG_DIMENSION_MISMATCH",
                        "Độ phân giải JPEG không khớp metadata.",
                    )

                if image.mode not in ("RGB", "YCbCr"):
                    raise RgbdDecodeError(
                        "UNSUPPORTED_JPEG_MODE",
                        "JPEG không chứa ảnh màu RGB được hỗ trợ.",
                    )

                # Decode now; detect malformed/truncated JPEG.
                image.load()

                rgb = image.convert("RGB")

                return np.ascontiguousarray(
                    np.asarray(rgb, dtype=np.uint8)
                )

        except RgbdDecodeError:
            raise
        except (
            OSError,
            ValueError,
            SyntaxError,
            Image.DecompressionBombError,
        ) as exc:
            raise RgbdDecodeError(
                "INVALID_MJPEG",
                "JPEG màu bị lỗi hoặc không thể giải mã.",
            ) from exc