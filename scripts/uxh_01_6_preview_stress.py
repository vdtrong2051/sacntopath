"""Operator-driven bounded preview lifecycle check (no camera)."""
from __future__ import annotations
import argparse
import tempfile
from pathlib import Path
from scantopath.application.preview_scratch_leases import PreviewScratchLeases


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument('--cycles', type=int, default=50)
    args = parser.parse_args()
    if not 1 <= args.cycles <= 2000:
        parser.error('--cycles must be between 1 and 2000')
    pool = PreviewScratchLeases()
    with tempfile.TemporaryDirectory(prefix='uxh16-stress-') as top:
        for idx in range(args.cycles):
            folder = tempfile.TemporaryDirectory(prefix='preview-', dir=top)
            src = Path(folder.name) / 'frame.ply'
            src.write_bytes(b'fixture')
            pool.retain(src, folder)
            pool.release_except((src,), renderer_retired=True)
            if len(pool) != 1 or not src.exists():
                raise RuntimeError(f'LEASE_CONTRACT_FAILED cycle={idx}')
        if pool.release_all() != 0:
            raise RuntimeError('SCRATCH_LEASES_LEFT_AFTER_STOP')
        if any(Path(top).iterdir()):
            raise RuntimeError('ORPHAN_PREVIEW_FOLDERS')
    print(f'PREVIEW_LEASE_STRESS_PASS cycles={args.cycles}; remaining=0')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
