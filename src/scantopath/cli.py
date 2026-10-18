"""Offline-first test commands; hardware capture is not claimed."""
import argparse
import json
from pathlib import Path
from scantopath.acquisition.sources import SyntheticSource
from scantopath.storage.session_store import SessionStore
from scantopath.domain.models import Pose


def main() -> None:
    parser = argparse.ArgumentParser(prog="scantopath")
    sub = parser.add_subparsers(dest="command", required=True)
    demo = sub.add_parser("demo", help="Create a synthetic fixture capture")
    demo.add_argument("--output", default="./scantopath-data")
    demo.add_argument("--session", default="fixture-001")
    demo.add_argument("--specimen", default="test-cylinder")
    check = sub.add_parser("verify", help="Reopen all committed captures and validate schema/shape")
    check.add_argument("--output", default="./scantopath-data")
    check.add_argument("--session", default="fixture-001")
    args = parser.parse_args()
    store = SessionStore(args.output)
    if args.command == "demo":
        path = store.commit(SyntheticSource().capture(), args.session, args.specimen,
                            pose=Pose(theta_deg=0, phi_deg=0, frame="manual"))
        print(json.dumps({"status":"committed", "synthetic":True, "path":str(path)}, indent=2))
    elif args.command == "verify":
        captures = store.list_committed(args.session)
        for path in captures:
            meta, depth, rgb = store.read(path)
            print(json.dumps({"capture_id":meta.capture_id,"kind":meta.kind.value,
                              "shape":list(depth.shape),"valid_depth_pixels":int((depth>0).sum()),
                              "measured":meta.measured}))
        print(f"Verified {len(captures)} committed capture(s)")


if __name__ == "__main__":
    main()
