"""PRE-04 CLI: capture one Gemini 2 RAW pair, or verify a stored v2 capture.

Examples:
  python -m scantopath.acquisition.capture_once --once --session s1 --specimen p1
  python -m scantopath.acquisition.capture_once --verify PATH --output ROOT

Verification does not import or access native hardware.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

from scantopath.acquisition.orbbec_adapter import capture_one_raw
from scantopath.storage.session_store import SessionStore


def _summary(capture, directory: Path) -> dict:
    m = capture.metadata
    return {
        "capture_id": m.capture_id,
        "session_id": m.session_id,
        "specimen_id": m.specimen_id,
        "schema_version": m.schema_version,
        "kind": m.kind.value,
        "measured": m.measured,
        "color": {
            "encoding": m.color.encoding.value,
            "size": [m.color.width, m.color.height],
            "bytes": len(capture.color_mjpeg),
            "timestamp_us": m.color.timestamp_us,
        },
        "depth": {
            "encoding": m.depth.encoding.value,
            "size": [m.depth.width, m.depth.height],
            "bytes": len(capture.depth_y16_le),
            "timestamp_us": m.depth.timestamp_us,
        },
        "alignment_mode": m.alignment_mode,
        "camera_pose_known": m.camera_pose is not None,
        "timestamp_delta_us_diagnostic_only": m.observed_timestamp_delta_us,
        "depth_scale_m_per_unit": m.depth_scale_m_per_unit,
        "capture_path": str(directory),
        "saved": True,
        "checksum_verified": True,
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="ScanToPath PRE-04 one-shot RAW acquisition & verification")
    actions = parser.add_mutually_exclusive_group(required=True)
    actions.add_argument("--once", action="store_true", help="Open Gemini 2 and persist one capture")
    actions.add_argument("--verify", metavar="CAPTURE_DIR", help="Verify a saved capture without camera")
    parser.add_argument("--output", default="./scantopath-data", help="SessionStore root")
    parser.add_argument("--session", help="Session ID (required with --once)")
    parser.add_argument("--specimen", help="Specimen ID (required with --once)")
    args = parser.parse_args(argv)

    if args.once:
        if not args.session or not args.specimen:
            parser.error("--once requires --session and --specimen")
        # Validate identifiers BEFORE hardware is opened.
        SessionStore._safe_name(args.session)
        SessionStore._safe_name(args.specimen)

    store = SessionStore(args.output)
    if args.once:
        capture = capture_one_raw(session_id=args.session, specimen_id=args.specimen)
        path = store.commit_raw(capture)
        replay = store.read_raw(path)
        if replay != capture:
            raise RuntimeError("Saved RAW capture differs from original in-memory packet")
    else:
        path = Path(args.verify)
        replay = store.read_raw(path)
    print(json.dumps(_summary(replay, path.resolve()), ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
