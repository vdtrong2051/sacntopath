"""Crash-conscious capture store: per-capture atomic directory commit.

A rename is atomic only inside the same filesystem. We use a staging sibling,
flush files, then rename. This does not claim power-loss durability on every FS.
"""
from pathlib import Path
import json
import os
import shutil
import uuid
import numpy as np
from scantopath.acquisition.sources import FrameBundle
from scantopath.domain.models import CaptureMetadata, Pose


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
