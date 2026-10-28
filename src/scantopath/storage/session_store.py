"""Lưu capture theo thư mục tạm và công bố có kiểm soát.

Đổi tên thư mục chỉ nguyên tử trong cùng hệ tệp: ghi vào thư mục tạm bên cạnh,
đẩy dữ liệu xuống hệ tệp rồi đổi tên. Không bảo đảm chống mất điện trên mọi ổ đĩa.
"""
from pathlib import Path
import json
import hashlib
import re
import os
import shutil
import uuid
import numpy as np
from scantopath.acquisition.sources import FrameBundle
from scantopath.acquisition.raw_rgbd import RawRgbdCapture
from scantopath.domain.models import CaptureMetadata, Pose
from scantopath.domain.raw_rgbd import RawRgbdCaptureMetadataV2


class SessionStore:
    def __init__(self, root: str | Path):
        self.root = Path(root).resolve()
        self.root.mkdir(parents=True, exist_ok=True)

    @staticmethod
    def _safe_name(value: str) -> str:
        if not value or not value.isascii() or not all(c.isalnum() or c in "-_" for c in value):
            raise ValueError("IDs must consist of ASCII letters, digits, '_' or '-'")
        return value

    @staticmethod
    def _write_array(path: Path, array: np.ndarray):
        with path.open("wb") as f:
            np.save(f, array, allow_pickle=False)
            f.flush()
            os.fsync(f.fileno())

    def commit(self, frame: FrameBundle, session_id: str, specimen_id: str,
               pose: Pose | None = None, camera_serial: str | None = None,
               sdk_version: str | None = None,
               firmware_version: str | None = None) -> Path:
        self._safe_name(session_id)
        self._safe_name(specimen_id)
        if frame.depth.dtype != np.uint16 or frame.depth.ndim != 2:
            raise ValueError("depth must be uint16 HxW")
        h, w = frame.depth.shape
        if (w, h) != (frame.intrinsics.width, frame.intrinsics.height):
            raise ValueError("depth shape disagrees with intrinsics")
        if frame.rgb.dtype != np.uint8 or frame.rgb.shape != (h, w, 3):
            raise ValueError("rgb must be uint8 HxWx3 and registered to depth dimensions")
        if frame.scale_m_per_unit <= 0:
            raise ValueError("invalid scale")
        meta = CaptureMetadata(
            session_id=session_id, specimen_id=specimen_id, kind=frame.kind,
            camera_model=frame.camera_model, camera_serial=camera_serial,
            sdk_version=sdk_version, firmware_version=firmware_version,
            depth_scale_m_per_unit=frame.scale_m_per_unit,
            intrinsics=frame.intrinsics, pose=pose or Pose(),
            measured=(frame.kind.value == "orbbec"),
            rgb_registered_to_depth=True,
        )
        target_dir = self.root / "sessions" / session_id / "captures"
        target_dir.mkdir(parents=True, exist_ok=True)
        final = target_dir / meta.capture_id
        tmp = target_dir / f".{meta.capture_id}.{uuid.uuid4().hex}.partial"
        tmp.mkdir()
        try:
            self._write_array(tmp / "depth.npy", frame.depth)
            self._write_array(tmp / "rgb.npy", frame.rgb)
            with (tmp / "metadata.json").open("w", encoding="utf-8") as f:
                json.dump(meta.model_dump(mode="json"), f, ensure_ascii=False, indent=2)
                f.flush()
                os.fsync(f.fileno())
            with (tmp / "COMMITTED").open("w", encoding="utf-8") as f:
                f.write("1\n")
                f.flush()
                os.fsync(f.fileno())
            tmp.rename(final)
        finally:
            if tmp.exists():
                shutil.rmtree(tmp)
        return final

    def list_committed(self, session_id: str) -> list[Path]:
        self._safe_name(session_id)
        path = self.root / "sessions" / session_id / "captures"
        if not path.exists():
            return []
        return sorted(p for p in path.iterdir() if p.is_dir() and
                      not p.name.startswith(".") and (p / "COMMITTED").is_file())

    def read(self, path: str | Path) -> tuple[CaptureMetadata, np.ndarray, np.ndarray]:
        path = Path(path)
        if not (path / "COMMITTED").exists():
            raise ValueError("Capture not committed")
        meta = CaptureMetadata.model_validate_json((path / "metadata.json").read_text(encoding="utf-8"))
        with (path / "depth.npy").open("rb") as f:
            depth = np.load(f, allow_pickle=False)
        with (path / "rgb.npy").open("rb") as f:
            rgb = np.load(f, allow_pickle=False)
        if depth.shape != (meta.intrinsics.height, meta.intrinsics.width) or depth.dtype != np.uint16:
            raise ValueError("Invalid stored depth")
        if rgb.shape != (*depth.shape, 3) or rgb.dtype != np.uint8:
            raise ValueError("Invalid stored RGB")
        return meta, depth, rgb


    # PRE-03: lưu RAW v2; giao diện commit()/read() của v1 ở phía trên vẫn được giữ nguyên.
    _RAW_FILES = frozenset({"color.mjpg", "depth.y16", "metadata.json"})
    _RAW_DIRECTORY_FILES = _RAW_FILES | {"manifest.json", "COMMITTED"}

    @staticmethod
    def _write_bytes(path: Path, contents: bytes) -> None:
        with path.open("xb") as stream:
            stream.write(contents)
            stream.flush()
            os.fsync(stream.fileno())

    @staticmethod
    def _digest(contents: bytes) -> str:
        return hashlib.sha256(contents).hexdigest()

    def commit_raw(self, capture: RawRgbdCapture) -> Path:
        """Commit an immutable RAW v2 capture; never decode, align or transform it.

        Writes all files to a sibling .partial directory and renames it only
        after writing the manifest and final COMMITTED marker. The rename is
        atomic on a single filesystem, but is NOT a power-loss durability claim.
        """
        if not isinstance(capture, RawRgbdCapture):
            raise TypeError("capture must be a PRE-02 RawRgbdCapture")
        meta = capture.metadata
        session_id = self._safe_name(meta.session_id)
        capture_id = self._safe_name(meta.capture_id)
        self._safe_name(meta.specimen_id)

        destination = self.root / "sessions" / session_id / "captures" / capture_id
        return self._commit_raw_to_destination(capture, destination)

    def commit_raw_numbered(self, capture: RawRgbdCapture, relative_path: str) -> Path:
        """Explicit v2 layout writer. Caller MUST own a persisted SQLite reservation.

        Unlike commit_raw(), this method never infers capture identity from C-code.
        It does not register or mutate the capture's immutable RAW metadata.
        """
        if not isinstance(capture, RawRgbdCapture):
            raise TypeError("Expected RawRgbdCapture")
        from scantopath.storage.numbered import _safe_path
        import re as _re
        components = relative_path.split("/")
        if (len(components) != 8 or components[0] != "01_PROJECTS"
                or components[2] != "01_SPECIMENS" or components[4] != "01_SESSIONS"
                or components[6] != "01_CAPTURES" or
                not all(_re.fullmatch(p, components[i]) for i, p in
                        ((1, r"P[0-9]{4,}"), (3, r"S[0-9]{4,}"),
                         (5, r"T[0-9]{4,}"), (7, r"C[0-9]{4,}")))):
            raise ValueError("Invalid numbered capture path shape")
        destination = _safe_path(self.root, relative_path, require_exists=False)
        return self._commit_raw_to_destination(capture, destination)

    def _commit_raw_to_destination(self, capture: RawRgbdCapture, destination: Path) -> Path:
        """The exact PRE-03 bytes, manifest and sibling-rename discipline."""
        meta = capture.metadata
        capture_id = self._safe_name(meta.capture_id)
        parent = destination.parent
        parent.mkdir(parents=True, exist_ok=True)
        if destination.exists() or destination.is_symlink():
            raise FileExistsError(f"Capture already exists: {capture_id}")
        partial = parent / f".{capture_id}.{uuid.uuid4().hex}.partial"
        partial.mkdir()
        try:
            data = {
                "color.mjpg": capture.color_mjpeg,
                "depth.y16": capture.depth_y16_le,
                "metadata.json": meta.model_dump_json(indent=2).encode("utf-8"),
            }
            manifest = {
                "manifest_schema_version": 1,
                "capture_schema_version": 2,
                "capture_id": capture_id,
                "files": {
                    name: {
                        "size_bytes": len(payload),
                        "sha256": self._digest(payload),
                    }
                    for name, payload in data.items()
                },
            }
            for name, contents in data.items():
                self._write_bytes(partial / name, contents)
            self._write_bytes(
                partial / "manifest.json",
                (json.dumps(manifest, ensure_ascii=False, sort_keys=True, indent=2) + "\n").encode("utf-8"),
            )
            # Thư mục ghi dở không có dấu COMMITTED để được công bố như capture hoàn chỉnh.
            self._write_bytes(partial / "COMMITTED", b"1\n")
            # Trên Windows, phép đổi tên thư mục không tự ghi đè đích đang tồn tại.
            if destination.exists() or destination.is_symlink():
                raise FileExistsError(f"Capture already exists: {capture_id}")
            partial.rename(destination)
        finally:
            if partial.exists():
                shutil.rmtree(partial)
        return destination

    def read_raw(self, path: str | Path) -> RawRgbdCapture:
        """Verify SHA-256, lengths, metadata and path before returning RAW bytes.

        The hashes detect accidental corruption. They do not authenticate an
        attacker who can edit both payloads and manifest.
        """
        supplied = Path(path)
        # Không cho người gọi chọn capture nằm ngoài kho đã cấu hình;
        # đồng thời từ chối chuyển hướng bằng symbolic link trong thư mục capture.
        location = supplied.resolve(strict=True)
        if location != supplied.absolute():
            raise ValueError("RAW capture path must not use symlinks or traversal")
        try:
            relative = location.relative_to(self.root)
        except ValueError as exc:
            raise ValueError("RAW capture must be inside this SessionStore") from exc
        if (len(relative.parts) != 4 or relative.parts[0] != "sessions"
                or relative.parts[2] != "captures"):
            raise ValueError("Not a capture directory")
        session_id = self._safe_name(relative.parts[1])
        capture_id = self._safe_name(relative.parts[3])
        return self._read_v2_contents(location, capture_id, session_id)

    def read_raw_numbered(self, path: str | Path, *, expected_capture_id: str,
                          expected_session_id: str) -> RawRgbdCapture:
        """Read numbered v2 RAW by verified registry identity, not C-code basename."""
        from scantopath.storage.numbered import _safe_path
        relative = Path(path).absolute().relative_to(self.root).as_posix()
        components = relative.split("/")
        if (len(components) != 8 or components[0] != "01_PROJECTS"
                or components[2] != "01_SPECIMENS" or components[4] != "01_SESSIONS"
                or components[6] != "01_CAPTURES" or
                not all(re.fullmatch(pattern, components[index]) for index, pattern in
                        ((1, r"P[0-9]{4,}"), (3, r"S[0-9]{4,}"),
                         (5, r"T[0-9]{4,}"), (7, r"C[0-9]{4,}")))):
            raise ValueError("Not a numbered capture directory")
        location = _safe_path(self.root, relative, require_exists=True)
        return self._read_v2_contents(location, self._safe_name(expected_capture_id),
                                      self._safe_name(expected_session_id))

    def _read_v2_contents(self, location: Path, capture_id: str,
                          session_id: str) -> RawRgbdCapture:
        """Shared RAW-v2 payload verification (same hashing for legacy and numbered)."""
        if not location.is_dir():
            raise ValueError("Capture path is not a directory")
        if {item.name for item in location.iterdir()} != self._RAW_DIRECTORY_FILES:
            raise ValueError("RAW capture files are incomplete or unexpected")
        for name in self._RAW_DIRECTORY_FILES:
            entry = location / name
            if entry.is_symlink() or not entry.is_file():
                raise ValueError(f"Invalid RAW file entry: {name}")
        if (location / "COMMITTED").read_bytes() != b"1\n":
            raise ValueError("RAW capture is not committed")

        manifest = json.loads((location / "manifest.json").read_text(encoding="utf-8"))
        if not isinstance(manifest, dict) or set(manifest) != {
            "manifest_schema_version", "capture_schema_version", "capture_id", "files"
        }:
            raise ValueError("Invalid RAW manifest structure")
        if (type(manifest["manifest_schema_version"]) is not int or
                manifest["manifest_schema_version"] != 1 or
                type(manifest["capture_schema_version"]) is not int or
                manifest["capture_schema_version"] != 2 or
                manifest["capture_id"] != capture_id or
                not isinstance(manifest["files"], dict) or
                set(manifest["files"]) != self._RAW_FILES):
            raise ValueError("Invalid RAW manifest version, ID or file list")

        verified: dict[str, bytes] = {}
        for name in self._RAW_FILES:
            descriptor = manifest["files"][name]
            if (not isinstance(descriptor, dict) or
                    set(descriptor) != {"size_bytes", "sha256"} or
                    type(descriptor["size_bytes"]) is not int or
                    descriptor["size_bytes"] <= 0 or
                    not isinstance(descriptor["sha256"], str) or
                    re.fullmatch(r"[0-9a-f]{64}", descriptor["sha256"]) is None):
                raise ValueError(f"Invalid RAW manifest entry: {name}")
            file_path = location / name
            if file_path.stat().st_size != descriptor["size_bytes"]:
                raise ValueError(f"RAW file length mismatch: {name}")
            contents = file_path.read_bytes()
            if len(contents) != descriptor["size_bytes"] or self._digest(contents) != descriptor["sha256"]:
                raise ValueError(f"RAW checksum mismatch: {name}")
            verified[name] = contents

        metadata = RawRgbdCaptureMetadataV2.model_validate_json(verified["metadata.json"])
        if metadata.session_id != session_id or metadata.capture_id != capture_id:
            raise ValueError("RAW capture metadata disagrees with directory identity")
        return RawRgbdCapture(
            metadata=metadata,
            color_mjpeg=verified["color.mjpg"],
            depth_y16_le=verified["depth.y16"],
        )

    def read_capture(self, path: str | Path) -> tuple[CaptureMetadata, np.ndarray, np.ndarray] | RawRgbdCapture:
        """Version-aware read; v1 returns its original tuple, v2 returns RAW."""
        capture_dir = Path(path)
        if not (capture_dir / "COMMITTED").is_file():
            raise ValueError("Capture not committed")
        # Tại đây chỉ nhận diện phiên bản; RAW v2 còn phải kiểm tra toàn bộ hash metadata.
        with (capture_dir / "metadata.json").open("r", encoding="utf-8") as stream:
            version = json.load(stream).get("schema_version")
        if type(version) is not int:
            raise ValueError("Invalid capture schema version")
        if version == 1:
            return self.read(capture_dir)
        if version == 2:
            return self.read_raw(capture_dir)
        raise ValueError(f"Unsupported capture schema version: {version}")
