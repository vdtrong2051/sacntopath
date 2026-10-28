"""R8.4: Một bộ chạy kiểm thử, bằng chứng fail-closed và tách nghiệm thu HMI.

Không sửa dữ liệu ScanToPath. Mọi đầu ra được ghi bên ngoài repository.
"""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import re
import subprocess
import sys
import time
import xml.etree.ElementTree as ET

SCHEMA = 'scantopath-r8-4-unified-verification-v1'
BASELINE = '5068224'
QUICK_TESTS = (
    'tests/unit/task/test_gd1_06_5_core.py',
    'tests/unit/raw/test_raw_rgbd_contract.py',
    'tests/contracts/nghiem_thu/test_gd1_07_12_acceptance_parser.py',
    'tests/contracts/nghiem_thu/test_gd1_r8_3_skip_policy.py',
    'tests/contracts/quality/test_gd1_r8_1_inventory.py',
    'tests/contracts/quality/test_gd1_r8_2_structure.py',
    'tests/contracts/quality/test_gd1_r8_3_contracts.py',
    'tests/contracts/quality/test_gd1_r8_4_runner.py',
    'tests/contracts/quality/test_gd1_r8_5_audit.py',
)
MANUAL_GATES = (
    'HMI_DPI_100_125_150',
    'HMI_REOPEN_CLOSE_REAL',
    'CPP_NATIVE_BUSY_CLOSE',
    'CPP_NATIVE_FAULT_ISOLATION',
    'GPU_VRAM_MEASURED',
    'INPUT_TO_PHYSICAL_PRESENT_LATENCY',
)


def outside_repo(root: Path, evidence: Path) -> bool:
    root, evidence = root.resolve(), evidence.resolve()
    return evidence != root and not evidence.is_relative_to(root)


def junit_summary(path: Path) -> dict:
    """Tóm tắt kết quả thực, không suy PASS từ exit-code của pytest."""
    tree = ET.parse(path)
    cases = list(tree.iter('testcase'))
    if not cases:
        raise RuntimeError('JUNIT_WITH_ZERO_CASES')
    failed = sum(any(c.find(e) is not None for e in ('failure', 'error')) for c in cases)
    skipped = sum(c.find('skipped') is not None for c in cases)
    return {'cases': len(cases), 'passed': len(cases) - failed - skipped,
            'failed': failed, 'skipped': skipped}


def ctest_summary(log: str) -> dict:
    """Validate the two supported CTest summaries, never turn failures into PASS.

    Some CTest builds omit the redundant `0 tests failed` fragment when every
    test passes. Require an explicit 100% success summary and at least 2 tests.
    """
    match = re.search(
        r'(?m)^\s*(\d+(?:\.\d+)?)%\s+tests?\s+passed'
        r'(?:,\s*(\d+)\s+tests?\s+failed)?\s+out\s+of\s+(\d+)\s*$',
        log,
    )
    if not match:
        raise RuntimeError('CTEST_MISSING_SUMMARY')
    percent = float(match.group(1))
    failed = int(match.group(2)) if match.group(2) is not None else 0
    total = int(match.group(3))
    if total < 2 or percent != 100.0 or failed:
        raise RuntimeError(f'CTEST_UNEXPECTED_RESULTS:{failed}/{total};percent={percent:g}')
    return {'total': total, 'passed': total, 'failed': 0}


def make_plan(profile: str, *, native_probe: bool = False, benchmark: bool = False) -> list[str]:
    if profile not in {'Quick', 'Full', 'Acceptance'}:
        raise ValueError('INVALID_PROFILE')
    if profile != 'Acceptance' and (native_probe or benchmark):
        raise ValueError('NATIVE_OPTIONS_REQUIRE_ACCEPTANCE_PROFILE')
    shared = ['R7_DOCS', 'R8_1_INVENTORY', 'R8_2_STRUCTURE',
              'R8_3_CONTRACTS', 'R8_5_AUDIT', 'ARCHITECTURE', 'QUALITY']
    plan = shared + (['PYTEST_QUICK'] if profile == 'Quick' else
                     ['PYTEST_FULL', 'JUNIT_POLICY', 'CTEST_RELEASE'])
    if native_probe:
        plan.append('NATIVE_R53_PROBE')
    if benchmark:
        plan.append('R44_AB_BENCHMARK')
    return plan


def _git(root: Path, *args: str) -> str:
    p = subprocess.run(['git', *args], cwd=root, capture_output=True,
                       text=True, encoding='utf-8', errors='replace', timeout=30)
    if p.returncode:
        raise RuntimeError('GIT_FAILED:' + ' '.join(args) + ':' + p.stderr[-200:])
    return p.stdout.strip()


def _preflight(root: Path, evidence: Path, profile: str,
               native_probe: bool, benchmark: bool) -> dict:
    if not root.is_dir() or not (root / 'scripts').is_dir():
        raise RuntimeError('PROJECT_ROOT_INVALID')
    if Path(_git(root, 'rev-parse', '--show-toplevel')).resolve() != root:
        raise RuntimeError('NOT_REPOSITORY_ROOT')
    if not outside_repo(root, evidence):
        raise RuntimeError('EVIDENCE_MUST_BE_OUTSIDE_REPOSITORY')
    if native_probe and os.name != 'nt':
        raise RuntimeError('NATIVE_PROBE_REQUIRES_WINDOWS')
    if benchmark and os.name != 'nt':
        raise RuntimeError('BENCHMARK_REQUIRES_WINDOWS')
    if native_probe or benchmark:
        if os.getenv('QT_QPA_PLATFORM', '').lower() in ('offscreen', 'minimal'):
            raise RuntimeError('NATIVE_REQUIRES_REAL_QT_DISPLAY')
    make_plan(profile, native_probe=native_probe, benchmark=benchmark)
    head = _git(root, 'rev-parse', 'HEAD')
    # Baseline lịch sử phải hiện diện; runner vẫn dùng được sau khi merge branch.
    ancestor = subprocess.run(['git', 'merge-base', '--is-ancestor', BASELINE, 'HEAD'],
                              cwd=root, capture_output=True, timeout=30)
    if ancestor.returncode:
        raise RuntimeError('R83_BASELINE_NOT_ANCESTOR')
    return {'commit': head, 'branch': _git(root, 'branch', '--show-current'),
            'git_dirty': bool(_git(root, 'status', '--porcelain', '--untracked-files=normal'))}


def _step_command(name: str, root: Path, run_dir: Path) -> list[str]:
    py = sys.executable
    args = {'R7_DOCS': [py, '-X', 'utf8', 'scripts/r7_docs_gate.py',
                        '--project-root', str(root), '--out-dir', str(run_dir)],
            'R8_1_INVENTORY': [py, '-X', 'utf8', 'scripts/r8_1_test_inventory.py',
                               '--project-root', str(root), '--out-dir', str(run_dir)],
            'R8_2_STRUCTURE': [py, '-X', 'utf8', 'scripts/r8_2_structure_gate.py',
                              '--project-root', str(root), '--out-dir', str(run_dir)],
            'R8_3_CONTRACTS': [py, '-X', 'utf8', 'scripts/r8_3_contracts_gate.py',
                              '--project-root', str(root), '--out-dir', str(run_dir)],
            'R8_5_AUDIT': [py, '-X', 'utf8', 'scripts/r8_5_audit.py',
                             '--project-root', str(root), '--out-dir', str(run_dir)],
            'ARCHITECTURE': [py, '-X', 'utf8', 'scripts/check_architecture_boundaries.py',
                             '--project-root', str(root)],
            'QUALITY': [py, '-X', 'utf8', 'scripts/check_07_12_quality.py',
                        '--project-root', str(root), '--out-dir', str(run_dir)],
            'PYTEST_QUICK': [py, '-X', 'utf8', '-m', 'pytest', '-q', '-rs', *QUICK_TESTS,
                             '--junitxml=' + str(run_dir / 'pytest_quick.xml')],
            'PYTEST_FULL': [py, '-X', 'utf8', '-m', 'pytest', '-q', '-rs', 'tests',
                            '--junitxml=' + str(run_dir / 'pytest_full.xml')],
            'JUNIT_POLICY': [py, '-X', 'utf8', 'scripts/check_qt_acceptance_xml.py',
                             '--junit', str(run_dir / 'pytest_full.xml')],
            'CTEST_RELEASE': ['ctest', '--test-dir', str(root / 'build-orbbec'),
                              '-C', 'Release', '--output-on-failure'],
            'NATIVE_R53_PROBE': [py, '-X', 'utf8', 'scripts/r5_3_native_probe.py',
                                 '--report', str(run_dir / 'native_r53_report.json')],
            'R44_AB_BENCHMARK': [py, '-X', 'utf8', 'scripts/r4_4_benchmark.py',
                                 '--evidence-dir', str(run_dir / 'r44_ab'),
                                 '--sizes', '1000,100000,1000000', '--samples', '30',
                                 '--cycles', '20', '--modes', 'resident,embedded'],
            }
    return args[name]


def _write_json(path: Path, value: dict) -> None:
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')


def run(profile: str, root: Path, evidence: Path, *, native_probe: bool = False,
        benchmark: bool = False) -> tuple[int, dict]:
    root = root.resolve(strict=True)
    evidence = evidence.resolve()
    info = _preflight(root, evidence, profile, native_probe, benchmark)
    plan = make_plan(profile, native_probe=native_probe, benchmark=benchmark)
    evidence.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S%fZ')
    run_dir = evidence / ('R84_' + stamp + '_' + str(os.getpid()))
    run_dir.mkdir(exist_ok=False)
    receipt = {
        'schema': SCHEMA, 'profile': profile,
        'start_utc': datetime.now(timezone.utc).isoformat(),
        'project_root': str(root), 'evidence_dir': str(run_dir),
        **info,
        'plan': plan, 'steps': [], 'junit': None, 'ctest': None,
        'optional': {'native_r53_probe': 'NOT_TESTED', 'r44_ab_benchmark': 'NOT_TESTED'},
        'manual_gates': {g: 'NOT_TESTED' for g in MANUAL_GATES},
        'automated': 'PENDING', 'overall': 'PENDING', 'errors': [],
    }
    _write_json(run_dir / 'SUMMARY.json', receipt)
    env_base = os.environ.copy()
    env_base['PYTHONUTF8'] = '1'
    for index, name in enumerate(plan, 1):
        command = _step_command(name, root, run_dir)
        env = env_base.copy()
        if name in ('NATIVE_R53_PROBE', 'R44_AB_BENCHMARK'):
            env.pop('QT_QPA_PLATFORM', None)
        else:
            env['QT_QPA_PLATFORM'] = 'offscreen'
        timeout = 240 if name in ('PYTEST_QUICK', 'NATIVE_R53_PROBE') else \
                  1200 if name in ('PYTEST_FULL', 'R44_AB_BENCHMARK') else 240
        log_path = run_dir / (f'{index:02d}_{name}.log')
        print(f'[R8.4 {profile}] {index}/{len(plan)} {name}', flush=True)
        start = time.monotonic()
        try:
            completed = subprocess.run(command, cwd=root, env=env, capture_output=True,
                                      encoding='utf-8', errors='replace', text=True,
                                      timeout=timeout, check=False)
            code = completed.returncode
            message = completed.stdout + ('\n--- STDERR ---\n' + completed.stderr if completed.stderr else '')
        except subprocess.TimeoutExpired as exc:
            code = 124
            message = f'R84_STEP_TIMEOUT after {timeout}s: {exc}'
        except OSError as exc:
            code = 127
            message = f'R84_STEP_EXEC_ERROR: {exc!r}'
        log_path.write_text(message, encoding='utf-8')
        elapsed = round(time.monotonic() - start, 3)
        step = {'name': name, 'status': 'PASS' if code == 0 else 'FAIL',
                'exit_code': code, 'elapsed_seconds': elapsed,
                'command': command, 'log': str(log_path)}
        if code == 0:
            try:
                if name.startswith('PYTEST_'):
                    junit = junit_summary(run_dir / ('pytest_quick.xml' if name == 'PYTEST_QUICK' else 'pytest_full.xml'))
                    if junit['failed'] or (name == 'PYTEST_FULL' and junit['cases'] < 663):
                        raise RuntimeError('PYTEST_JUNIT_MISMATCH_OR_INCOMPLETE')
                    receipt['junit'] = junit
                    step['junit'] = junit
                if name == 'CTEST_RELEASE':
                    receipt['ctest'] = ctest_summary(message)
                    step['ctest'] = receipt['ctest']
                if name == 'NATIVE_R53_PROBE':
                    report = json.loads((run_dir / 'native_r53_report.json').read_text('utf-8'))
                    if report.get('status') != 'PASS' or report.get('qt_platform', '').lower() in ('offscreen','minimal'):
                        raise RuntimeError('NATIVE_R53_REPORT_INVALID')
                    receipt['optional']['native_r53_probe'] = 'PASS'
                if name == 'R44_AB_BENCHMARK':
                    latest = json.loads((run_dir / 'r44_ab/LATEST_RUN.json').read_text('utf-8'))
                    if latest.get('status') != 'MEASURED_PASS':
                        raise RuntimeError('R44_BENCHMARK_REPORT_INVALID')
                    receipt['optional']['r44_ab_benchmark'] = 'MEASURED_PASS'
            except (OSError, ValueError, RuntimeError, ET.ParseError) as exc:
                step['status'] = 'FAIL'
                step['validation_error'] = str(exc)
        receipt['steps'].append(step)
        if step['status'] != 'PASS':
            receipt['errors'].append(f'{name}: {step.get("validation_error", "exit=" + str(code))}')
            receipt['automated'] = 'FAIL'
            receipt['overall'] = 'FAIL'
            break
        # Không dùng các con số pytest để tự nghiệm thu HMI thật.
        _write_json(run_dir / 'SUMMARY.json', receipt)
    else:
        receipt['automated'] = 'PASS'
        receipt['overall'] = 'PENDING_MANUAL' if profile == 'Acceptance' else 'PASS'
    receipt['finished_utc'] = datetime.now(timezone.utc).isoformat()
    _write_json(run_dir / 'SUMMARY.json', receipt)
    print('R8.4 RESULT | profile=' + profile + ' | automated=' + receipt['automated'] +
          ' | overall=' + receipt['overall'] + ' | evidence=' + str(run_dir), flush=True)
    if receipt['errors']:
        print('R8.4 ERROR:', '; '.join(receipt['errors']), flush=True)
    if profile == 'Acceptance':
        print('R8.4 ACCEPTANCE DOES NOT CERTIFY HMI/GPU/PRESENT/NATIVE-FAULT; manual gates remain NOT_TESTED.', flush=True)
    return (0 if receipt['automated'] == 'PASS' else 1), receipt


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description='ScanToPath R8.4 unified regression runner')
    p.add_argument('--project-root', type=Path, required=True)
    p.add_argument('--profile', choices=('Quick','Full','Acceptance'), default='Quick')
    p.add_argument('--evidence-dir', type=Path)
    p.add_argument('--native-probe', action='store_true')
    p.add_argument('--benchmark', action='store_true')
    args = p.parse_args(argv)
    root = args.project_root.resolve(strict=True)
    evidence = (args.evidence_dir or
                root.parent / '_setup' / 'ScanToPath_R8_Verification' / 'evidence')
    try:
        code, _ = run(args.profile, root, evidence,
                      native_probe=args.native_probe, benchmark=args.benchmark)
        return code
    except (OSError, ValueError, RuntimeError) as exc:
        print('R8.4 PREFLIGHT FAILED:', str(exc), file=sys.stderr)
        return 2


if __name__ == '__main__':
    raise SystemExit(main())
