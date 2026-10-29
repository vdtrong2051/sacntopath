"""GĐ2-09.01 immutable operator context, not a persistent session or hardware handle.

Selection must be explicitly resolved against Project data before capture.
"""
from __future__ import annotations
from dataclasses import dataclass
from re import fullmatch


@dataclass(frozen=True, slots=True)
class CaptureContext:
    store_root: str
    project_id: str
    specimen_id: str
    session_id: str
    capture_id: str | None = None

    def __post_init__(self) -> None:
        if not isinstance(self.store_root, str) or not self.store_root.strip():
            raise ValueError("store_root must be an explicitly selected nonempty path")
        for field in ("project_id", "specimen_id", "session_id", "capture_id"):
            value = getattr(self, field)
            if value is None and field == "capture_id":
                continue
            if not isinstance(value, str) or fullmatch(r"[A-Za-z0-9_-]+", value) is None:
                raise ValueError(f"invalid {field}")

    def require_replay_capture_id(self) -> str:
        """Replay requires an explicit Capture reference; never guess latest."""
        if self.capture_id is None:
            raise ValueError("RAW replay requires an explicit capture_id")
        return self.capture_id
