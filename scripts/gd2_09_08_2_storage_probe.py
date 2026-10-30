"""09.08.2 isolated persistence probe (synthetic RAW, temporary SQLite only).

This is NOT a Gemini 2 hardware test and NOT the end-to-end 09.08.3 gate.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import tempfile
from pathlib import Path

from scantopath.metadata.store import MetadataStore
from scantopath.storage.numbered import NumberedStorageRegistry
from scantopath.modules.capture.application.contracts import CaptureContext
from scantopath.modules.capture.application.capture_service import CaptureCommitService
from scantopath.modules.capture.infrastructure.capture_writer import NumberedCapturePersistenceAdapter
from scantopath.modules.capture.application.replay import RawReplayService
from scantopath.modules.capture.infrastructure.raw_reader import RawReaderAdapter
from tests.support.raw_fixture import raw


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--captures", type=int, default=5)
    args = parser.parse_args()
    if not 1 <= args.captures <= 20:
        parser.error("--captures must be 1..20")
    with tempfile.TemporaryDirectory(prefix="scantopath-0982-") as tmp:
        root = Path(tmp)
        with MetadataStore(root) as db:
            db.create_project("gd2p", "09.08.2 temporary project")
            db.create_specimen("gd2s", "gd2p", "Synthetic specimen")
            db.create_scan_session("gd2t", "gd2s", "Temporary session")
        NumberedStorageRegistry.migrate_database(root)
        service = CaptureCommitService(NumberedCapturePersistenceAdapter())
        registry = NumberedStorageRegistry(root)
        report = []
        for index in range(args.captures):
            cid = f"gd2-0982-{index:03d}"
            ctx = CaptureContext(str(root), "gd2p", "gd2s", "gd2t", cid)
            packet = raw(session="gd2t", specimen="gd2s", capture_id=cid)
            assert service.commit(ctx, packet) == cid
            observed = RawReplayService(RawReaderAdapter()).load(ctx)
            assert observed == packet
            location = registry.resolve_id("capture", cid, verify=True)
            assert location.layout_version == 2
            report.append({
                "capture_id": cid,
                "path": location.relative_path,
                "depth_sha256": hashlib.sha256(observed.depth_y16_le).hexdigest(),
            })
        assert not registry.pending_reservations()
        print(json.dumps({
            "result": "GD2_09_08_2_STORAGE=PASS",
            "data_source": "SYNTHETIC_RAW_V2_FIXTURE",
            "store": "TEMPORARY_AUTO_DELETED",
            "captures": report,
        }, ensure_ascii=False, indent=2))
    print("NO_CAMERA_USED; NO_OPERATOR_STORE_MODIFIED; NO_GIT_OPERATIONS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
