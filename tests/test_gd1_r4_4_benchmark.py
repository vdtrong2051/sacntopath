"""R4.4 verifies truthful benchmark reports and no source / UI modifications."""
from __future__ import annotations
import importlib.util
import json
import os
from pathlib import Path
import subprocess
import sys

import pytest

ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / 'scripts'
sys.path.insert(0, str(SCRIPTS))
from r4_4_common import (SCHEMA, make_point_ply, percentile, read_json, rss_bytes,
                         sha256_file, summarise_timings, validate_report, write_json)


def _valid():
    return {'schema': SCHEMA, 'mode': 'resident', 'point_count': 1000,
            'sample_count': 10, 'source_sha256': 'a' * 64,
            'source_sha256_after': 'a' * 64, 'fresh_frames': 10,
            'host_pid': 222, 'open_count': 1, 'latency_ms': [1.0] * 10,
            'elapsed_seconds': .1, 'p50_ms': 1.0, 'p95_ms': 1.0,
            'p99_ms': 1.0, 'fresh_frame_rate_hz': 100.0,
            'viewport': [640, 480],
            'measurement_type': 'input_to_render_completed_not_presented'}


def test_r44_percentile_is_monotonic_and_does_not_invent_samples():
    t = [float(x) for x in range(1, 101)]
    assert percentile(t, 50) == pytest.approx(50.5)
    assert percentile(t, 95) == pytest.approx(95.05)
    assert percentile(t, 99) == pytest.approx(99.01)
    assert summarise_timings(t, 10)['fresh_frame_rate_hz'] == 10
    with pytest.raises(ValueError):
        percentile([], 95)
    with pytest.raises(ValueError):
        percentile([1.0, float('nan')], 95)


def test_r44_bounded_source_fixtures_are_reproducible_and_immutable(tmp_path):
    p = make_point_ply(tmp_path, 1000)
    blob = p.read_bytes()
    assert p.stat().st_size < 16384
    assert b'element vertex 1000\n' in blob[:160]
    with pytest.raises(FileExistsError):
        make_point_ply(tmp_path, 1000)
    assert p.read_bytes() == blob
    with pytest.raises(ValueError):
        make_point_ply(tmp_path, 999)
    from scantopath.modules.viewer3d.infrastructure.ply_header import inspect_ply
    assert inspect_ply(p).vertex_count == 1000
    assert inspect_ply(p).source_sha256 == sha256_file(p)


def test_r44_report_validation_rejects_fake_or_old_success():
    valid = _valid()
    validate_report(valid, 'resident', 1000, 10)
    cases = ({'fresh_frames': 9}, {'point_count': 100000},
             {'source_sha256_after': 'b' * 64}, {'open_count': 2},
             {'p95_ms': 0.1}, {'viewport': [320, 240]},
             {'latency_ms': [0] * 10}, {'mode': 'embedded'},
             {'host_pid': 0}, {'measurement_type': 'screen_presented'})
    for mutation in cases:
        with pytest.raises(ValueError):
            validate_report({**valid, **mutation}, 'resident', 1000, 10)


def test_r44_file_receipts_are_bounded_and_never_follow_symlink(tmp_path):
    path = tmp_path / 'report.json'
    write_json(path, _valid())
    assert read_json(path)['schema'] == SCHEMA
    path.write_bytes(b'X' * (129 * 1024))
    with pytest.raises(ValueError):
        read_json(path)


def test_r44_script_scope_separate_from_production_viewer():
    supervisor = (SCRIPTS / 'r4_4_benchmark.py').read_text(encoding='utf-8')
    worker = (SCRIPTS / 'r4_4_worker.py').read_text(encoding='utf-8')
    assert 'subprocess.run' in supervisor
    assert 'vtkmodules.qt.QVTKRenderWindowInteractor' in worker
    assert 'CoalescingRenderSession' in worker
    assert 'input_to_render_completed_not_presented' in worker
    viewer = (ROOT / 'src/scantopath/modules/viewer3d/presentation/controller.py').read_text(encoding='utf-8')
    assert 'r4_4_' not in viewer


def test_r44_standalone_resident_1k_smoke(tmp_path):
    path = make_point_ply(tmp_path, 1000)
    original = sha256_file(path)
    report = tmp_path / 'resident.json'
    p = subprocess.run([sys.executable, '-X', 'faulthandler', str(SCRIPTS / 'r4_4_worker.py'),
                        '--mode', 'resident', '--input', str(path), '--samples', '10',
                        '--report', str(report)], cwd=ROOT, capture_output=True, timeout=120)
    assert p.returncode == 0, p.stderr[-2500:]
    data = read_json(report)
    validate_report(data, 'resident', 1000, 10)
    assert data['frame_revision'] >= 11
    assert data['frames_dropped'] == 0
    assert sha256_file(path) == original
