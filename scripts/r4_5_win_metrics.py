"""Windows-only process-memory audit: WS peak/current, private bytes, CPU ticks.

This is an observational diagnostic, not a GPU/VRAM or presentation monitor.
"""
from __future__ import annotations

import ctypes
import os
import sys
import threading
import time
from typing import Callable


class _Counters(ctypes.Structure):
    _fields_ = [
        ('cb', ctypes.c_ulong), ('PageFaultCount', ctypes.c_ulong),
        ('PeakWorkingSetSize', ctypes.c_size_t), ('WorkingSetSize', ctypes.c_size_t),
        ('QuotaPeakPagedPoolUsage', ctypes.c_size_t), ('QuotaPagedPoolUsage', ctypes.c_size_t),
        ('QuotaPeakNonPagedPoolUsage', ctypes.c_size_t), ('QuotaNonPagedPoolUsage', ctypes.c_size_t),
        ('PagefileUsage', ctypes.c_size_t), ('PeakPagefileUsage', ctypes.c_size_t),
        ('PrivateUsage', ctypes.c_size_t),
    ]


def windows_process_snapshot(pid: int) -> dict | None:
    """Read PROCESS_MEMORY_COUNTERS_EX for a live PID; never confuse current with peak."""
    if sys.platform != 'win32' or type(pid) is not int or pid <= 0:
        return None
    kernel = ctypes.WinDLL('kernel32', use_last_error=True)
    psapi = ctypes.WinDLL('psapi', use_last_error=True)
    kernel.OpenProcess.argtypes = (ctypes.c_ulong, ctypes.c_int, ctypes.c_ulong)
    kernel.OpenProcess.restype = ctypes.c_void_p
    kernel.CloseHandle.argtypes = (ctypes.c_void_p,)
    kernel.CloseHandle.restype = ctypes.c_int
    psapi.GetProcessMemoryInfo.argtypes = (ctypes.c_void_p, ctypes.c_void_p, ctypes.c_ulong)
    psapi.GetProcessMemoryInfo.restype = ctypes.c_int
    kernel.GetProcessTimes.argtypes = (ctypes.c_void_p,) + (ctypes.POINTER(ctypes.c_ulonglong),) * 4
    kernel.GetProcessTimes.restype = ctypes.c_int
    handle = kernel.OpenProcess(0x1000 | 0x400 | 0x10, 0, pid)
    if not handle:
        return None
    try:
        mem = _Counters()
        mem.cb = ctypes.sizeof(mem)
        if not psapi.GetProcessMemoryInfo(handle, ctypes.byref(mem), mem.cb):
            return None
        created, exited, system, user = (ctypes.c_ulonglong() for _ in range(4))
        cpu = None
        if kernel.GetProcessTimes(handle, ctypes.byref(created), ctypes.byref(exited),
                                  ctypes.byref(system), ctypes.byref(user)):
            cpu = (system.value + user.value) / 10_000_000.0
        return {
            'pid': pid,
            'working_set_bytes': int(mem.WorkingSetSize),
            'peak_working_set_bytes': int(mem.PeakWorkingSetSize),
            'private_usage_bytes': int(mem.PrivateUsage),
            'cpu_total_seconds': cpu,
        }
    finally:
        kernel.CloseHandle(handle)


class ProcessSampler:
    """Periodically observe both Qt benchmark worker and VTK host, if distinct."""

    def __init__(self, providers: dict[str, Callable[[], int | None]], interval: float = .025):
        if not .005 <= interval <= .5:
            raise ValueError('INVALID_SAMPLE_INTERVAL')
        self.providers = providers
        self.interval = interval
        self.samples: dict[str, list[dict]] = {name: [] for name in providers}
        self._lock = threading.Lock()
        self._stop = threading.Event()
        self._thread: threading.Thread | None = None

    def sample(self) -> None:
        for name, provider in self.providers.items():
            pid = provider()
            if pid is None:
                continue
            data = windows_process_snapshot(pid)
            if data is not None:
                with self._lock:
                    self.samples[name].append(data)

    def start(self) -> None:
        if self._thread is not None:
            raise RuntimeError('SAMPLER_ALREADY_STARTED')
        self.sample()
        self._thread = threading.Thread(target=self._run, daemon=True, name='R4.5-memory-audit')
        self._thread.start()

    def _run(self) -> None:
        while not self._stop.wait(self.interval):
            self.sample()

    def finish(self) -> dict:
        self._stop.set()
        if self._thread is not None:
            self._thread.join(timeout=3)
        self.sample()
        with self._lock:
            snapshots = {key: list(items) for key, items in self.samples.items()}
        result = {}
        for name, values in snapshots.items():
            if not values:
                result[name] = {'status': 'NOT_OBSERVED', 'samples': 0}
                continue
            cpu = [v['cpu_total_seconds'] for v in values if v['cpu_total_seconds'] is not None]
            pids = {v['pid'] for v in values}
            result[name] = {
                'status': 'OBSERVED' if len(pids) == 1 else 'PID_CHANGED',
                'pid': values[-1]['pid'], 'samples': len(values),
                'current_working_set_bytes_last': values[-1]['working_set_bytes'],
                'max_observed_working_set_bytes': max(v['working_set_bytes'] for v in values),
                'os_peak_working_set_bytes': max(v['peak_working_set_bytes'] for v in values),
                'max_observed_private_usage_bytes': max(v['private_usage_bytes'] for v in values),
                'cpu_delta_seconds': round(max(0.0, cpu[-1] - cpu[0]), 6) if len(cpu) >= 2 else None,
            }
        return result
