"""PRE-05 opt-in metadata CLI. PRE-04 camera/storage CLI is unchanged.

Example:
 python -m scantopath.metadata.cli --root ./scantopath-data create-project --id project-001 --name 'Scan research'
"""
from __future__ import annotations

import argparse
import json
from scantopath.metadata.store import MetadataStore


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="ScanToPath GĐ0 project/specimen/session metadata")
    parser.add_argument("--root", default="./scantopath-data", help="Shared SessionStore root")
    subs = parser.add_subparsers(dest="command", required=True)

    p = subs.add_parser("create-project")
    p.add_argument("--id", required=True)
    p.add_argument("--name", required=True)
    p.add_argument("--description", default="")

    p = subs.add_parser("update-project")
    p.add_argument("--id", required=True)
    p.add_argument("--name")
    p.add_argument("--description")

    subs.add_parser("list-projects")

    p = subs.add_parser("create-specimen")
    p.add_argument("--id", required=True)
    p.add_argument("--project", required=True)
    p.add_argument("--label", required=True)
    p.add_argument("--description", default="")

    p = subs.add_parser("update-specimen")
    p.add_argument("--id", required=True)
    p.add_argument("--label")
    p.add_argument("--description")

    p = subs.add_parser("create-session")
    p.add_argument("--id", required=True)
    p.add_argument("--specimen", required=True)
    p.add_argument("--label", default="Scan")

    p = subs.add_parser("close-session")
    p.add_argument("--id", required=True)

    p = subs.add_parser("register-capture")
    p.add_argument("--path", required=True)

    p = subs.add_parser("show-capture")
    p.add_argument("--id", required=True)
    p.add_argument("--verify", action="store_true")

    p = subs.add_parser("create-run")
    p.add_argument("--id")
    p.add_argument("--session", required=True)
    p.add_argument("--stage", required=True)
    p.add_argument("--algorithm", required=True)
    p.add_argument("--version", required=True)
    p.add_argument("--input", required=True, action="append", dest="inputs")
    p.add_argument("--parameters", default="{}", help="JSON object of primitive parameters")

    p = subs.add_parser("start-run")
    p.add_argument("--id", required=True)

    p = subs.add_parser("finish-run")
    p.add_argument("--id", required=True)
    p.add_argument("--state", choices=("succeeded", "failed"), required=True)
    p.add_argument("--output-file", action="append", default=[])
    p.add_argument("--error-message")

    p = subs.add_parser("show-run")
    p.add_argument("--id", required=True)

    p = subs.add_parser("tree")
    p.add_argument("--project", required=True)

    p = subs.add_parser("log-event")
    p.add_argument("--level", choices=("INFO", "WARNING", "ERROR"), required=True)
    p.add_argument("--action", required=True)
    p.add_argument("--entity-type", required=True)
    p.add_argument("--entity-id", required=True)
    p.add_argument("--details", default="{}", help="Sanitized JSON object")

    p = subs.add_parser("events")
    p.add_argument("--limit", type=int, default=100)

    args = parser.parse_args(argv)
    with MetadataStore(args.root) as store:
        if args.command == "create-project":
            result = store.create_project(args.id, args.name, args.description)
        elif args.command == "update-project":
            result = store.update_project(args.id, name=args.name, description=args.description)
        elif args.command == "list-projects":
            result = store.list_projects()
        elif args.command == "create-specimen":
            result = store.create_specimen(args.id, args.project, args.label, args.description)
        elif args.command == "update-specimen":
            result = store.update_specimen(args.id, label=args.label, description=args.description)
        elif args.command == "create-session":
            result = store.create_scan_session(args.id, args.specimen, args.label)
        elif args.command == "close-session":
            result = store.close_scan_session(args.id)
        elif args.command == "register-capture":
            result = store.register_capture(args.path)
        elif args.command == "show-capture":
            result = store.get_capture(args.id, verify_raw=args.verify)
        elif args.command == "create-run":
            result = store.create_processing_run(
                run_id=args.id, session_id=args.session, stage=args.stage,
                algorithm=args.algorithm, version=args.version,
                input_capture_ids=args.inputs, parameters=json.loads(args.parameters),
            )
        elif args.command == "start-run":
            result = store.start_processing_run(args.id)
        elif args.command == "finish-run":
            result = store.finish_processing_run(
                args.id, state=args.state, output_files=args.output_file,
                error_message=args.error_message,
            )
        elif args.command == "show-run":
            result = store.get_processing_run(args.id)
        elif args.command == "tree":
            result = store.get_project_tree(args.project)
        elif args.command == "log-event":
            result = store.record_event(
                level=args.level, action=args.action,
                entity_type=args.entity_type, entity_id=args.entity_id,
                details=json.loads(args.details),
            )
        elif args.command == "events":
            result = store.list_events(limit=args.limit)
        else:
            parser.error("Unknown action")
    print(json.dumps(result, indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
