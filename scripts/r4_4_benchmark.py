"""R4.4 Windows A/B supervisor; never imports Qt, VTK or runs inside production UI.

Every worker is a subprocess with bounded runtime and isolated native failures.
A benchmark FAIL cannot create a successful receipt or silently reuse old data.
"""
from __future__ import annotations
import argparse
import csv
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import subprocess
import sys
import time
import uuid

from r4_4_common import COUNTS, environment, make_point_ply, read_json, sha256_file, validate_report, write_json

SCRIPT = Path(__file__).resolve().parent


def _invoke(args: list[str], log: Path, timeout: int) -> tuple[int, float]:
    started = time.perf_counter()
    try:
        done = subprocess.run(args, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                              timeout=timeout, check=False)
        code, stdout, stderr = done.returncode, done.stdout, done.stderr
    except subprocess.TimeoutExpired as exc:
        code = 124
        stdout, stderr = exc.stdout or b'', (exc.stderr or b'') + b'\nBENCHMARK_TIMEOUT\n'
    # Do not print file paths or unlimited native driver logs to the terminal.
    log.write_bytes((b'EXIT_CODE=' + str(code).encode('ascii') + b'\nSTDOUT\n'
                     + stdout[-32768:] + b'\nSTDERR\n' + stderr[-32768:])[-65536:])
    return code, time.perf_counter() - started


def run(evidence_root: Path, *, sizes: tuple[int, ...], samples: int,
        cycles: int, modes: tuple[str, ...], timeout: int = 900) -> dict:
    if not 10 <= samples <= 300 or not 1 <= cycles <= 30:
        raise ValueError('INVALID_BENCHMARK_WORKLOAD')
    if not sizes or not set(sizes).issubset(COUNTS) or set(modes) - {'resident', 'embedded'}:
        raise ValueError('INVALID_BENCHMARK_MODE')
    if evidence_root.is_symlink():
        raise ValueError('UNSAFE_EVIDENCE_ROOT')
    evidence_root.mkdir(parents=True, exist_ok=True)
    run_id = datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ') + '_' + uuid.uuid4().hex[:8]
    folder = evidence_root / ('R4_4_' + run_id)
    folder.mkdir()
    result: dict = {'schema': 'r4.4-run-v1', 'run_id': run_id,
                    'environment': environment(), 'samples_per_dataset': samples,
                    'sizes': list(sizes), 'modes': list(modes),
                    'measurements': [], 'stability': [],
                    'unsupported_scope': {
                        'resident_ply_faces': 'DEFERRED_R5_1',
                        'resident_obj': 'DEFERRED_R5_1',
                        'native_cpp_crash_injection': 'NOT_TESTED',
                        'gpu_vram': 'NOT_MEASURED',
                        'display_present_latency': 'NOT_MEASURED',
                    }, 'status': 'INCOMPLETE'}
    try:
        sources: dict[int, Path] = {}
        for size in sizes:
            path = make_point_ply(folder, size)
            sources[size] = path
        for size in sizes:
            for mode in modes:
                output = folder / f'{mode}_{size}.json'
                log = folder / f'{mode}_{size}.log'
                cmd = [sys.executable, '-X', 'faulthandler', str(SCRIPT / 'r4_4_worker.py'),
                       '--mode', mode, '--input', str(sources[size]), '--samples', str(samples),
                       '--report', str(output)]
                code, elapsed = _invoke(cmd, log, timeout)
                row = {'mode': mode, 'points': size, 'worker_exit_code': code,
                       'wall_seconds': round(elapsed, 4), 'status': 'FAIL',
                       'report': output.name, 'log': log.name}
                if code == 0:
                    try:
                        data = read_json(output)
                        validate_report(data, mode, size, samples)
                        if data['source_sha256'] != sha256_file(sources[size]):
                            raise ValueError('SOURCE_MISMATCH_AFTER_WORKER')
                        row.update({k: data[k] for k in ('p50_ms', 'p95_ms', 'p99_ms',
                                                         'fresh_frame_rate_hz', 'cold_seconds',
                                                         'peak_renderer_rss_bytes', 'renderer_cpu_seconds')})
                        row['status'] = 'PASS'
                    except Exception as exc:
                        row['validation_error'] = str(exc)[:160]
                result['measurements'].append(row)
                print(f'R4.4 {mode} {size}: {row["status"]}', flush=True)
        if 1000 in sources and 'resident' in modes:
            output = folder / 'resident_stability.json'
            code, _ = _invoke([sys.executable, '-X', 'faulthandler',
                               str(SCRIPT / 'r4_4_stability.py'), '--source', str(sources[1000]),
                               '--cycles', str(cycles), '--report', str(output)],
                              folder / 'resident_stability.log', timeout)
            row = {'mode': 'resident', 'status': 'FAIL', 'exit_code': code}
            if code == 0:
                try:
                    data = read_json(output)
                    if (data.get('schema') == 'r4.4-stability-v1' and
                        data.get('cycles_completed') == cycles and
                        data.get('parent_survived') is True and
                        data.get('controlled_host_termination_detected') is True and
                        data.get('source_unchanged') is True and
                        data.get('scene_pid_unchanged') is True):
                        row['status'] = 'PASS'
                except Exception as exc:
                    row['validation_error'] = str(exc)[:160]
            result['stability'].append(row)
        if 1000 in sources and 'embedded' in modes:
            report = folder / 'embedded_stability.json'
            code, _ = _invoke([sys.executable, '-X', 'faulthandler',
                               str(SCRIPT / 'r4_2_embedded_comparator.py'),
                               '--scenario', 'stress', '--cycles', str(cycles), '--events', '12',
                               '--source', str(sources[1000]), '--report', str(report)],
                              folder / 'embedded_stability.log', timeout)
            row = {'mode': 'embedded', 'status': 'FAIL', 'exit_code': code}
            if code == 0:
                try:
                    from scantopath.modules.viewer3d.infrastructure.embedded_poc.contracts import read_report
                    value = read_report(report, 'stress', cycles)
                    if value.get('drag_confirmed') is True and value.get('cycles_completed') == cycles:
                        row['status'] = 'PASS'
                except Exception as exc:
                    row['validation_error'] = str(exc)[:160]
            result['stability'].append(row)
        expected_stability = len(modes) if 1000 in sources else 0
        success = (all(row['status'] == 'PASS' for row in result['measurements']) and
                   len(result['stability']) == expected_stability and
                   all(row['status'] == 'PASS' for row in result['stability']))
        # A single chosen mode may be used for exploratory/debug runs, NOT full A/B acceptance.
        result['status'] = 'MEASURED_PASS' if success else 'MEASUREMENT_FAILED'
    finally:
        result['finished_at_utc'] = datetime.now(timezone.utc).isoformat()
        write_json(folder / 'SUMMARY.json', result)
        write_json(evidence_root / 'LATEST_RUN.json', {'schema': 'r4.4-latest-v1', 'run_id': run_id, 'folder': folder.name, 'status': result['status']})
        with (folder / 'SUMMARY.csv').open('w', newline='', encoding='utf-8') as stream:
            writer = csv.DictWriter(stream, fieldnames=['mode', 'points', 'status', 'p50_ms', 'p95_ms',
                                                         'p99_ms', 'fresh_frame_rate_hz', 'cold_seconds',
                                                         'peak_renderer_rss_bytes', 'renderer_cpu_seconds', 'wall_seconds', 'log'],
                                    extrasaction='ignore')
            writer.writeheader()
            for row in result['measurements']:
                writer.writerow(row)
    print('R4.4 benchmark folder:', folder, 'status:', result['status'], flush=True)
    return {'summary': result, 'folder': folder}


def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument('--evidence-dir', type=Path, required=True)
    p.add_argument('--sizes', default='1000,100000,1000000')
    p.add_argument('--samples', type=int, default=30)
    p.add_argument('--cycles', type=int, default=20)
    p.add_argument('--modes', default='resident,embedded')
    p.add_argument('--timeout', type=int, default=900)
    a = p.parse_args()
    try:
        sizes = tuple(int(x) for x in a.sizes.split(','))
        modes = tuple(a.modes.split(','))
        if len(set(sizes)) != len(sizes) or len(set(modes)) != len(modes):
            raise ValueError('DUPLICATE_WORKLOAD')
        answer = run(a.evidence_dir, sizes=sizes, samples=a.samples,
                     cycles=a.cycles, modes=modes, timeout=a.timeout)
        return 0 if answer['summary']['status'] == 'MEASURED_PASS' else 2
    except (ValueError, OSError) as exc:
        print('R4.4 invalid arguments: ' + repr(exc), file=sys.stderr)
        return 2


if __name__ == '__main__':
    raise SystemExit(main())
