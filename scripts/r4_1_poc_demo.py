"""R4.1 reproducible point-scene camera sequence; writes ONE final PPM + JSON report.

Invoke from repo root using .venv Python; output paths belong in _setup evidence.
"""
from __future__ import annotations
import argparse
import hashlib
import json
from pathlib import Path
import statistics
import time

from scantopath.modules.viewer3d.infrastructure.resident_poc.client import ResidentRenderClient


def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument('--evidence-dir', type=Path, required=True)
    p.add_argument('--input', type=Path)
    p.add_argument('--events', type=int, default=24)
    args = p.parse_args()
    if not 1 <= args.events <= 200:
        raise ValueError('events must be in 1..200')
    args.evidence_dir.mkdir(parents=True, exist_ok=True)
    ply = args.input
    if ply is None:
        ply = args.evidence_dir / 'r4_1_fixture.ply'
        if not ply.exists():
            ply.write_text('ply\nformat ascii 1.0\nelement vertex 4\nproperty float x\n'
                           'property float y\nproperty float z\nend_header\n'
                           '0 0 0\n1 0 0\n0 1 0\n0 0 1\n', encoding='ascii')
    ply = ply.resolve(strict=True)
    digest = hashlib.sha256(ply.read_bytes()).hexdigest()
    durations: list[float] = []
    with ResidentRenderClient(width=400, height=300, timeout=45) as client:
        opened = client.open_ply(ply)
        pid = client.pid
        first = hashlib.sha256(client.latest_rgb()).hexdigest()
        for i in range(args.events):
            operation = ('orbit', 'pan', 'zoom')[i % 3]
            delta = (3, 0) if operation == 'zoom' else (2, 1)
            start = time.perf_counter()
            result = client.camera(operation, *delta)
            durations.append((time.perf_counter() - start) * 1000)
            if client.pid != pid or result['open_count'] != 1:
                raise RuntimeError('Host/geometry was recreated')
        frame = client.latest_rgb()
        latest = hashlib.sha256(frame).hexdigest()
        # PPM file created once at the end: no PNG-per-gesture hot path.
        ppm = args.evidence_dir / 'r4_1_last_frame.ppm'
        line = 400 * 3
        with ppm.open('wb') as f:
            f.write(b'P6\n400 300\n255\n')
            for y in reversed(range(300)):
                f.write(frame[y*line:(y+1)*line])
        status = client.request('status')
        report = {'baseline': 'R4.1', 'host_pid': pid, 'open_count': status['open_count'],
                  'events': args.events, 'scene_revision': status['scene_revision'],
                  'frame_revision': status['frame_revision'], 'frame_changed': first != latest,
                  'p50_camera_request_ms': statistics.median(durations),
                  'max_camera_request_ms': max(durations), 'sha256_source': digest,
                  'source_point_count': opened['point_count'], 'last_frame_sha256': latest,
                  'transport': 'rgb24-shm-2slot', 'limitations':
                  'CLI synchronous commands; no Qt compositor; R4.3 optimizes IPC.'}
    if hashlib.sha256(ply.read_bytes()).hexdigest() != digest:
        raise RuntimeError('Source PLY modified')
    path = args.evidence_dir / 'r4_1_demo_report.json'
    path.write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding='utf-8')
    print('R4.1 PROTOTYPE DEMO:', path, 'frames:', report['frame_revision'],
          'source unchanged; host closed')


if __name__ == '__main__':
    main()
