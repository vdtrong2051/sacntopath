"""R4.3 strict-frame-ACK/coalescing demonstration with disposable, read-only geometry."""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import time

from scantopath.modules.viewer3d.infrastructure.resident_poc.async_session import CoalescingRenderSession


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument('--evidence-dir', type=Path, required=True)
    parser.add_argument('--events', type=int, default=100)
    args = parser.parse_args()
    if not 1 <= args.events <= 500:
        raise ValueError('events must be in 1..500')
    root = args.evidence_dir.resolve()
    root.mkdir(parents=True, exist_ok=True)
    source = root / 'r4_3_fixture.ply'
    fixture = ('ply\nformat ascii 1.0\nelement vertex 4\nproperty float x\n'
               'property float y\nproperty float z\nend_header\n'
               '0 0 0\n1 0 0\n0 1 0\n0 0 1\n').encode('ascii')
    source.write_bytes(fixture)
    baseline_sha = hashlib.sha256(source.read_bytes()).hexdigest()
    with CoalescingRenderSession(320, 240, timeout=45) as session:
        begin = time.perf_counter()
        opened = session.open_ply(source).result(timeout=45)
        first = session.next_frame(timeout=10)
        pid = session.pid
        for _ in range(args.events):
            final_revision = session.camera('orbit', 0.4, 0.1)
        deadline = time.monotonic() + 45
        while time.monotonic() < deadline:
            stats = session.statistics
            if stats['rendered_input_revision'] == final_revision:
                break
            time.sleep(.025)
        else:
            raise RuntimeError('final camera input was not rendered')
        latest = session.next_frame(timeout=10)
        stats = session.statistics
        if (latest.input_revision != final_revision or session.pid != pid
                or opened['open_count'] != 1 or latest.frame_revision != stats['frames_received']
                or hashlib.sha256(first.rgb).digest() == hashlib.sha256(latest.rgb).digest()):
            raise RuntimeError('frame provenance or resident-camera contract failed')
        report = {
            'schema': 'r4.3-transport-proof-v1', 'baseline': 'R4.3',
            'host_pid': pid, 'events_submitted': args.events,
            'latest_input_revision': latest.input_revision,
            'latest_frame_revision': latest.frame_revision,
            'scene_revision': latest.scene_revision,
            'point_count': opened['point_count'], 'geometry_open_count': opened['open_count'],
            'frames_received': stats['frames_received'], 'frames_dropped': stats['frames_dropped'],
            'camera_renders': stats['camera_renders'], 'source_sha256': baseline_sha,
            'elapsed_seconds': round(time.perf_counter() - begin, 5),
            'transport': 'rgb24-shm-2slot-strict-ack',
            'limitations': 'Standalone async PoC. No Qt live viewport or native fault-injection acceptance.',
        }
    if hashlib.sha256(source.read_bytes()).hexdigest() != baseline_sha:
        raise RuntimeError('source PLY was modified')
    out = root / 'r4_3_transport_proof.json'
    out.write_text(json.dumps(report, indent=2, ensure_ascii=True) + '\n', encoding='utf-8')
    print('R4.3 TRANSPORT PASS:', out, 'events:', args.events,
          'camera_renders:', report['camera_renders'], 'PID:', pid)
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
