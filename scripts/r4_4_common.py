"""R4.4 benchmark contracts and deterministic, read-only geometry fixtures.

No imports from Qt or VTK. These results are measurements, not metric truth.
"""
from __future__ import annotations

import ctypes
import hashlib
import json
import math
import os
from pathlib import Path
import platform
import struct
import sys
from typing import Any

SCHEMA = 'r4.4-interaction-v1'
COUNTS = (1000, 100000, 1000000)
MAX_REPORT_BYTES = 128 * 1024


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open('rb') as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b''):
            digest.update(block)
    return digest.hexdigest()


def make_point_ply(folder: Path, count: int) -> Path:
    """Stream deterministic float32 XYZ, bounded to the accepted PLY matrix."""
    if type(count) is not int or count not in COUNTS:
        raise ValueError('INVALID_BENCHMARK_COUNT')
    folder.mkdir(parents=True, exist_ok=True)
    path = folder / f'R44_POINTS_{count}.ply'
    if path.exists():
        # Never overwrite a fixture or any other previously existing file.
        raise FileExistsError(f'FIXTURE_ALREADY_EXISTS: {path}')
    header = (f'ply\nformat binary_little_endian 1.0\n'
              f'element vertex {count}\nproperty float x\nproperty float y\n'
              f'property float z\nend_header\n').encode('ascii')
    with path.open('xb') as stream:
        stream.write(header)
        for start in range(0, count, 4096):
            end = min(start + 4096, count)
            chunk = bytearray()
            for i in range(start, end):
                # Noncoplanar, deterministic, no randomness or precision claims.
                x = (i % 997) / 97.0
                y = ((i // 997) % 997) / 97.0
                z = (i % 211) / 211.0 + (i % 13) * 0.003
                chunk.extend(struct.pack('<fff', x, y, z))
            stream.write(chunk)
    return path


def percentile(values: list[float], p: int) -> float:
    if not values or p not in (50, 95, 99):
        raise ValueError('INVALID_PERCENTILE')
    if any(not math.isfinite(v) or v < 0 for v in values):
        raise ValueError('INVALID_TIMINGS')
    ordered = sorted(values)
    position = (len(ordered) - 1) * p / 100.0
    lo, hi = math.floor(position), math.ceil(position)
    return ordered[lo] + (ordered[hi] - ordered[lo]) * (position - lo)


def summarise_timings(values: list[float], elapsed: float) -> dict[str, float]:
    if not math.isfinite(elapsed) or elapsed <= 0:
        raise ValueError('INVALID_ELAPSED')
    return {'p50_ms': round(percentile(values, 50), 3),
            'p95_ms': round(percentile(values, 95), 3),
            'p99_ms': round(percentile(values, 99), 3),
            'fresh_frame_rate_hz': round(len(values) / elapsed, 3)}


def rss_bytes(pid: int) -> int | None:
    """Return current process RSS / working set, or None if not observable."""
    if type(pid) is not int or pid <= 0:
        return None
    if sys.platform == 'win32':
        # PROCESS_QUERY_INFORMATION | PROCESS_VM_READ. 64-bit Windows Python.
        class MemoryCounters(ctypes.Structure):
            _fields_ = [('cb', ctypes.c_ulong),
                        ('PageFaultCount', ctypes.c_ulong),
                        ('PeakWorkingSetSize', ctypes.c_size_t),
                        ('WorkingSetSize', ctypes.c_size_t),
                        ('QuotaPeakPagedPoolUsage', ctypes.c_size_t),
                        ('QuotaPagedPoolUsage', ctypes.c_size_t),
                        ('QuotaPeakNonPagedPoolUsage', ctypes.c_size_t),
                        ('QuotaNonPagedPoolUsage', ctypes.c_size_t),
                        ('PagefileUsage', ctypes.c_size_t),
                        ('PeakPagefileUsage', ctypes.c_size_t)]
        try:
            kernel = ctypes.WinDLL('kernel32', use_last_error=True)
            psapi = ctypes.WinDLL('psapi', use_last_error=True)
            kernel.OpenProcess.argtypes = [ctypes.c_ulong, ctypes.c_int, ctypes.c_ulong]
            kernel.OpenProcess.restype = ctypes.c_void_p
            kernel.CloseHandle.argtypes = [ctypes.c_void_p]
            psapi.GetProcessMemoryInfo.argtypes = [ctypes.c_void_p, ctypes.c_void_p, ctypes.c_ulong]
            handle = kernel.OpenProcess(0x400 | 0x10, 0, pid)
            if not handle:
                return None
            try:
                mem = MemoryCounters()
                mem.cb = ctypes.sizeof(mem)
                if not psapi.GetProcessMemoryInfo(handle, ctypes.byref(mem), mem.cb):
                    return None
                return int(mem.WorkingSetSize)
            finally:
                kernel.CloseHandle(handle)
        except (OSError, AttributeError):
            return None
    if sys.platform.startswith('linux'):
        try:
            with open(f'/proc/{pid}/status', encoding='ascii') as stream:
                for line in stream:
                    if line.startswith('VmRSS:'):
                        return int(line.split()[1]) * 1024
        except (OSError, ValueError):
            pass
    return None


def process_cpu_seconds(pid: int) -> float | None:
    """Current user+kernel process CPU seconds; not GPU utilization."""
    if type(pid) is not int or pid <= 0:
        return None
    if sys.platform == 'win32':
        try:
            kernel = ctypes.WinDLL('kernel32', use_last_error=True)
            kernel.OpenProcess.argtypes = [ctypes.c_ulong, ctypes.c_int, ctypes.c_ulong]
            kernel.OpenProcess.restype = ctypes.c_void_p
            kernel.CloseHandle.argtypes = [ctypes.c_void_p]
            kernel.GetProcessTimes.argtypes = [ctypes.c_void_p] + [ctypes.POINTER(ctypes.c_ulonglong)] * 4
            handle = kernel.OpenProcess(0x400 | 0x10, 0, pid)
            if not handle:
                return None
            try:
                created, exited, kernel_time, user_time = (ctypes.c_ulonglong() for _ in range(4))
                ok = kernel.GetProcessTimes(handle, ctypes.byref(created), ctypes.byref(exited),
                                            ctypes.byref(kernel_time), ctypes.byref(user_time))
                return (kernel_time.value + user_time.value) / 1e7 if ok else None
            finally:
                kernel.CloseHandle(handle)
        except (OSError, AttributeError):
            return None
    if sys.platform.startswith('linux'):
        try:
            stat = Path(f'/proc/{pid}/stat').read_text(encoding='ascii').split(') ', 1)[1].split()
            return (int(stat[11]) + int(stat[12])) / os.sysconf('SC_CLK_TCK')
        except (OSError, ValueError, IndexError):
            pass
    return None


def validate_report(data: Any, mode: str, count: int, samples: int) -> None:
    """Fail closed for incomplete, fabricated or stale benchmark receipts."""
    if not isinstance(data, dict) or data.get('schema') != SCHEMA or data.get('mode') != mode:
        raise ValueError('BAD_BENCHMARK_SCHEMA')
    if data.get('point_count') != count or data.get('sample_count') != samples:
        raise ValueError('BAD_BENCHMARK_COUNTS')
    if data.get('source_sha256') != data.get('source_sha256_after'):
        raise ValueError('SOURCE_CHANGED')
    sha = data.get('source_sha256')
    if not isinstance(sha, str) or len(sha) != 64 or any(x not in '0123456789abcdef' for x in sha):
        raise ValueError('INVALID_SOURCE_FINGERPRINT')
    if data.get('fresh_frames') != samples:
        raise ValueError('NOT_ALL_FRAMES_FRESH')
    if not isinstance(data.get('host_pid'), int) or data['host_pid'] <= 0:
        raise ValueError('INVALID_PID')
    values = data.get('latency_ms')
    if not isinstance(values, list) or len(values) != samples or any(
        type(x) not in (float, int) or not math.isfinite(x) or x <= 0 for x in values):
        raise ValueError('INVALID_LATENCY_SAMPLES')
    if type(data.get('elapsed_seconds')) not in (float, int) or data['elapsed_seconds'] <= 0:
        raise ValueError('INVALID_ELAPSED')
    for field in ('p50_ms', 'p95_ms', 'p99_ms', 'fresh_frame_rate_hz'):
        if type(data.get(field)) not in (float, int) or not math.isfinite(data[field]) or data[field] <= 0:
            raise ValueError('MISSING_METRIC: ' + field)
    if not data['p50_ms'] <= data['p95_ms'] <= data['p99_ms']:
        raise ValueError('NON_MONOTONIC_PERCENTILES')
    expected = summarise_timings(values, data['elapsed_seconds'])
    if any(abs(data[key] - expected[key]) > 0.02 for key in expected):
        raise ValueError('METRICS_DO_NOT_MATCH_RAW_SAMPLES')
    if data.get('open_count') != 1:
        raise ValueError('SOURCE_NOT_RESIDENT')
    if data.get('viewport') != [640, 480]:
        raise ValueError('VIEWPORT_MISMATCH')
    if data.get('measurement_type') != 'input_to_render_completed_not_presented':
        raise ValueError('INVALID_LATENCY_SEMANTICS')


def write_json(path: Path, data: dict[str, Any]) -> None:
    raw = json.dumps(data, ensure_ascii=False, sort_keys=True, indent=2, allow_nan=False).encode('utf-8') + b'\n'
    if len(raw) > MAX_REPORT_BYTES:
        raise ValueError('REPORT_TOO_LARGE')
    if path.is_symlink() or not path.parent.is_dir():
        raise ValueError('UNSAFE_REPORT_PATH')
    # Report is generated only in the benchmark's private evidence directory.
    path.write_bytes(raw)


def read_json(path: Path) -> dict:
    if path.is_symlink() or not path.is_file() or path.stat().st_size > MAX_REPORT_BYTES:
        raise ValueError('UNSAFE_REPORT')
    data = json.loads(path.read_text(encoding='utf-8'))
    if not isinstance(data, dict):
        raise ValueError('INVALID_REPORT')
    return data


def environment() -> dict:
    return {'platform': platform.platform(), 'python': sys.version.split()[0],
            'machine': platform.machine()}
