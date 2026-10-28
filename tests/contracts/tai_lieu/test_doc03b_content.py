"""DOC-03B documentation checks; never opens Qt, SDK, SQLite or user RAW."""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / 'scripts'))
import check_doc03b_content as doc


def test_doc03b_exact_five_modules():
    assert set(doc.FILES) == {
        'RGBD_ACQUISITION.md', 'RAW_STORAGE.md', 'PROJECT_WORKSPACE.md',
        'DESKTOP_UI.md', 'VIEWER_3D.md',
    }
    assert all((ROOT / 'docs/03-modules' / p).is_file() for p in doc.FILES)


def test_doc03b_thirteen_substantial_chapters_and_constraints():
    for name in doc.FILES:
        body = (ROOT / 'docs/03-modules' / name).read_text(encoding='utf-8')
        assert not doc.module_errors(name, body), name


def test_doc03b_no_broken_relative_links():
    for name in doc.FILES:
        path = ROOT / 'docs/03-modules' / name
        assert doc.link_errors(ROOT, path, path.read_text(encoding='utf-8')) == []


def test_doc03b_docs_portal_points_to_canonical_modules():
    body = (ROOT / 'docs/README.md').read_text(encoding='utf-8')
    for name in doc.FILES:
        assert f'03-modules/{name}' in body
    assert 'DOC-03B' in body and 'DOC-05' in body


def test_doc03b_data_provenance_and_manual_gates_not_inflated():
    for name in ('RGBD_ACQUISITION.md', 'RAW_STORAGE.md', 'VIEWER_3D.md'):
        body = (ROOT / 'docs/03-modules'/name).read_text(encoding='utf-8')
        assert 'NOT_TESTED' in body and 'measured' in body.lower()
    viewer = (ROOT / 'docs/03-modules/VIEWER_3D.md').read_text(encoding='utf-8')
    assert 'unknown' in viewer and 'frame_revision' in viewer
    assert 'FPS' in viewer and 'ACK' in viewer


def test_doc03b_doc02_migration_map_and_src_contracts():
    result = doc.verify(ROOT)
    assert result['status'] == 'PASS', result['errors']
    assert result['modules'] == 5 and result['hmi_manual'] == 'NOT_TESTED'
    assert result['source_paths'] == len(doc.SOURCES)
    assert result['test_paths'] == len(doc.TESTS)


def test_doc03b_rejects_missing_chapter_and_unrealistic_short_text():
    txt = (ROOT / 'docs/03-modules/VIEWER_3D.md').read_text(encoding='utf-8')
    assert 'MISSING_OR_UNORDERED_13_SECTIONS' in ' '.join(doc.module_errors('VIEWER_3D.md',txt.replace('## 12.', '## 12X.')))
    assert 'INSUFFICIENT_EXPLANATION' in ' '.join(doc.module_errors('VIEWER_3D.md','# a\n'))


def test_doc03b_rejects_missing_contract_and_old_flat_test_reference():
    txt = (ROOT / 'docs/03-modules/RAW_STORAGE.md').read_text(encoding='utf-8')
    assert any('CONTRACT_NOT_EXPLAINED' in x for x in doc.module_errors('RAW_STORAGE.md',txt.replace('NumberedStorageRegistry','REMOVED_ALIAS')))
    assert any('OLD_FLAT_TEST' in x for x in doc.module_errors('RAW_STORAGE.md', txt+'\ntests/test_raw_storage.py'))


def test_doc03b_rejects_bad_links_and_escape(tmp_path):
    repo = tmp_path / 'repo'
    md = repo/'docs/03-modules/example.md'
    md.parent.mkdir(parents=True)
    assert any('BROKEN_LINK' in x for x in doc.link_errors(repo,md,'[missing](no.md)'))
    assert any('BROKEN_LINK' in x for x in doc.link_errors(repo,md,'[escape](../../../secret.md)'))
    assert any('UNSAFE_LINK' in x for x in doc.link_errors(repo,md,'[win](C:\\secret.md)'))


def test_doc03b_cli_does_not_suggest_readonly_on_new_database():
    body = (ROOT/'docs/03-modules/PROJECT_WORKSPACE.md').read_text(encoding='utf-8')
    assert 'có thể **tạo SQLite nếu root trống**' in body
    assert "--root '<EXISTING_DATA_ROOT>' list-projects" in body
