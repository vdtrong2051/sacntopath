"""Cổng R8.2: cấu trúc test mới và hai fixture không đổi hành vi."""
from __future__ import annotations

import csv
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0,str(ROOT/'scripts'))
from r8_2_structure_gate import verify


def test_r82_all_76_baseline_tests_preserved():
    report=verify(ROOT)
    assert report['status']=='PASS',report['errors']
    assert report['mapped_tests']==76


def test_r82_new_paths_are_separated_by_role_and_module():
    with (ROOT/'docs/99-lich-su/STANDARDIZATION/R8_2_BAN_DO_TEST.csv').open(encoding='utf-8-sig',newline='') as f:
        rows=list(csv.DictReader(f))
    assert len(rows)==76
    assert len({r['duong_dan_moi'] for r in rows})==76
    assert all(len(Path(r['duong_dan_moi']).parts)==4 for r in rows)
    assert {Path(r['duong_dan_moi']).parts[1] for r in rows}=={'unit','integration','contracts','ui','native','performance'}


def test_r82_project_and_raw_helpers_are_not_test_modules():
    from tests.support.raw_fixture import raw
    from tests.support.project_seed import _seed_v1, _seed_numbered
    assert callable(raw) and callable(_seed_v1) and callable(_seed_numbered)


def test_r82_no_stale_flat_test_entrypoints():
    assert not list((ROOT/'tests').glob('test_*.py'))


def test_r82_legacy_r35_runner_points_to_new_tree():
    s=(ROOT/'scripts/verify_gd1_r3_5.ps1').read_text(encoding='utf-8')
    assert 'tests/ui/project/test_gd1_r3_5_integrated_ux.py' in s
    assert 'tests/test_gd1_r3_5_integrated_ux.py' not in s
