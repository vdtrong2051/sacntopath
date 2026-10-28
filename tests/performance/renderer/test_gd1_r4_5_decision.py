"""R4.5 decision is evidence-bound and never certifies screen FPS or production safety."""
from __future__ import annotations

import copy
import json
from pathlib import Path
import sys

import pytest

ROOT = Path(__file__).resolve().parents[3]
SCRIPTS = ROOT / 'scripts'
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

from r4_4_common import make_point_ply, sha256_file, write_json
from r4_5_decision import decide, load_r44, run, verify_resource, MODES, SIZES
from r4_5_win_metrics import ProcessSampler, windows_process_snapshot


def sample_resource(mode='resident', count=100000, samples=30):
    fields = {'status': 'OBSERVED', 'pid': 12345, 'samples': 15,
              'current_working_set_bytes_last': 200_000_000,
              'max_observed_working_set_bytes': 210_000_000,
              'os_peak_working_set_bytes': 215_000_000,
              'max_observed_private_usage_bytes': 100_000_000,
              'cpu_delta_seconds': 0.03125}
    resources = {'worker': fields}
    if mode == 'resident':
        resources = {'worker': fields, 'host': {**fields, 'pid': 23456}}
    return {'schema': 'r4.5-resource-v1', 'status': 'OBSERVED', 'mode': mode,
            'points': count, 'frames_requested': samples,
            'source_sha256': 'a'*64, 'source_sha256_after': 'a'*64,
            'proof': {'frames_verified': samples, 'open_count': 1},
            'resources': resources}


def _row(mode, count):
    p95 = {1000: (2.279, 5.022), 100000: (3.794, 23.708),
           1000000: (12.414, 38.034)}[count][0 if mode == 'resident' else 1]
    return {'p95_ms': p95, 'cold_seconds': 1.0}


def test_r45_conditional_selection_not_production_certification():
    rows = {(mode, n): _row(mode, n) for n in SIZES for mode in MODES}
    decision = decide(rows)
    assert decision['status'] == 'CONDITIONAL_B_FOR_R5'
    assert decision['preferred_prototype'] == 'resident'
    assert len(decision['comparison']) == 3
    assert 'not production' in decision['scope']
    assert len(decision['remaining_unknowns']) >= 5
    rows['resident', 100000] = {**rows['resident', 100000], 'p95_ms': 240.0}
    assert decide(rows)['status'] == 'NO_PROMOTION_KEEP_FALLBACK'


@pytest.mark.parametrize('mutation', [
    {'status': 'FAIL'}, {'frames_requested': 10},
    {'source_sha256_after': 'b'*64}, {'proof': {'frames_verified': 30, 'open_count': 2}},
    {'resources': {}},
])
def test_r45_resource_report_rejects_missing_or_false_success(mutation):
    baseline = sample_resource()
    assert verify_resource(baseline, 'resident', 100000, 'a'*64, 30) is None
    with pytest.raises(ValueError):
        verify_resource({**baseline, **mutation}, 'resident', 100000, 'a'*64, 30)


def test_r45_resource_report_rejects_invalid_peak_and_same_pid():
    d = sample_resource()
    d['resources']['host']['os_peak_working_set_bytes'] = 1
    with pytest.raises(ValueError, match='PEAK_LOWER'):
        verify_resource(d, 'resident', 100000, 'a'*64, 30)
    d = sample_resource()
    d['resources']['host']['pid'] = d['resources']['worker']['pid']
    with pytest.raises(ValueError, match='NOT_ISOLATED'):
        verify_resource(d, 'resident', 100000, 'a'*64, 30)


def complete_run(tmp_path):
    folder = tmp_path / 'R4_4_20261027T055444Z_d94d04c3'
    folder.mkdir()
    rows = []
    for count in SIZES:
        source = make_point_ply(folder, count)
        digest = sha256_file(source)
        for mode in MODES:
            raw = {
                'schema': 'r4.4-interaction-v1', 'mode': mode,
                'point_count': count, 'sample_count': 30,
                'source_sha256': digest, 'source_sha256_after': digest,
                'fresh_frames': 30, 'host_pid': 999, 'open_count': 1,
                'latency_ms': [1.0]*30, 'elapsed_seconds': .1,
                'p50_ms': 1.0, 'p95_ms': 1.0, 'p99_ms': 1.0,
                'fresh_frame_rate_hz': 300.0, 'viewport': [640, 480],
                'measurement_type': 'input_to_render_completed_not_presented',
            }
            write_json(folder / f'{mode}_{count}.json', raw)
            rows.append({'mode': mode, 'points': count, 'status': 'PASS',
                         'report': f'{mode}_{count}.json', 'worker_exit_code': 0,
                         'p50_ms': 1.0, 'p95_ms': 1.0, 'p99_ms': 1.0,
                         'fresh_frame_rate_hz': 300.0, 'cold_seconds': .2})
    data = {
        'schema': 'r4.4-run-v1', 'status': 'MEASURED_PASS',
        'run_id': folder.name[len('R4_4_'):], 'sizes': list(SIZES),
        'modes': list(MODES), 'samples_per_dataset': 30,
        'measurements': rows,
        'stability': [{'mode': m, 'status': 'PASS'} for m in MODES],
    }
    write_json(folder / 'SUMMARY.json', data)
    return folder


def test_r45_binds_all_raw_reports_and_fixtures(tmp_path):
    folder = complete_run(tmp_path)
    summary, rows, digest = load_r44(folder)
    assert len(rows) == 6 and len(digest) == 64
    assert summary['run_id'] == folder.name[5:]
    (folder / 'resident_100000.json').unlink()
    with pytest.raises(ValueError):
        load_r44(folder)


def test_r45_rejects_tampering_or_fake_summary_success(tmp_path):
    folder = complete_run(tmp_path)
    summary_path = folder / 'SUMMARY.json'
    data = json.loads(summary_path.read_text('utf-8'))
    data['measurements'][0]['p95_ms'] = 99.0
    write_json(summary_path, data)
    with pytest.raises(ValueError, match='DIFFERS'):
        load_r44(folder)
    data['measurements'][0]['p95_ms'] = 1.0
    data['status'] = 'INCOMPLETE'
    write_json(summary_path, data)
    with pytest.raises(ValueError, match='NOT_FULL'):
        load_r44(folder)


def test_r45_invalid_native_probe_cannot_claim_success(monkeypatch, tmp_path):
    folder = complete_run(tmp_path)
    class Failure:
        returncode = 3
        stdout = b''
        stderr = b'NATIVE_FAILURE'
    monkeypatch.setattr('r4_5_decision.subprocess.run', lambda *args, **kwargs: Failure())
    answer = run(folder, tmp_path / 'new_evidence', frames=10)
    assert answer['result']['status'] == 'DIAGNOSTICS_INCOMPLETE'
    assert all(row['status'] == 'FAIL' for row in answer['result']['telemetry'])
    latest = json.loads((tmp_path / 'new_evidence' / 'R4_5_LATEST.json').read_text('utf-8'))
    assert latest['status'] == 'DIAGNOSTICS_INCOMPLETE'


def test_r45_supervisor_remains_qt_vtk_free_and_viewer_unchanged():
    for filename in ('r4_5_decision.py', 'r4_5_win_metrics.py'):
        assert not any(x in (SCRIPTS / filename).read_text('utf-8') for x in (
            'from PySide6', 'from vtkmodules'))
    viewer = (ROOT / 'src/scantopath/modules/viewer3d/presentation/controller.py').read_text('utf-8')
    assert 'r4_5_' not in viewer
    if sys.platform != 'win32':
        assert windows_process_snapshot(123) is None


def test_r45_sampler_rejects_invalid_interval():
    with pytest.raises(ValueError):
        ProcessSampler({'main': lambda: None}, interval=0.0)
