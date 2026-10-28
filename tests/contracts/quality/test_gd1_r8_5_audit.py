"""R8.5: kiểm tra kiểm toán tĩnh, không chạy GPU, camera hoặc dữ liệu người dùng."""
from __future__ import annotations

from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT/'scripts'))
import r8_5_audit as r85


def test_r85_baseline_has_fixed_reference_counts():
    assert r85.EXPECT_TEST_FILES == 80
    assert r85.EXPECT_SCRIPT_FILES == 27
    assert r85.BASELINE == '4a2df5938d8e82a3c7790acb2a251003d9224511'


def test_r85_script_role_does_not_auto_delete_historical_probe():
    assert r85.script_category('scripts/r4_4_benchmark.py') == 'HISTORICAL_NATIVE_OR_PERFORMANCE_DIAGNOSTIC'
    assert r85.script_category('scripts/verify_gd1_r3_5.ps1') == 'LEGACY_ACCEPTANCE_COMPATIBILITY'
    assert r85.script_category('scripts/r8_5_audit.py') == 'ACTIVE_UNIFIED_GATE'


def test_r85_detects_identical_ast_as_review_not_delete():
    pair = {'tests/unit/raw/test_alpha.py':'def test_example():\n    assert 1 + 1 == 2\n',
            'tests/unit/raw/test_beta.py':'def test_other():\n    assert 1 + 1 == 2\n'}
    candidates = r85.duplicate_candidates(pair)
    assert len(candidates) == 1
    assert candidates[0]['decision'] == 'REVIEW_ONLY_NOT_DELETE'
    assert len(candidates[0]['members']) == 2


def test_r85_static_test_groups_include_all_six_layers():
    paths = ['tests/'+g+'/x/test_case.py' for g in r85.GROUPS]
    tests,scripts = r85.tests_and_scripts(paths+['scripts/verify.ps1', 'scripts/r4_4_common.py'])
    assert len(tests) == 6 and len(scripts) == 2
    assert 'scripts/verify.ps1' in scripts


def test_r85_test_name_and_source_flags_are_static():
    original = "from tests.support.project_seed import _seed_v1\n\ndef test_record():\n    assert True\n"
    assert r85.functions(original) == ['test_record']
    assert 'CROSS_TEST_IMPORT' not in r85.source_risk(original)
    bad = "from tests.ui.project.test_any import helper\n\ndef test_bad():\n    s = p.read_text()\n    assert len(s.splitlines()) < 3\n"
    assert 'CROSS_TEST_IMPORT' in r85.source_risk(bad)
    assert 'SPLITLINES_STATIC_CHECK' in r85.source_risk(bad)


def test_r85_export_rejects_repo_interior(tmp_path):
    report={'tests':[],'scripts':[],'candidates':[], 'baseline':'test',
            'baseline_test_files':80,'baseline_script_files':27,'test_files':81,
            'script_files':28,'status':'PASS','groups':{},'errors':[]}
    try:
        r85.export(report,tmp_path/'evidence',tmp_path)
    except RuntimeError as exc:
        assert str(exc) == 'EVIDENCE_MUST_BE_OUTSIDE_REPOSITORY'
    else:
        raise AssertionError('In-repo evidence must be rejected')
    r85.export(report,tmp_path.parent/'test-r85-evidence-external',tmp_path)
    assert (tmp_path.parent/'test-r85-evidence-external'/'R85_AUDIT.json').is_file()


def test_r85_real_repository_audit_preserves_baseline_tests():
    report=r85.audit(ROOT)
    assert report['status']=='PASS',report['errors']
    assert report['baseline_test_files']==80
    assert report['baseline_script_files']==27
    assert report['test_files']>=81 and report['script_files']>=28
    assert report['decision']['automatic_deletions']==0
    assert report['decision']['gd1_final_freeze']=='PENDING_08_06_6'
