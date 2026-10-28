"""Opt-in operator CLI for 07.7: dry-run is read-only by default."""
from __future__ import annotations
import argparse
import json
from scantopath.storage.legacy_migration import LegacyRawMigrator


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description='07.7 opt-in legacy RAW migration; CLOSE ScanToPath first')
    p.add_argument('--root', required=True, help='Existing numbered SQLite v2 storage root')
    sub = p.add_subparsers(dest='action', required=True)
    dry = sub.add_parser('dry-run', help='No writes, no backups, no allocations')
    dry.add_argument('--capture-id', default=None)
    apply = sub.add_parser('apply', help='Copy RAW then atomically switch SQLite references')
    apply.add_argument('--capture-id', default=None)
    apply.add_argument('--confirm', action='store_true')
    rollback = sub.add_parser('rollback', help='Return SQLite refs to ORIGINAL legacy RAW')
    rollback.add_argument('--migration-id', required=True)
    rollback.add_argument('--confirm', action='store_true')
    args = p.parse_args(argv)
    if args.action in ('apply', 'rollback') and not args.confirm:
        p.error('This is a durable data change: repeat with --confirm after reviewing dry-run and backups')
    migrator = LegacyRawMigrator(args.root)
    if args.action == 'dry-run':
        items = migrator.plan(capture_id=args.capture_id)
        result = {'status': 'dry_run', 'eligible_count': len(items), 'items': [
            {'capture_id': item.capture_id, 'raw_schema_version': item.schema_version,
             'source': item.source, 'target': item.target, 'file_count': len(item.hashes)}
            for item in items]}
    elif args.action == 'apply':
        result = migrator.apply(capture_id=args.capture_id)
    else:
        result = migrator.rollback(args.migration_id)
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0

if __name__ == '__main__':
    raise SystemExit(main())
