"""R8.4: kiểm thử runner giả lập; không mở camera, Qt hoặc CTest thật."""
from __future__ import annotations

from pathlib import Path
import json
import subprocess
import sys
import xml.etree.ElementTree as ET

import pytest

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / 'scripts'))
import r8_4_verify as r84


def test_r84_quick_has_static_gates_and_focused_tests():
    plan = r84.make_plan('Quick')
    assert 'ARCHITECTURE' in plan and 'QUALITY' in plan
    assert 'R8_1_INVENTORY' in plan and 'R8_2_STRUCTURE' in plan and 'R8_3_CONTRACTS' in plan
    assert 'PYTEST_QUICK' in plan
    assert 'CTEST_RELEASE' not in plan and 'NATIVE_R53_PROBE' not in plan


def test_r84_full_runs_all_pytest_ctest_and_junit_policy():
    plan = r84.make_plan('Full')
    assert 'PYTEST_FULL' in plan and 'JUNIT_POLICY' in plan and 'CTEST_RELEASE' in plan
    assert 'PYTEST_QUICK' not in plan


def test_r84_acceptance_has_explicit_native_opt_in_only():
    plan = r84.make_plan('Acceptance', native_probe=True, benchmark=True)
    assert plan[-2:] == ['NATIVE_R53_PROBE','R44_AB_BENCHMARK']
    assert r84.MANUAL_GATES and 'CPP_NATIVE_FAULT_ISOLATION' in r84.MANUAL_GATES
    with pytest.raises(ValueError, match='NATIVE_OPTIONS_REQUIRE_ACCEPTANCE_PROFILE'):
        r84.make_plan('Full', native_probe=True)


def test_r84_junit_summary_counts_actual_cases(tmp_path):
    root = ET.Element('testsuites')
    suite = ET.SubElement(root, 'testsuite')
    ET.SubElement(suite, 'testcase', name='test_ok')
    ET.SubElement(ET.SubElement(suite, 'testcase', name='test_skip'), 'skipped')
    ET.SubElement(ET.SubElement(suite, 'testcase', name='test_failed'), 'failure')
    path = tmp_path / 'pytest.xml'
    ET.ElementTree(root).write(path)
    assert r84.junit_summary(path) == {'cases':3,'passed':1,'failed':1,'skipped':1}
    with pytest.raises(RuntimeError, match='JUNIT_WITH_ZERO_CASES'):
        z = tmp_path / 'empty.xml'
        z.write_text('<testsuites/>')
        r84.junit_summary(z)


def test_r84_ctest_requires_nonempty_real_summary():
    assert r84.ctest_summary('100% tests passed, 0 tests failed out of 2')['passed'] == 2
    with pytest.raises(RuntimeError, match='CTEST_MISSING_SUMMARY'):
        r84.ctest_summary('ctest runner exit 0')
    with pytest.raises(RuntimeError, match='CTEST_UNEXPECTED_RESULTS'):
        r84.ctest_summary('50% tests passed, 1 tests failed out of 2')
    with pytest.raises(RuntimeError, match='CTEST_UNEXPECTED_RESULTS'):
        r84.ctest_summary('100% tests passed, 0 tests failed out of 0')


def test_r84_ctest_accepts_actual_windows_summary_without_failed_fragment():
    log = ("Test project E:/scantopath/build-orbbec\n"
           "    Start 1: core_smoke\n"
           "1/2 Test #1: core_smoke ...................   Passed    0.01 sec\n"
           "    Start 2: rgbd_contract_smoke\n"
           "2/2 Test #2: rgbd_contract_smoke .......   Passed    0.02 sec\n"
           "100% tests passed out of 2\n"
           "Total Test time (real) = 0.03 sec\n")
    assert r84.ctest_summary(log) == {'total': 2, 'passed': 2, 'failed': 0}


def test_r84_ctest_still_fails_on_incomplete_or_failing_run():
    for log in ('100% tests passed out of 0',
                '100% tests passed out of 1',
                '50% tests passed out of 2',
                '50% tests passed, 1 tests failed out of 2',
                '100% tests passed, 1 tests failed out of 2'):
        with pytest.raises(RuntimeError, match='CTEST_UNEXPECTED_RESULTS'):
            r84.ctest_summary(log)
    with pytest.raises(RuntimeError, match='CTEST_MISSING_SUMMARY'):
        r84.ctest_summary('CTest exit code 0 without summary')


def test_r84_evidence_must_stay_outside_repo(tmp_path):
    root = tmp_path / 'repo'
    root.mkdir()
    assert not r84.outside_repo(root, root)
    assert not r84.outside_repo(root, root / 'evidence')
    assert r84.outside_repo(root, tmp_path / 'setup' / 'evidence')


def _run_fake(tmp_path, monkeypatch, *, failing_step=None, profile='Quick'):
    root = tmp_path / 'repo'
    (root / 'scripts').mkdir(parents=True)
    evidence = tmp_path / 'evidence'
    monkeypatch.setattr(r84, '_preflight', lambda *a, **k:
                        {'commit':'testcommit', 'branch':'testbranch','git_dirty':False})
    monkeypatch.setattr(r84, '_step_command', lambda name, *_: ['fake',name])
    def fake_run(command, **kwargs):
        step = command[-1]
        if step in ('PYTEST_QUICK','PYTEST_FULL'):
            path = next(evidence.glob('R84_*')) / ('pytest_quick.xml' if step == 'PYTEST_QUICK' else 'pytest_full.xml')
            cases = 664 if step == 'PYTEST_FULL' else 4
            suite = ET.Element('testsuite')
            for i in range(cases):
                ET.SubElement(suite,'testcase',name=f'test_{i}')
            ET.ElementTree(suite).write(path)
        stdout = '100% tests passed, 0 tests failed out of 2' if step == 'CTEST_RELEASE' else 'fake test result'
        return subprocess.CompletedProcess(command, 13 if step == failing_step else 0, stdout, '')
    monkeypatch.setattr(r84.subprocess, 'run', fake_run)
    return r84.run(profile, root, evidence)


def test_r84_fail_closed_on_step_error(tmp_path, monkeypatch):
    code, result = _run_fake(tmp_path,monkeypatch,failing_step='QUALITY')
    assert code == 1
    assert result['automated'] == 'FAIL' and result['overall'] == 'FAIL'
    assert 'PYTEST_QUICK' not in [s['name'] for s in result['steps']]
    assert json.loads((Path(result['evidence_dir']) / 'SUMMARY.json').read_text())['automated'] == 'FAIL'


def test_r84_quick_pass_no_manual_claim(tmp_path, monkeypatch):
    code, result = _run_fake(tmp_path,monkeypatch)
    assert code == 0 and result['automated'] == 'PASS'
    assert result['overall'] == 'PASS'
    assert all(v == 'NOT_TESTED' for v in result['manual_gates'].values())
    assert result['junit']['cases'] == 4


def test_r84_acceptance_remains_pending_even_all_auto_pass(tmp_path, monkeypatch):
    code, result = _run_fake(tmp_path, monkeypatch, profile='Acceptance')
    assert code == 0 and result['automated'] == 'PASS'
    assert result['overall'] == 'PENDING_MANUAL'
    assert result['ctest']['total'] == 2
    assert result['optional']['native_r53_probe'] == 'NOT_TESTED'
