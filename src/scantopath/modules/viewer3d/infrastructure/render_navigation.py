"""Isolated one-action camera render. No Qt. Re-renders read-only source each time.

Deliberately one disposable process per completed gesture: slower than live GPU,
but a driver crash cannot terminate the desktop process (08.02 regression).
"""
from __future__ import annotations
import argparse
from pathlib import Path
from ..application.navigation import CameraView
from .ply_header import inspect_ply
from .render_ply import render_ply
from .render_preview import render_fixture_png


def run(kind: str, output: Path, state: str, source: Path | None = None,
        expected_sha256: str | None = None, metadata: Path | None = None) -> None:
    view = CameraView.from_json(state)
    if kind == 'fixture':
        if source is not None or expected_sha256 is not None or metadata is not None:
            raise ValueError('Fixture request must have no PLY source')
        render_fixture_png(output, view_state=view)
    elif kind == 'ply':
        if source is None or metadata is None or expected_sha256 is None or len(expected_sha256) != 64:
            raise ValueError('Missing PLY source metadata')
        if inspect_ply(source).source_sha256 != expected_sha256:
            raise ValueError('PLY changed since last successful import')
        render_ply(source, output, metadata, view_state=view)
        if inspect_ply(source).source_sha256 != expected_sha256:
            raise ValueError('PLY changed during navigation')
    else:
        raise ValueError('Invalid scene kind')
    print('SCANTOPATH_NAV_PREVIEW_OK',flush=True)


def main() -> int:
    ap=argparse.ArgumentParser()
    ap.add_argument('--kind',choices=('fixture','ply'),required=True)
    ap.add_argument('--output',type=Path,required=True)
    ap.add_argument('--state',required=True)
    ap.add_argument('--input',type=Path)
    ap.add_argument('--expected-sha256')
    ap.add_argument('--metadata',type=Path)
    a=ap.parse_args()
    try:
        run(a.kind,a.output,a.state,a.input,a.expected_sha256,a.metadata)
    except (ValueError,OSError) as e:
        print('SCANTOPATH_NAV_REJECTED:' + ('SOURCE_CHANGED' if 'changed' in str(e) else type(e).__name__), flush=True)
        return 2
    return 0


if __name__=='__main__':
    raise SystemExit(main())
