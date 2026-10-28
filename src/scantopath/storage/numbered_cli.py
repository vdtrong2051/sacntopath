"""Operator-only numbered registry CLI. No automatic migration or camera use.

Examples:
 python -m scantopath.storage.numbered_cli --root ./scantopath-data status
 python -m scantopath.storage.numbered_cli --root ./scantopath-data migrate --confirm
 python -m scantopath.storage.numbered_cli --root ./scantopath-data assign-all
"""
from __future__ import annotations

import argparse
from dataclasses import asdict
import json
from pathlib import Path
import sqlite3

from scantopath.storage.numbered import NumberedStorageRegistry


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="ScanToPath numbered storage registry (07.2)")
    parser.add_argument("--root", default="./scantopath-data")
    sub = parser.add_subparsers(dest="action", required=True)
    sub.add_parser("status")
    mig = sub.add_parser("migrate")
    mig.add_argument("--confirm", action="store_true", help="Explicitly authorize schema migration + backup")
    sub.add_parser("assign-all")
    item = sub.add_parser("assign")
    item.add_argument("--kind", required=True, choices=("project", "specimen", "session", "capture", "run"))
    item.add_argument("--id", required=True)
    item = sub.add_parser("resolve")
    group = item.add_mutually_exclusive_group(required=True)
    group.add_argument("--public-path")
    group.add_argument("--id")
    item.add_argument("--kind", choices=("project", "specimen", "session", "capture", "run"))
    item.add_argument("--verify", action="store_true")
    sub.add_parser("catalog")
    sub.add_parser("pending")
    args = parser.parse_args(argv)
    root = Path(args.root).absolute()
    if args.action == "status":
        file = root / "metadata.sqlite3"
        if not file.is_file():
            result = {"database": "missing", "schema_version": None}
        else:
            with sqlite3.connect(f"file:{file.as_posix()}?mode=ro", uri=True) as db:
                result = {"database": "present", "schema_version": db.execute("PRAGMA user_version").fetchone()[0]}
    elif args.action == "migrate":
        if not args.confirm:
            parser.error("Migration writes SQLite schema: repeat with --confirm after closing app and backing up data")
        result = {"backup": str(NumberedStorageRegistry.migrate_database(root)), "schema_version": 2}
    else:
        registry = NumberedStorageRegistry(root)
        if args.action == "assign-all":
            result = registry.assign_all()
        elif args.action == "assign":
            result = asdict(registry.assign(args.kind, args.id))
        elif args.action == "resolve":
            if args.id:
                if args.kind is None:
                    parser.error("--id requires --kind")
                result = asdict(registry.resolve_id(args.kind, args.id, verify=args.verify))
            else:
                if args.kind is not None:
                    parser.error("--public-path does not accept --kind")
                result = asdict(registry.resolve_public_path(args.public_path, verify=args.verify))
        elif args.action == "catalog":
            result = {"exported": str(registry.export_catalog())}
        else:
            result = [asdict(x) for x in registry.pending_reservations()]
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
