"""Operator entry for R4.2 A/B in-process Qt/VTK comparator, always child-isolated."""
from __future__ import annotations
import argparse
from pathlib import Path
import sys

from scantopath.modules.viewer3d.infrastructure.embedded_poc.contracts import ComparatorRequest
from scantopath.modules.viewer3d.infrastructure.embedded_poc.runner import run_child


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description='R4.2 standalone Qt/VTK comparison runner')
    parser.add_argument('--scenario', choices=['smoke', 'stress', 'manual', 'process_exit_probe'])
    parser.add_argument('--make-fixture', type=Path, help='Create 4-point disposable PLY in evidence folder')
    parser.add_argument('--cycles', type=int, default=1)
    parser.add_argument('--events', type=int, default=12)
    parser.add_argument('--source', type=Path)
    parser.add_argument('--report', type=Path)
    parser.add_argument('--timeout', type=int, default=600)
    args = parser.parse_args(argv)
    if args.make_fixture is not None:
        path = args.make_fixture
        if path.suffix.lower() != '.ply' or path.exists() or not path.parent.is_dir():
            parser.error('fixture destination must be a new PLY under an existing directory')
        path.write_text('ply\nformat ascii 1.0\nelement vertex 4\nproperty float x\nproperty float y\nproperty float z\nend_header\n0 0 0\n1 0 0\n0 1 0\n0 0 1\n', encoding='ascii')
        print('R4.2 disposable fixture created:', path)
        return 0
    if args.scenario is None:
        parser.error('--scenario required unless --make-fixture is specified')
    if args.report is None:
        parser.error('--report required for subprocess scenario')
    request = ComparatorRequest(args.scenario, args.cycles, args.events, args.source)
    try:
        data = run_child(request, args.report, timeout=args.timeout, native=True)
    except (ValueError, OSError, RuntimeError) as error:
        print('R4.2 FAIL: ' + str(error), file=sys.stderr)
        return 2
    print(f'R4.2 PASS: {data}')
    if args.scenario == 'manual':
        print('Manual run ended; this is not operator HMI approval by itself.')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
