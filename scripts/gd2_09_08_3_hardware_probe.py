"""GD2-09.08.3: REAL Gemini 2 -> isolated IPC -> RAW v2 -> SQLite -> replay.

Creates ONLY a fresh private test store: temporary by default, or --keep-root
pointing to a NEW, non-existing directory. No GUI, automatic migration of an
existing operator store, raw pose inference or dimensional-accuracy claims.
"""
from __future__ import annotations

import argparse
from contextlib import closing, contextmanager
import hashlib
import json
from pathlib import Path
import sqlite3
import sys
import tempfile

from scantopath.metadata.store import MetadataStore
from scantopath.storage.numbered import NumberedStorageRegistry
from scantopath.modules.capture.application.contracts import CaptureContext
from scantopath.modules.capture.application.capture_service import CaptureCommitService
from scantopath.modules.capture.application.capture_pipeline import CapturePipelineService
from scantopath.modules.capture.application.replay import RawReplayService
from scantopath.modules.capture.infrastructure.capture_writer import NumberedCapturePersistenceAdapter
from scantopath.modules.capture.infrastructure.process_camera import ProcessIsolatedCameraAdapter
from scantopath.modules.capture.infrastructure.raw_reader import RawReaderAdapter


@contextmanager
def new_store_root(keep_root: str | None):
    if keep_root is None:
        with tempfile.TemporaryDirectory(prefix="scantopath-gd2-0983-") as directory:
            yield Path(directory), "TEMPORARY_AUTO_DELETED"
        return
    root = Path(keep_root).expanduser().absolute()
    if root.exists() or root.is_symlink():
        raise ValueError("KEEP_ROOT_MUST_NOT_EXIST: choose a new evidence directory")
    if root.parent.is_symlink() or (hasattr(root.parent, "is_junction") and root.parent.is_junction()):
        raise ValueError("KEEP_ROOT_PARENT_CANNOT_BE_A_LINK")
    root.mkdir(parents=True, exist_ok=False)
    yield root, "NEW_PERSISTED_EVIDENCE_STORE"


def initialize(root: Path):
    with MetadataStore(root) as db:
        db.create_project("gd2p0983", "09.08.3 Gemini 2 acceptance")
        db.create_specimen("gd2s0983", "gd2p0983", "Handheld test specimen")
        db.create_scan_session("gd2t0983", "gd2s0983", "Real keyframes")
    NumberedStorageRegistry.migrate_database(root)
    return CaptureContext(str(root), "gd2p0983", "gd2s0983", "gd2t0983")


def run(count: int, keep_root: str | None) -> dict:
    with new_store_root(keep_root) as (root, storage_kind):
        context = initialize(root)
        writer = NumberedCapturePersistenceAdapter()
        # Verify store and exact Project/Session BEFORE native device is opened.
        writer.validate_context(context)
        camera = ProcessIsolatedCameraAdapter()
        report = []
        try:
            camera.open()
            preview_before = camera.read_next(per_attempt_timeout_ms=300, max_attempts=1)
            pipeline = CapturePipelineService(camera, CaptureCommitService(writer), writer)
            replay = RawReplayService(RawReaderAdapter())
            registry = NumberedStorageRegistry(root)

            for _ in range(count):
                receipt = pipeline.capture_and_commit(context)
                selected = CaptureContext(
                    str(root), context.project_id, context.specimen_id,
                    context.session_id, receipt.capture_id,
                )
                stored = replay.load(selected)
                meta = stored.metadata
                assert meta.kind.value == "orbbec" and meta.measured is True
                assert meta.schema_version == 2 and meta.camera_pose is None
                assert meta.alignment_mode == "disabled"
                assert meta.color_intrinsics.fx > 0 and meta.depth_intrinsics.fx > 0
                assert len(meta.color_distortion.k1_k6_p1_p2) == 8
                assert len(meta.depth_distortion.k1_k6_p1_p2) == 8
                assert len(meta.depth_to_color.rotation) == 9
                assert len(meta.depth_to_color.translation_mm) == 3
                assert meta.depth_scale_m_per_unit > 0
                assert hashlib.sha256(stored.color_mjpeg).hexdigest() == receipt.color_sha256
                assert hashlib.sha256(stored.depth_y16_le).hexdigest() == receipt.depth_sha256
                location = registry.resolve_id("capture", receipt.capture_id, verify=True)
                assert location.layout_version == 2
                report.append({
                    "capture_id": receipt.capture_id,
                    "storage_path": location.relative_path,
                    "color_frame_index": receipt.color_frame_index,
                    "depth_frame_index": receipt.depth_frame_index,
                    "color_dimensions": [meta.color.width, meta.color.height],
                    "depth_dimensions": [meta.depth.width, meta.depth.height],
                    "color_timestamp_us": receipt.color_timestamp_us,
                    "depth_timestamp_us": receipt.depth_timestamp_us,
                    "timestamp_delta_us_diagnostic_only": meta.observed_timestamp_delta_us,
                    "depth_scale_m_per_unit": meta.depth_scale_m_per_unit,
                    "color_sha256": receipt.color_sha256,
                    "depth_sha256": receipt.depth_sha256,
                    "depth_to_color_translation_mm": list(meta.depth_to_color.translation_mm),
                    "verification": "RAW_REPLAY_AND_SHA256_PASS",
                })
            preview_after = camera.read_next(per_attempt_timeout_ms=300, max_attempts=1)
            assert preview_after.color_frame_index > preview_before.color_frame_index
            assert preview_after.depth_frame_index > preview_before.depth_frame_index
            assert len(report) == count
            assert len({x["capture_id"] for x in report}) == count
            assert len({x["storage_path"] for x in report}) == count
            assert not registry.pending_reservations()
            with closing(sqlite3.connect(root / "metadata.sqlite3")) as db:
                assert db.execute("SELECT COUNT(*) FROM captures").fetchone()[0] == count
                assert db.execute("SELECT COUNT(*) FROM storage_captures").fetchone()[0] == count
            camera.close()
            assert camera.last_exit_code == 0
        except BaseException:
            try:
                camera.close()
            except Exception as close_exc:
                print("CAMERA_CLOSE_FAILED", type(close_exc).__name__, str(close_exc), file=sys.stderr)
            raise

        result = {
            "result": "GD2_09_08_3_HARDWARE_STORAGE_REPLAY=PASS",
            "source": "REAL_ORBBEC_GEMINI_2",
            "store_mode": storage_kind,
            "store_root": str(root) if keep_root else "TEMPORARY_AUTO_DELETED",
            "capture_count": count,
            "camera_preview_resumed": True,
            "pending_reservations": 0,
            "captures": report,
        }
        if keep_root:
            (root / "gd2_09_08_3_probe_report.json").write_text(
                json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8",
            )
        return result


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--captures", type=int, default=5)
    parser.add_argument("--keep-root", type=str, default=None,
                        help="Optional NEW directory to keep RAW/SQLite evidence; must not exist.")
    args = parser.parse_args()
    if not 1 <= args.captures <= 20:
        parser.error("--captures must be 1..20")
    try:
        report = run(args.captures, args.keep_root)
    except Exception as exc:
        print("GD2_09_08_3_HARDWARE_STORAGE_REPLAY=FAIL",
              type(exc).__name__, str(exc), file=sys.stderr)
        return 1
    print(json.dumps(report, ensure_ascii=False, indent=2))
    print("NO_EXISTING_OPERATOR_STORE_MODIFIED; NO_GIT_OPERATIONS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
