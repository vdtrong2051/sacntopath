"""Bounded R4.2 comparator requests and subprocess result validation."""
from __future__ import annotations
from dataclasses import dataclass
from pathlib import Path
import hashlib
import json
import math

MAX_REPORT_BYTES = 128 * 1024
SCENARIOS = frozenset({'smoke', 'stress', 'manual', 'process_exit_probe'})


@dataclass(frozen=True, slots=True)
class ComparatorRequest:
    scenario: str
    cycles: int
    events_per_cycle: int
    source: Path | None

    def __post_init__(self):
        if self.scenario not in SCENARIOS:
            raise ValueError('unknown comparator scenario')
        if type(self.cycles) is not int or not 1 <= self.cycles <= 200:
            raise ValueError('cycles must be between 1 and 200')
        if type(self.events_per_cycle) is not int or not 1 <= self.events_per_cycle <= 200:
            raise ValueError('events must be between 1 and 200')
        if self.scenario == 'process_exit_probe' and self.cycles != 1:
            raise ValueError('process exit probe is one process only')
        if self.source is not None and (not isinstance(self.source, Path) or self.source.suffix.lower() != '.ply'):
            raise ValueError('R4.2 accepts only a .ply geometry source')


def write_report(path: Path, data: dict) -> None:
    """Write a bounded, strict JSON report using replacement, never read/write source."""
    content = (json.dumps(data, ensure_ascii=True, indent=2, allow_nan=False) + '\n').encode('utf-8')
    if len(content) > MAX_REPORT_BYTES:
        raise ValueError('report too large')
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(path.name + '.part')
    temporary.write_bytes(content)
    temporary.replace(path)


def read_report(path: Path, scenario: str, expected_cycles: int) -> dict:
    if not path.is_file() or path.stat().st_size > MAX_REPORT_BYTES:
        raise ValueError('missing or oversized comparator report')
    data = json.loads(path.read_text(encoding='utf-8'))
    if type(data) is not dict or data.get('schema') != 'r4.2-comparator-v1':
        raise ValueError('invalid comparator report schema')
    if data.get('scenario') != scenario or type(data.get('cycles_completed')) is not int:
        raise ValueError('invalid comparator scenario or cycles')
    if data['cycles_completed'] != expected_cycles:
        raise ValueError('incomplete comparator cycles')
    if type(data.get('pid')) is not int or data['pid'] <= 0:
        raise ValueError('missing native Qt/VTK process ID')
    if data.get('qt_platform') in ('offscreen', 'minimal', '', None):
        raise ValueError('native Qt platform not used')
    if data.get('widget') != 'QVTKRenderWindowInteractor':
        raise ValueError('incorrect widget kind')
    if type(data.get('drag_confirmed')) is not bool or not data['drag_confirmed']:
        raise ValueError('Qt-to-VTK mouse interaction not confirmed')
    if type(data.get('renders')) is not int or data['renders'] < expected_cycles:
        raise ValueError('insufficient native render calls')
    elapsed = data.get('elapsed_seconds')
    if isinstance(elapsed, bool) or not isinstance(elapsed, (int, float)) or not math.isfinite(elapsed) or elapsed <= 0:
        raise ValueError('invalid measured time')
    if data.get('source_sha256') is not None:
        digest = data['source_sha256']
        if not isinstance(digest, str) or len(digest) != 64 or any(c not in '0123456789abcdef' for c in digest):
            raise ValueError('invalid provenance fingerprint')
    return data


def file_sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open('rb') as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b''):
            h.update(chunk)
    return h.hexdigest()
