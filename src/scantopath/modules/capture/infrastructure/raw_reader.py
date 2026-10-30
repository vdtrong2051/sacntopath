"""09.02: read-only adapter for existing MetadataStore and SessionStore contracts.

No new tables, no migration, no code assignment, no RAW write, and no Qt imports.
"""
from __future__ import annotations

from pathlib import Path, PurePosixPath
import sqlite3

from scantopath.acquisition.raw_rgbd import RawRgbdCapture
from scantopath.modules.capture.application.contracts import CaptureContext
from scantopath.modules.capture.application.replay import RawReplayError


class RawReaderAdapter:
    """Resolve a registered Capture ID and verify RAW v2 without side effects."""

    @staticmethod
    def _existing_root(supplied: str) -> Path:
        root = Path(supplied).absolute()
        if (not root.is_dir() or root.is_symlink()
                or (hasattr(root, "is_junction") and root.is_junction())):
            raise RawReplayError("STORE_NOT_OPEN", "Hãy chọn một kho dữ liệu hiện có.")
        db_path = root / "metadata.sqlite3"
        if not db_path.is_file() or db_path.is_symlink():
            raise RawReplayError("STORE_NOT_OPEN", "Kho dữ liệu không có SQLite hợp lệ.")
        try:
            db = sqlite3.connect(db_path.resolve(strict=True).as_uri() + "?mode=ro", uri=True)
            try:
                version = db.execute("PRAGMA user_version").fetchone()[0]
            finally:
                db.close()  # Context manager alone would not close on Windows.
        except (OSError, sqlite3.DatabaseError) as exc:
            raise RawReplayError("STORE_NOT_OPEN", "Không đọc được phiên bản kho SQLite.") from exc
        if version not in (1, 2):
            raise RawReplayError("STORE_NOT_OPEN", "Phiên bản SQLite chưa được hỗ trợ.")
        return root.resolve(strict=True)

    @staticmethod
    def _validate_lineage(tree: dict, context: CaptureContext, capture_id: str) -> None:
        for specimen in tree["specimens"]:
            if specimen["specimen_id"] != context.specimen_id:
                continue
            for session in specimen["sessions"]:
                if session["session_id"] != context.session_id:
                    continue
                if any(item["capture_id"] == capture_id for item in session["captures"]):
                    return
        raise RawReplayError("CAPTURE_CONTEXT_MISMATCH", "Bản thu không thuộc Project/Specimen/Session đã chọn.")

    def load(self, context: CaptureContext) -> RawRgbdCapture:
        if not isinstance(context, CaptureContext):
            raise TypeError("context must be CaptureContext")
        try:
            capture_id = context.require_replay_capture_id()
        except ValueError as exc:
            raise RawReplayError("CAPTURE_ID_REQUIRED", "Chưa chọn bản thu để phát lại.") from exc
        root = self._existing_root(context.store_root)

        # Lazy imports: importing the Capture module must not open SQLite or RAW.
        from scantopath.metadata.store import MetadataStore
        from scantopath.storage.session_store import SessionStore
        from scantopath.storage.numbered import NumberedStorageRegistry

        with MetadataStore(root) as metadata:
            try:
                record = metadata.get_capture(capture_id)
            except LookupError as exc:
                raise RawReplayError("CAPTURE_NOT_REGISTERED", "Không tìm thấy bản thu đã đăng ký.") from exc
            try:
                tree = metadata.get_project_tree(context.project_id)
            except LookupError as exc:
                raise RawReplayError("CAPTURE_CONTEXT_MISMATCH", "Không tìm thấy Project của bản thu đã chọn.") from exc
        self._validate_lineage(tree, context, capture_id)

        if (record["capture_id"] != capture_id
                or record["session_id"] != context.session_id
                or record["specimen_id"] != context.specimen_id):
            raise RawReplayError("CAPTURE_CONTEXT_MISMATCH", "Thông tin bản thu không khớp phiên quét.")
        if record["schema_version"] != 2:
            raise RawReplayError("UNSUPPORTED_RAW_SCHEMA", "Replay hiện chỉ hỗ trợ RAW v2.")

        relative = record["relative_path"]
        if (not isinstance(relative, str) or not relative or "\\" in relative
                or relative.startswith("/") or any(part in ("", ".", "..") for part in relative.split("/"))):
            raise RawReplayError("RAW_PATH_UNSAFE", "Đường dẫn bản thu trong SQLite không hợp lệ.")
        parts = PurePosixPath(relative).parts
        path = root.joinpath(*parts)
        store = SessionStore(root)

        try:
            if len(parts) == 4 and parts[0] == "sessions" and parts[2] == "captures":
                packet = store.read_raw(path)
            elif len(parts) == 8 and parts[0] == "01_PROJECTS":
                location = NumberedStorageRegistry(root).resolve_id("capture", capture_id, verify=False)
                if location.relative_path != relative or location.layout_version != 2:
                    raise RawReplayError("STORAGE_MAPPING_MISMATCH", "Ánh xạ Numbered Storage không khớp SQLite.")
                packet = store.read_raw_numbered(
                    path, expected_capture_id=capture_id, expected_session_id=context.session_id,
                )
            else:
                raise RawReplayError("RAW_PATH_UNSAFE", "Đường dẫn bản thu không thuộc layout hỗ trợ.")
        except RawReplayError:
            raise
        except LookupError as exc:
            raise RawReplayError("STORAGE_MAPPING_MISSING", "Bản thu chưa có ánh xạ Numbered Storage.") from exc
        except FileNotFoundError as exc:
            raise RawReplayError("RAW_MISSING", "Không tìm thấy tệp RAW đã đăng ký.") from exc
        except (OSError, RuntimeError, ValueError, TypeError) as exc:
            raise RawReplayError("RAW_INTEGRITY_FAILED", "RAW không đạt kiểm tra nội dung hoặc checksum.") from exc

        if not isinstance(packet, RawRgbdCapture):
            raise RawReplayError("UNSUPPORTED_RAW_SCHEMA", "RAW không phải định dạng v2.")
        if (packet.metadata.capture_id != capture_id
                or packet.metadata.session_id != context.session_id
                or packet.metadata.specimen_id != context.specimen_id):
            raise RawReplayError("CAPTURE_CONTEXT_MISMATCH", "Metadata RAW không khớp bản thu đã chọn.")
        return packet
