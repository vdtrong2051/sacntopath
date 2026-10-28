"""Isolated native Windows R4.5 resource diagnostic; no production Viewer changes."""
from __future__ import annotations

import argparse
import os
from pathlib import Path
import sys
import time

from r4_4_common import sha256_file, write_json
from r4_5_win_metrics import ProcessSampler


def resident_run(source: Path, frames: int) -> tuple[dict, dict]:
    from scantopath.modules.viewer3d.infrastructure.resident_poc.async_session import CoalescingRenderSession
    session = CoalescingRenderSession(640, 480, timeout=90)
    sampler = ProcessSampler({'worker': os.getpid, 'host': lambda: session.pid})
    started = time.perf_counter()
    metrics = {}
    proof = {}
    try:
        session.start().result(timeout=40)
        sampler.start()
        opened = session.open_ply(source).result(timeout=150)
        initial = session.next_frame(timeout=45)
        pid = session.pid
        if pid is None or pid == os.getpid():
            raise RuntimeError('RENDERER_PROCESS_NOT_ISOLATED')
        sampler.sample()
        last = initial.frame_revision
        for i in range(frames):
            wanted = session.camera('orbit', 1.0, 0.3 if i % 2 else -0.3)
            frame = session.next_frame(timeout=90)
            if frame.frame_revision <= last or frame.input_revision != wanted or frame.host_pid != pid:
                raise RuntimeError('STALE_OR_MISMATCHED_RESIDENT_FRAME')
            last = frame.frame_revision
            sampler.sample()
        proof = {
            'renderer_pid': pid, 'open_count': opened['open_count'],
            'frames_verified': frames, 'last_frame_revision': last,
            'duration_seconds': round(time.perf_counter() - started, 6),
        }
    finally:
        metrics = sampler.finish()
        session.stop(timeout=5)
    return proof, metrics


def embedded_run(source: Path, frames: int) -> tuple[dict, dict]:
    from r4_4_worker import _embedded
    sampler = ProcessSampler({'worker': os.getpid})
    sampler.start()
    try:
        data = _embedded(source, frames)
        if data.get('fresh_frames') != frames:
            raise RuntimeError('EMBEDDED_FRAMES_MISSING')
        proof = {'renderer_pid': os.getpid(), 'open_count': data['open_count'],
                 'frames_verified': data['fresh_frames'],
                 'duration_seconds': round(data['elapsed_seconds'], 6)}
    finally:
        metrics = sampler.finish()
    return proof, metrics


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument('--mode', choices=('resident', 'embedded'), required=True)
    parser.add_argument('--source', type=Path, required=True)
    parser.add_argument('--frames', type=int, default=30)
    parser.add_argument('--report', type=Path, required=True)
    args = parser.parse_args()
    if sys.platform != 'win32':
        raise RuntimeError('WINDOWS_NATIVE_REQUIRED')
    if args.frames < 10 or args.frames > 120 or not args.source.is_absolute() or args.source.is_symlink():
        raise ValueError('INVALID_DIAGNOSTIC_INPUT')
    if args.report.is_symlink() or args.report.resolve() == args.source.resolve():
        raise ValueError('UNSAFE_REPORT_DESTINATION')
    from scantopath.modules.viewer3d.infrastructure.ply_header import inspect_ply
    header = inspect_ply(args.source)
    digest = header.source_sha256
    if args.mode == 'resident':
        proof, metrics = resident_run(args.source, args.frames)
    else:
        proof, metrics = embedded_run(args.source, args.frames)
    if sha256_file(args.source) != digest:
        raise RuntimeError('SOURCE_MUTATED')
    expected = ('worker', 'host') if args.mode == 'resident' else ('worker',)
    if any(metrics.get(k, {}).get('status') != 'OBSERVED' or
           metrics[k]['os_peak_working_set_bytes'] <= 0 or
           metrics[k]['max_observed_private_usage_bytes'] <= 0 for k in expected):
        raise RuntimeError('TELEMETRY_INCOMPLETE')
    report = {
        'schema': 'r4.5-resource-v1', 'mode': args.mode,
        'points': header.vertex_count, 'frames_requested': args.frames,
        'source_sha256': digest, 'source_sha256_after': digest,
        'proof': proof, 'resources': metrics,
        'status': 'OBSERVED',
        'limitations': ['OS working set and private usage, not dedicated GPU/VRAM',
                        'Not a display-present latency measurement',
                        'CPU delta may be 0 at timer resolution',
                        'Memory totals across processes may include shared pages'],
    }
    write_json(args.report, report)
    print(f'R4.5 resource {args.mode} {header.vertex_count}: OBSERVED', flush=True)
    return 0


if __name__ == '__main__':
    try:
        raise SystemExit(main())
    except Exception as exc:
        print('R4.5 resource probe FAIL: ' + repr(exc), file=sys.stderr, flush=True)
        raise SystemExit(2)
