"""Read-only acceptance inspection of the development scantopath-data SQLite store.

Run as a module from repository root. No schema changes or storage writes.
"""
from __future__ import annotations
import argparse
from pathlib import Path
import sqlite3
import json


def inspect(root: Path) -> dict:
    root = root.absolute()
    dbfile = root / "metadata.sqlite3"
    if not root.is_dir() or root.is_symlink() or not dbfile.is_file() or dbfile.is_symlink():
        raise ValueError("STORE_NOT_OPEN")
    db = sqlite3.connect(dbfile.resolve(strict=True).as_uri() + "?mode=ro", uri=True)
    try:
        version = db.execute("PRAGMA user_version").fetchone()[0]
        integrity = db.execute("PRAGMA integrity_check").fetchone()[0]
        fk_errors = len(db.execute("PRAGMA foreign_key_check").fetchall())
        counts = {table: db.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]
                  for table in ("projects", "specimens", "scan_sessions", "captures",
                                "storage_capture_reservations")}
    finally:
        db.close()  # Explicit release for Windows.
    return {"result": "GD2_09_09_1_STORE_INSPECT=PASS" if version == 2 and integrity == "ok" and fk_errors == 0 else "GD2_09_09_1_STORE_INSPECT=FAIL",
            "root": str(root), "schema_version": version,
            "sqlite_integrity_check": integrity,
            "foreign_key_errors": fk_errors, "counts": counts,
            "mode": "READ_ONLY_NO_WRITES"}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", type=Path, default=Path.cwd() / "scantopath-data")
    args = parser.parse_args()
    try:
        data = inspect(args.root)
    except (OSError, ValueError, sqlite3.DatabaseError) as exc:
        print(json.dumps({"result":"GD2_09_09_1_STORE_INSPECT=FAIL",
                          "reason":type(exc).__name__}, indent=2))
        raise SystemExit(1)
    print(json.dumps(data, ensure_ascii=False, indent=2))
    raise SystemExit(0 if data["result"].endswith("PASS") else 1)

if __name__ == "__main__":
    main()
