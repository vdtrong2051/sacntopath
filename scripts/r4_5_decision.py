"""Validate historical R4.4 raw evidence, run fresh Windows telemetry, write conditional ADR receipt.

No native Qt/VTK objects are created in this supervisor; all diagnostics are isolated.
"""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import subprocess
import sys
import uuid

from r4_4_common import read_json, sha256_file, validate_report, write_json

SIZES = (1000, 100000, 1000000)
MODES = ('resident', 'embedded')
AUDIT_SIZES = (100000, 1000000)
SCRIPT = Path(__file__).resolve().parent


def load_r44(run_dir: Path) -> tuple[dict, dict[tuple[str, int], dict], str]:
    """Bind summary to its exact six raw receipts and three original fixture files."""
    if run_dir.is_symlink() or not run_dir.is_dir() or not run_dir.name.startswith('R4_4_'):
        raise ValueError('INVALID_R44_RUN_DIRECTORY')
    path = run_dir / 'SUMMARY.json'
    summary = read_json(path)
    if (summary.get('schema') != 'r4.4-run-v1' or summary.get('status') != 'MEASURED_PASS' or
            summary.get('run_id') != run_dir.name[len('R4_4_'):] or
            summary.get('sizes') != list(SIZES) or summary.get('modes') != list(MODES) or
            summary.get('samples_per_dataset') != 30):
        raise ValueError('R44_SUMMARY_NOT_FULL_ACCEPTED_RUN')
    if len(summary.get('measurements', [])) != 6 or len(summary.get('stability', [])) != 2:
        raise ValueError('R44_RESULTS_INCOMPLETE')
    if {(x.get('mode'), x.get('status')) for x in summary['stability']} != {
            ('resident', 'PASS'), ('embedded', 'PASS')}:
        raise ValueError('R44_STABILITY_NOT_PASSED')
    rows: dict[tuple[str, int], dict] = {}
    for item in summary['measurements']:
        key = (item.get('mode'), item.get('points'))
        if key in rows or key[0] not in MODES or key[1] not in SIZES or item.get('status') != 'PASS':
            raise ValueError('R44_INVALID_ROW')
        expected_raw = f'{key[0]}_{key[1]}.json'
        if item.get('report') != expected_raw or item.get('worker_exit_code') != 0:
            raise ValueError('R44_UNEXPECTED_REPORT_NAME_OR_EXIT')
        source = run_dir / f'R44_POINTS_{key[1]}.ply'
        raw = read_json(run_dir / expected_raw)
        validate_report(raw, key[0], key[1], 30)
        if raw.get('source_sha256') != sha256_file(source):
            raise ValueError('R44_GEOMETRY_HASH_CHANGED')
        for field in ('p50_ms', 'p95_ms', 'p99_ms', 'fresh_frame_rate_hz'):
            if abs(item[field] - raw[field]) > 0.02:
                raise ValueError('R44_SUMMARY_DIFFERS_FROM_RAW')
        rows[key] = item
    if set(rows) != {(m, n) for m in MODES for n in SIZES}:
        raise ValueError('R44_MISSING_A_B_COMPARISON')
    return summary, rows, sha256_file(path)


def verify_resource(raw: dict, mode: str, points: int, source_hash: str, samples: int) -> None:
    if (raw.get('schema') != 'r4.5-resource-v1' or raw.get('status') != 'OBSERVED' or
            raw.get('mode') != mode or raw.get('points') != points or
            raw.get('frames_requested') != samples or
            raw.get('source_sha256') != source_hash or
            raw.get('source_sha256_after') != source_hash or
            raw.get('proof', {}).get('frames_verified') != samples or
            raw.get('proof', {}).get('open_count') != 1):
        raise ValueError('INVALID_RESOURCE_REPORT')
    resources = raw.get('resources')
    if not isinstance(resources, dict):
        raise ValueError('INVALID_RESOURCE_DATA')
    names = ('worker', 'host') if mode == 'resident' else ('worker',)
    for name in names:
        item = resources.get(name, {})
        if (item.get('status') != 'OBSERVED' or type(item.get('samples')) is not int or
                item['samples'] < 2 or type(item.get('pid')) is not int or item['pid'] <= 0):
            raise ValueError('RESOURCE_NOT_OBSERVED')
        for field in ('max_observed_working_set_bytes', 'os_peak_working_set_bytes',
                      'max_observed_private_usage_bytes'):
            if type(item.get(field)) is not int or item[field] <= 0:
                raise ValueError('RESOURCE_INVALID_' + field)
        if item['os_peak_working_set_bytes'] < item['max_observed_working_set_bytes']:
            raise ValueError('PEAK_LOWER_THAN_CURRENT')
    if mode == 'resident' and resources['worker']['pid'] == resources['host']['pid']:
        raise ValueError('RESIDENT_HOST_NOT_ISOLATED')


def decide(rows: dict[tuple[str, int], dict]) -> dict:
    per_size = []
    for points in SIZES:
        b = rows['resident', points]
        a = rows['embedded', points]
        per_size.append({
            'points': points, 'a_p95_ms': a['p95_ms'], 'b_p95_ms': b['p95_ms'],
            'b_p95_over_a_ratio': round(b['p95_ms'] / a['p95_ms'], 4),
            'a_cold_seconds': a['cold_seconds'], 'b_cold_seconds': b['cold_seconds'],
        })
    performance_candidate = (
        rows['resident', 100000]['p95_ms'] < 200 and
        rows['resident', 1000000]['p95_ms'] < 500 and
        all(rows['resident', n]['p95_ms'] < rows['embedded', n]['p95_ms'] for n in SIZES)
    )
    return {
        'status': 'CONDITIONAL_B_FOR_R5' if performance_candidate else 'NO_PROMOTION_KEEP_FALLBACK',
        'preferred_prototype': 'resident' if performance_candidate else 'none',
        'comparison': per_size,
        'scope': 'R5 engineering direction only; not production renderer acceptance',
        'not_equivalent': 'A Qt-event-to-Render vs B IPC-to-ACKed-RGB; frame rates are not display FPS',
        'hard_gates_R5': [
            'R5.1 face-based PLY mesh and OBJ readers with provenance and picking contracts',
            'R5.2 native Qt compositor with measured pointer-to-present or accepted proxy',
            'R5.2 close while genuinely native-busy, orphan cleanup, host failure and retry',
            'R5.2 no UI-thread blocking, bounded GPU/CPU resource profile on actual Windows hardware',
            'R5.3 operator HMI interaction including model switching and Inspector',
            'R6 full Python/Qt/CTest and Windows acceptance before production promotion',
        ],
        'remaining_unknowns': [
            'No real screen presentation latency, refresh rate or VSYNC evidence',
            'No GPU/VRAM accounting', 'No native C++ crash fault injection',
            'No proof of actual close while native render blocked',
            'Resident prototype still refuses face-based PLY and OBJ',
            'Measured camera gesture paths and measurement endpoints differ',
        ],
    }


def run(run_dir: Path, evidence_dir: Path, *, frames: int = 30, timeout: int = 180) -> dict:
    if not 10 <= frames <= 120 or not 30 <= timeout <= 900:
        raise ValueError('INVALID_AUDIT_WORKLOAD')
    if evidence_dir.is_symlink():
        raise ValueError('UNSAFE_EVIDENCE_ROOT')
    summary, rows, summary_sha = load_r44(run_dir)
    evidence_dir.mkdir(parents=True, exist_ok=True)
    audit_id = datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ') + '_' + uuid.uuid4().hex[:8]
    folder = evidence_dir / ('R4_5_' + audit_id)
    folder.mkdir()
    evidence = {
        'schema': 'r4.5-decision-v1', 'status': 'INCOMPLETE', 'audit_id': audit_id,
        'r44_run_dir': str(run_dir.resolve()), 'r44_run_id': summary['run_id'],
        'r44_summary_sha256': summary_sha, 'telemetry': [], 'decision': decide(rows),
    }
    try:
        for count in AUDIT_SIZES:
            source = run_dir / f'R44_POINTS_{count}.ply'
            for mode in MODES:
                report = folder / f'{mode}_{count}_resources.json'
                command = [sys.executable, '-X', 'faulthandler', str(SCRIPT / 'r4_5_resource_child.py'),
                           '--mode', mode, '--source', str(source), '--frames', str(frames),
                           '--report', str(report)]
                try:
                    completed = subprocess.run(command, capture_output=True, timeout=timeout)
                    code, stdout, stderr = completed.returncode, completed.stdout, completed.stderr
                except subprocess.TimeoutExpired as exc:
                    code, stdout, stderr = 124, exc.stdout or b'', (exc.stderr or b'') + b'\nTIMEOUT\n'
                (folder / f'{mode}_{count}.log').write_bytes(
                    (b'EXIT=' + str(code).encode() + b'\n' + stdout[-16000:] + b'\n' + stderr[-16000:])[-32000:])
                row = {'mode': mode, 'points': count, 'exit_code': code, 'status': 'FAIL'}
                if code == 0:
                    try:
                        data = read_json(report)
                        verify_resource(data, mode, count, sha256_file(source), frames)
                        row['status'] = 'PASS'
                        row['report_sha256'] = sha256_file(report)
                        row['report'] = report.name
                        row['resources'] = data['resources']
                    except Exception as exc:
                        row['error'] = str(exc)[:200]
                evidence['telemetry'].append(row)
                print(f'R4.5 telemetry {mode} {count}: {row["status"]}', flush=True)
        if len(evidence['telemetry']) == 4 and all(r['status'] == 'PASS' for r in evidence['telemetry']):
            evidence['status'] = 'DIAGNOSTICS_PASS'
        else:
            evidence['status'] = 'DIAGNOSTICS_INCOMPLETE'
    finally:
        evidence['finished_utc'] = datetime.now(timezone.utc).isoformat()
        write_json(folder / 'DECISION_EVIDENCE.json', evidence)
        write_json(evidence_dir / 'R4_5_LATEST.json', {
            'schema': 'r4.5-index-v1', 'folder': folder.name, 'audit_id': audit_id,
            'status': evidence['status'], 'decision': evidence['decision']['status'],
        })
    print('R4.5 evidence:', folder, evidence['status'], evidence['decision']['status'], flush=True)
    return {'folder': folder, 'result': evidence}


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument('--r44-run-dir', type=Path, required=True)
    parser.add_argument('--evidence-dir', type=Path, required=True)
    parser.add_argument('--frames', type=int, default=30)
    args = parser.parse_args()
    try:
        answer = run(args.r44_run_dir, args.evidence_dir, frames=args.frames)
        return 0 if answer['result']['status'] == 'DIAGNOSTICS_PASS' else 2
    except (ValueError, OSError) as exc:
        print('R4.5 decision rejected: ' + repr(exc), file=sys.stderr, flush=True)
        return 2


if __name__ == '__main__':
    raise SystemExit(main())
