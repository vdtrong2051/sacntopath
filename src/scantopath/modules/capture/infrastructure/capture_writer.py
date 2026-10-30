"""GD2-09.08.2: numbered RAW v2 persistence using existing GĐ1 contracts.

No new SQLite tables, hidden migrations, RAW rewrites, Qt or camera access.
A registered capture is always independently checked through RAW Replay.
"""
from __future__ import annotations

import sqlite3
from pathlib import Path
from typing import Callable, Any

from scantopath.acquisition.raw_rgbd import RawRgbdCapture
from scantopath.modules.capture.application.contracts import CaptureContext
from scantopath.modules.capture.application.capture_service import CaptureCommitError


class NumberedCapturePersistenceAdapter:
    """Implements CapturePersistencePort; one explicit capture per call.

    Failed post-write registration keeps the durable reservation and RAW bytes.
    Recovery is intentionally explicit and never replaces existing RAW files.
    """

    def __init__(
        self,
        *,
        registry_factory: Callable[[Path], Any] | None = None,
        replay_factory: Callable[[], Any] | None = None,
    ) -> None:
        # Factories are resolved only when a command is executed.
        self._registry_factory = registry_factory
        self._replay_factory = replay_factory

    @staticmethod
    def _preflight(context: CaptureContext) -> Path:
        root = Path(context.store_root).absolute()
        if (not root.is_dir() or root.is_symlink()
                or (hasattr(root, "is_junction") and root.is_junction())):
            raise CaptureCommitError("STORE_NOT_OPEN")
        db_path = root / "metadata.sqlite3"
        if not db_path.is_file() or db_path.is_symlink():
            raise CaptureCommitError("STORE_NOT_OPEN")
        try:
            db = sqlite3.connect(
                db_path.resolve(strict=True).as_uri() + "?mode=ro",
                uri=True,
            )
            try:
                if db.execute("PRAGMA user_version").fetchone()[0] != 2:
                    raise CaptureCommitError("NUMBERED_SCHEMA_REQUIRED")
                row = db.execute(
                    "SELECT ss.state FROM scan_sessions AS ss "
                    "JOIN specimens AS sp ON sp.specimen_id=ss.specimen_id "
                    "JOIN projects AS p ON p.project_id=sp.project_id "
                    "WHERE ss.session_id=? AND sp.specimen_id=? AND p.project_id=?",
                    (context.session_id, context.specimen_id, context.project_id),
                ).fetchone()
            finally:
                db.close()
        except CaptureCommitError:
            raise
        except (OSError, sqlite3.DatabaseError) as exc:
            raise CaptureCommitError("STORE_NOT_OPEN") from exc
        if row is None:
            raise CaptureCommitError("CAPTURE_CONTEXT_MISMATCH")
        if row[0] != "open":
            raise CaptureCommitError("SESSION_NOT_OPEN")
        return root.resolve(strict=True)

    def validate_context(self, context: CaptureContext) -> None:
        """Read-only preflight for 09.08.3; reject bad session before camera acquisition.

        Registration still re-checks live session state inside its transaction;
        preflight alone does not reserve a Capture slot or claim atomicity.
        """
        if not isinstance(context, CaptureContext):
            raise TypeError("context must be CaptureContext")
        self._preflight(context)

    def _registry(self, root: Path):
        if self._registry_factory is not None:
            return self._registry_factory(root)
        from scantopath.storage.numbered import NumberedStorageRegistry
        return NumberedStorageRegistry(root)

    def _replay(self, context: CaptureContext, capture_id: str) -> RawRgbdCapture:
        from scantopath.modules.capture.application.replay import RawReplayService
        from scantopath.modules.capture.infrastructure.raw_reader import RawReaderAdapter
        source = self._replay_factory() if self._replay_factory is not None else RawReaderAdapter()
        scoped = CaptureContext(
            context.store_root, context.project_id, context.specimen_id,
            context.session_id, capture_id,
        )
        return RawReplayService(source).load(scoped)

    @staticmethod
    def _existing_reservation(registry: Any, capture_id: str) -> bool:
        return any(item.capture_id == capture_id for item in registry.pending_reservations())

    def _verify_registered(
        self, context: CaptureContext, capture_id: str, expected: RawRgbdCapture,
    ) -> None:
        try:
            result = self._replay(context, capture_id)
        except Exception as exc:
            raise CaptureCommitError("REPLAY_VERIFICATION_FAILED") from exc
        if result != expected:
            raise CaptureCommitError("REPLAY_VERIFICATION_FAILED")

    def commit(self, context: CaptureContext, raw: RawRgbdCapture) -> str:
        if not isinstance(context, CaptureContext):
            raise TypeError("context must be CaptureContext")
        if not isinstance(raw, RawRgbdCapture):
            raise TypeError("raw must be RawRgbdCapture")
        meta = raw.metadata
        if (meta.schema_version != 2 or meta.session_id != context.session_id
                or meta.specimen_id != context.specimen_id
                or (context.capture_id is not None and meta.capture_id != context.capture_id)):
            raise CaptureCommitError("CAPTURE_CONTEXT_MISMATCH")
        root = self._preflight(context)
        registry = self._registry(root)
        capture_id = meta.capture_id

        # Never restart a half-completed write automatically: an operator must
        # inspect and explicitly recover a verified pending reservation.
        if self._existing_reservation(registry, capture_id):
            raise CaptureCommitError("CAPTURE_RECOVERY_REQUIRED")
        try:
            registry.reserve_capture(capture_id, context.session_id, context.specimen_id)
        except (ValueError, sqlite3.IntegrityError) as exc:
            raise CaptureCommitError("CAPTURE_RESERVE_REJECTED") from exc
        except Exception as exc:
            raise CaptureCommitError("CAPTURE_RESERVE_FAILED") from exc
        try:
            path = registry.write_reserved_capture(raw)
        except Exception as exc:
            # Pending reservation is intentionally retained, even after a failed write.
            raise CaptureCommitError("RAW_WRITE_FAILED") from exc

        # Check disk bytes/manifest BEFORE registration, so corruption cannot
        # become a visible capture in SQLite.
        try:
            from scantopath.storage.session_store import SessionStore
            observed = SessionStore(root).read_raw_numbered(
                path,
                expected_capture_id=capture_id,
                expected_session_id=context.session_id,
            )
            if observed != raw:
                raise ValueError("read-back differs from requested RAW v2")
        except Exception as exc:
            raise CaptureCommitError("RAW_INTEGRITY_FAILED") from exc
        try:
            registry.register_reserved_capture(capture_id)
        except Exception as exc:
            # The RAW directory and its reservation must NOT be deleted.
            raise CaptureCommitError("CAPTURE_REGISTRATION_FAILED") from exc
        # This is a post-commit verification: if it fails, do not claim success,
        # but the registered capture may already exist and must be investigated.
        self._verify_registered(context, capture_id, raw)
        return capture_id

    def recover(self, context: CaptureContext, capture_id: str) -> str:
        """Explicitly register a previously written, complete, verified RAW.

        This never calls write_reserved_capture; it cannot overwrite bytes.
        """
        if not isinstance(context, CaptureContext):
            raise TypeError("context must be CaptureContext")
        if (not isinstance(capture_id, str) or not capture_id
                or not capture_id.isascii()
                or not all(ch.isalnum() or ch in "_-" for ch in capture_id)
                or (context.capture_id is not None and context.capture_id != capture_id)):
            raise CaptureCommitError("INVALID_CAPTURE_ID")
        root = self._preflight(context)
        registry = self._registry(root)
        matches = [r for r in registry.pending_reservations() if r.capture_id == capture_id]
        if len(matches) != 1 or matches[0].session_id != context.session_id:
            raise CaptureCommitError("CAPTURE_RESERVATION_NOT_FOUND")
        reservation = matches[0]
        # The numbered store itself validates relative path safety and SHA.
        try:
            from scantopath.storage.session_store import SessionStore
            raw = SessionStore(root).read_raw_numbered(
                root / reservation.relative_path,
                expected_capture_id=capture_id,
                expected_session_id=context.session_id,
            )
        except (OSError, ValueError, RuntimeError, FileNotFoundError) as exc:
            raise CaptureCommitError("RAW_INTEGRITY_FAILED") from exc
        if raw.metadata.specimen_id != context.specimen_id:
            raise CaptureCommitError("CAPTURE_CONTEXT_MISMATCH")
        try:
            registry.register_reserved_capture(capture_id)
        except Exception as exc:
            raise CaptureCommitError("CAPTURE_REGISTRATION_FAILED") from exc
        self._verify_registered(context, capture_id, raw)
        return capture_id
