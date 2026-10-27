"""R4.2 subprocess boundaries, contracts and source guard; native Qt gates run externally."""
from __future__ import annotations
import ast
import hashlib
import json
from pathlib import Path
import subprocess
import sys

import pytest

from scantopath.modules.viewer3d.infrastructure.embedded_poc.contracts import (
    ComparatorRequest, MAX_REPORT_BYTES, read_report, write_report,
)
from scantopath.modules.viewer3d.infrastructure.embedded_poc.runner import (
    NativeComparatorFailed, run_child,
)

ROOT = Path(__file__).resolve().parents[1]
EMBEDDED = ROOT / 'src/scantopath/modules/viewer3d/infrastructure/embedded_poc'
QT_HARNESS = ROOT / 'scripts/r4_2_embedded_harness.py'


def _valid():
    return {'schema': 'r4.2-comparator-v1', 'scenario': 'smoke', 'cycles_completed': 1,
            'pid': 123, 'qt_platform': 'windows', 'widget': 'QVTKRenderWindowInteractor',
            'drag_confirmed': True, 'renders': 2, 'elapsed_seconds': 0.4,
            'source_sha256': None}


def test_r42_contract_rejects_unbounded_cases():
    for scenario, cycles, events in [('foo', 1, 5), ('stress', 0, 5),
                                      ('stress', 201, 5), ('smoke', 1, 0),
                                      ('smoke', 1, 201), ('process_exit_probe', 2, 1)]:
        with pytest.raises(ValueError):
            ComparatorRequest(scenario, cycles, events, None)
    with pytest.raises(ValueError):
        ComparatorRequest('smoke', 1, 3, Path('not-a-ply.exe'))


def test_r42_report_validation_requires_real_interaction_and_cycle_count(tmp_path):
    report = tmp_path / 'receipt.json'
    write_report(report, _valid())
    assert read_report(report, 'smoke', 1)['drag_confirmed']
    for mutation in ({'drag_confirmed': False}, {'qt_platform': 'offscreen'},
                     {'cycles_completed': 0}, {'renders': 0}, {'elapsed_seconds': -1},
                     {'pid': 0}, {'widget': 'NotQVTK'}, {'schema': 'bogus'}):
        write_report(report, {**_valid(), **mutation})
        with pytest.raises(ValueError):
            read_report(report, 'smoke', 1)
    report.write_bytes(b'0' * (MAX_REPORT_BYTES + 1))
    with pytest.raises(ValueError):
        read_report(report, 'smoke', 1)


def test_r42_subprocess_probe_reports_controlled_exit_not_native_crash(tmp_path):
    report = tmp_path / 'probe.json'
    result = run_child(ComparatorRequest('process_exit_probe', 1, 1, None),
                       report, timeout=30)
    assert result['child_exit_code'] == 86 and result['parent_survived'] is True
    assert not report.exists()


def test_r42_guard_never_imports_qt_vtk_during_parent_setup():
    script = ('import sys; '
              'from scantopath.modules.viewer3d.infrastructure.embedded_poc.contracts import ComparatorRequest; '
              'from scantopath.modules.viewer3d.infrastructure.embedded_poc.runner import run_child; '
              'assert not any(name.startswith(("PySide6", "vtkmodules")) for name in sys.modules); '
              'print("ISOLATED")')
    p = subprocess.run([sys.executable, '-c', script], cwd=ROOT,
                       capture_output=True, text=True, timeout=15)
    assert p.returncode == 0, p.stderr
    assert 'ISOLATED' in p.stdout


def test_r42_no_production_import_or_database_sensors():
    harness = QT_HARNESS.read_text(encoding='utf-8')
    runner = (EMBEDDED / 'runner.py').read_text(encoding='utf-8')
    assert 'QVTKRenderWindowInteractor' in harness
    assert 'os._exit(86)' in harness
    assert 'subprocess.run' in runner
    assert 'r4_2_embedded_harness.py' in runner
    assert not (EMBEDDED / 'harness.py').exists()
    for name in ('metadata.sqlite3', 'scantopath.acquisition', 'scantopath.storage'):
        assert name not in harness
    production = (ROOT / 'src/scantopath/modules/viewer3d/presentation/controller.py').read_text(encoding='utf-8')
    assert 'embedded_poc' not in production
    tree = ast.parse((EMBEDDED / 'contracts.py').read_text(encoding='utf-8'))
    imports = [item.module for item in ast.walk(tree) if isinstance(item, ast.ImportFrom)]
    assert not any(item and item.startswith(('PySide6', 'vtkmodules')) for item in imports)


def test_r42_old_and_new_prototype_source_remain_separate():
    expected = (ROOT / 'src/scantopath/modules/viewer3d/infrastructure/resident_poc/host.py')
    assert expected.is_file()
    assert 'embedded_poc' not in expected.read_text(encoding='utf-8')
