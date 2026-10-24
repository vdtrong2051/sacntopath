"""Opt-in RAW structure/checksum inspection; no writes and no metric claims."""
from __future__ import annotations
from .models import CaptureInspection

class CaptureIntegrityChecker:
    def __init__(self, context, queries):
        self.context = context
        self.queries = queries

    def inspect_capture(self, capture_id: str) -> CaptureInspection:
        """Explicit read-only RAW check; v1 structural, v2 SHA-256 + metadata.

        Do not persist success in SQLite. Never leak absolute paths or RAW bytes
        into UI error messages. Registered is not synonymous with verified.
        """
        capture = self.queries.get_capture(capture_id)  # Require registered ID first.

        relative = capture.storage.relative_path
        if not relative:
            return CaptureInspection(capture_id, "missing", capture.schema_version,
                                     "Không có tham chiếu đường dẫn RAW trong SQLite.")
        try:
            path = self.context.safe_raw_path(self.context.root, relative)
            if not path.is_dir():
                return CaptureInspection(capture_id, "missing", capture.schema_version,
                                         "RAW đã đăng ký nhưng thiếu thư mục dữ liệu.")
            self.queries.get_capture(capture_id, verify_raw=True)
        except FileNotFoundError:
            return CaptureInspection(capture_id, "missing", capture.schema_version,
                                     "RAW đã đăng ký nhưng thiếu tệp dữ liệu.")
        except (ValueError, RuntimeError, TypeError) as exc:
            # Bad manifest, ID mismatch, forbidden traversal, bad version, etc.
            return CaptureInspection(capture_id, "corrupt", capture.schema_version,
                                     "RAW không đạt kiểm tra cấu trúc, danh tính hoặc checksum.")
        except (OSError, PermissionError):
            return CaptureInspection(capture_id, "inaccessible", capture.schema_version,
                                     "Không thể đọc RAW vì quyền truy cập hoặc lỗi I/O.")
        if capture.schema_version == 1:
            msg = "Đã kiểm tra cấu trúc RAW v1; định dạng này không có SHA-256."
        else:
            msg = "Đã kiểm tra cấu trúc RAW v2, danh tính và SHA-256."
        return CaptureInspection(capture_id, "verified", capture.schema_version, msg)
