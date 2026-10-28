"""R4.4 isolated host lifecycle probes; process termination is not native crash proof."""
from __future__ import annotations
import argparse
import os
from pathlib import Path
import signal
import time

from r4_4_common import sha256_file, write_json
from scantopath.modules.viewer3d.infrastructure.resident_poc.async_session import CoalescingRenderSession
from scantopath.modules.viewer3d.infrastructure.resident_poc.client import RenderHostError


def check(path: Path, cycles: int) -> dict:
    if not path.is_absolute() or path.is_symlink() or not path.is_file() or not 1 <= cycles <= 30:
        raise ValueError('INVALID_STABILITY_INPUT')
    before = sha256_file(path)
    scene_pids: list[int] = []
    s = CoalescingRenderSession(640, 480, timeout=30)
    try:
        s.start().result(timeout=30)
        pid = s.pid
        if not pid or pid <= 0:
            raise RuntimeError('NO_HOST_PID')
        for _ in range(cycles):
            s.open_ply(path).result(timeout=30)
            frame = s.next_frame(timeout=30)
            if not frame.rgb or frame.host_pid != pid:
                raise RuntimeError('INVALID_SCENE_FRAME')
            scene_pids.append(pid)
            s.close_scene().result(timeout=30)
        if len(set(scene_pids)) != 1:
            raise RuntimeError('HOST_RESTARTED_DURING_REOPEN')
    finally:
        s.stop(timeout=5)
    if sha256_file(path) != before:
        raise RuntimeError('SOURCE_CHANGED')
    # A separate session tests bounded close immediately after dispatching load.
    busy = CoalescingRenderSession(640, 480, timeout=30)
    close_start = time.perf_counter()
    busy_pid = None
    try:
        busy.start().result(timeout=30)
        busy_pid = busy.pid
        future = busy.open_ply(path)
        busy.stop(timeout=2)
        if not future.done():
            raise RuntimeError('UNRESOLVED_BUSY_FUTURE')
    finally:
        busy.stop(timeout=2)
    busy_close_seconds = time.perf_counter() - close_start
    if busy_close_seconds > 15:
        raise RuntimeError('BUSY_CLOSE_TIMEOUT')
    if sha256_file(path) != before:
        raise RuntimeError('SOURCE_CHANGED_AFTER_BUSY_CLOSE')
    # Controlled termination of an isolated child, NOT a native segfault injection.
    crash = CoalescingRenderSession(640, 480, timeout=15)
    survivor_pid = os.getpid()
    killed_pid = None
    try:
        crash.start().result(timeout=30)
        crash.open_ply(path).result(timeout=30)
        crash.next_frame(timeout=30)
        killed_pid = crash.pid
        if not killed_pid or killed_pid == survivor_pid:
            raise RuntimeError('INVALID_CRASH_PROBE_PID')
        os.kill(killed_pid, signal.SIGTERM)
        deadline = time.monotonic() + 5
        while time.monotonic() < deadline:
            try:
                crash.camera('orbit', 1, 0)
            except RenderHostError:
                break
            time.sleep(.05)
        else:
            raise RuntimeError('HOST_TERMINATION_NOT_DETECTED')
    finally:
        crash.stop(timeout=5)
    return {'schema': 'r4.4-stability-v1', 'cycles_completed': cycles,
            'scene_pid_unchanged': len(set(scene_pids)) == 1,
            'close_while_busy_seconds': round(busy_close_seconds, 4),
            'controlled_host_termination_detected': True,
            'parent_survived': os.getpid() == survivor_pid,
            'source_unchanged': sha256_file(path) == before,
            'note': 'SIGTERM is controlled termination. NOT proof of containment of native C++ segfault.'}


def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument('--source', type=Path, required=True)
    p.add_argument('--cycles', type=int, default=20)
    p.add_argument('--report', type=Path, required=True)
    a = p.parse_args()
    result = check(a.source, a.cycles)
    write_json(a.report, result)
    print('R4.4 B stability PASS: ' + str(a.cycles) + ' reopen cycles + busy close + SIGTERM', flush=True)
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
