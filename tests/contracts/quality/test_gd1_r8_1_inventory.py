"""R8.1 — kiểm thử riêng cho công cụ kiểm kê chỉ đọc, không mở Qt/camera."""
from __future__ import annotations

import ast
import csv
from pathlib import Path
import sys

ROOT=Path(__file__).resolve().parents[3]
sys.path.insert(0,str(ROOT/'scripts'))
import r8_1_test_inventory as inv


def test_r81_catalog_has_75_tests_22_scripts_without_duplicate_paths():
    rows=inv.load_catalog(ROOT)
    assert len(rows)==97
    assert len({x['duong_dan'] for x in rows})==97
    assert sum(x['loai']=='TEST' for x in rows)==75
    assert sum(x['loai']=='SCRIPT' for x in rows)==22
    assert all(x['hop_dong_duoc_bao_ve_hoac_muc_dich'].strip() for x in rows)


def test_r81_baseline_paths_match_catalog():
    tests,scripts=inv.tracked_baseline(ROOT)
    assert len(tests)==75 and len(scripts)==22
    assert {x['duong_dan'] for x in inv.load_catalog(ROOT)}==set(tests+scripts)


def test_r81_static_test_imports_are_not_executed():
    tree=ast.parse('from scantopath.storage.session_store import SessionStore\nfrom test_gd1_07_8_integrated import _seed_v1\n')
    source,helper=inv._source_imports(tree)
    assert source==['scantopath.storage.session_store']
    assert helper==['test_gd1_07_8_integrated']


def test_r81_source_based_checks_flagged_as_candidates_only():
    source="s = p.read_text()\nassert 'LiveViewer3DController(' in s\nassert len(s.splitlines()) < 500\n"
    flags=inv._source_risk(ast.parse(source),source)
    assert 'CO_DOC_SOURCE' in flags
    assert 'CO_GIOI_HAN_SO_DONG' in flags
    assert 'CO_KIEM_TRA_CHUOI' in flags


def test_r81_scan_all_existing_files_has_no_missing_mapping():
    report=inv.scan(ROOT)
    assert report['status']=='PASS', report['errors']
    assert report['tong_tap']==97
    assert report['so_test']==75 and report['so_script']==22
    assert len(report['chi_tiet'])==97
    assert all(row['git_blob_baseline'] and len(row['git_blob_baseline'])==40 for row in report['chi_tiet'])


def test_r81_export_writes_reports_only_outside_repo(tmp_path):
    report=inv.scan(ROOT)
    inv.export(report,tmp_path,ROOT)
    assert (tmp_path/'R8_1_MA_TRAN_BO_SUNG.csv').is_file()
    assert (tmp_path/'R8_1_DU_LIEU_QUET.json').is_file()
    with (tmp_path/'R8_1_MA_TRAN_BO_SUNG.csv').open(encoding='utf-8-sig',newline='') as f:
        assert len(list(csv.DictReader(f)))==97
