"""Parent-side subprocess comparator; a native crash never runs inside this process."""
from __future__ import annotations
import os
from pathlib import Path
import subprocess
import sys
import time

from .contracts import ComparatorRequest, read_report


class NativeComparatorFailed(RuntimeError):
    pass


def run_child(request: ComparatorRequest, report_path: Path, *, timeout: int = 600, native: bool = True) -> dict:
    """Launch a disposable PySide6/VTK child, preserve logs, and validate native receipt."""
    if not 10 <= timeout <= 1800:
        raise ValueError('invalid subprocess timeout')
    if request.scenario == 'manual':
        timeout = max(timeout, 1800)
    if report_path.suffix.lower() != '.json' or report_path.is_symlink():
        raise ValueError('comparator output must be a non-symlink JSON file')
    if request.source is not None and report_path.resolve() == request.source.resolve():
        raise ValueError('comparator output must never overwrite source geometry')
    report_path.parent.mkdir(parents=True, exist_ok=True)
    if report_path.exists():
        report_path.unlink()  # stale success must never pass a later failed native run
    # The Qt+VTK executable is a development script, not feature infrastructure.
    # This PoC runner is source-tree-only; production packaging is deferred to R5.
    harness = Path(__file__).resolve().parents[6] / 'scripts' / 'r4_2_embedded_harness.py'
    if not harness.is_file():
        raise NativeComparatorFailed('R4.2 standalone Qt/VTK harness is missing')
    argv = [sys.executable, '-X', 'faulthandler', str(harness),
            '--scenario', request.scenario, '--cycles', str(request.cycles),
            '--events', str(request.events_per_cycle), '--report', str(report_path)]
    if request.source:
        argv.extend(('--source', str(request.source)))
    if not native:
        argv.append('--allow-offscreen')
    env = os.environ.copy()
    if native:
        env.pop('QT_QPA_PLATFORM', None)  # offscreen was set by prior Qt pytest gates
    start = time.perf_counter()
    try:
        done = subprocess.run(argv, capture_output=True, text=True, errors='backslashreplace',
                              env=env, timeout=timeout, check=False)
    except subprocess.TimeoutExpired as exc:
        raise NativeComparatorFailed('R4.2 Qt/VTK child timed out and was killed') from exc
    (report_path.parent / (report_path.stem + '.stdout.txt')).write_text(done.stdout[-32768:], encoding='utf-8')
    (report_path.parent / (report_path.stem + '.stderr.txt')).write_text(done.stderr[-32768:], encoding='utf-8')
    if request.scenario == 'process_exit_probe':
        if done.returncode == 86 and not report_path.exists():
            return {'scenario': request.scenario, 'child_exit_code': 86, 'parent_survived': True,
                    'elapsed_seconds': time.perf_counter() - start}
        raise NativeComparatorFailed(f'unexpected process exit probe code {done.returncode}')
    if done.returncode != 0:
        raise NativeComparatorFailed(f'R4.2 child failed or native-crashed: returncode={done.returncode}; inspect .stderr.txt')
    if native:
        return read_report(report_path, request.scenario, 1 if request.scenario == 'manual' else request.cycles)
    # Development-only offscreen smoke is not acceptance evidence.
    return {'non_native': True, 'report_path': str(report_path)}
