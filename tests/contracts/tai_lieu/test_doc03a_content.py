"""DOC-03A document contract tests; no Qt, camera or SQLite operations."""
from __future__ import annotations

from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / 'scripts'))
import check_doc03a_content as doc


def test_doc03a_eight_documents_present_and_independent():
    assert len(doc.FILES) == 8
    assert len(set(doc.FILES)) == 8
    assert len([p for p in doc.FILES if p.startswith('docs/01-tong-quan/')]) == 3
    assert len([p for p in doc.FILES if p.startswith('docs/02-kien-truc/')]) == 3
    assert all((ROOT / path).is_file() for path in doc.FILES)


def test_doc03a_no_missing_markdown_targets():
    for path in doc.FILES:
        data = (ROOT / path).read_text('utf-8')
        assert not doc.broken_links(ROOT, path, data), path


def test_doc03a_provenance_and_mandatory_technical_content():
    texts = {p: (ROOT / p).read_text(encoding='utf-8') for p in doc.FILES}
    assert doc.content_errors(texts) == []


def test_doc03a_readme_keeps_legacy_r7_gate_link():
    data = (ROOT / 'README.md').read_text('utf-8')
    assert '[Tài liệu GĐ1 hiện hành](docs/README.md)' in data
    assert 'docs/01-tong-quan/' in data
    assert 'pip install -e ".[ui,viewer,test]"' in data
    assert 'capture_once --once' not in data.split('## 5.')[1].split('## 6.')[0]


def test_doc03a_units_and_provenance_are_not_conflated():
    data = (ROOT / 'docs/02-kien-truc/DU_LIEU_VA_HE_TOA_DO.md').read_text('utf-8')
    for term in ('m/unit', 'translation_mm', 'sdk_reported_unverified',
                 'depth_optical', 'unknown', 'measured=True', 'SQLite', 'COMMITTED'):
        assert term in data


def test_doc03a_future_pipeline_not_marked_implemented():
    data = (ROOT / 'docs/01-tong-quan/PHAM_VI_VA_NANG_LUC.md').read_text('utf-8')
    assert 'NOT_IMPLEMENTED_IN_THIS_BUILD' in data
    assert 'PENDING_ACCEPTANCE' in data
    assert 'CAP-09' in data and 'CAP-12' in data


def test_doc03a_existing_source_paths_confirmed_at_baseline():
    assert set(doc.SOURCE_PATHS).issubset(doc.baseline_files(ROOT))


def test_doc03a_gate_reports_no_findings():
    r = doc.verify(ROOT)
    assert r['status'] == 'PASS', r['errors']
    assert r['docs_checked'] == 8 and r['source_paths_checked'] == len(doc.SOURCE_PATHS)
    assert r['manual_hmi'] == 'NOT_TESTED'
    assert r['hardware_decision'] == 'OPEN_REQUIRED_SOURCE_DECISION'


def test_doc03a_rejects_out_of_repo_or_missing_link(tmp_path):
    root = tmp_path / 'r'
    root.mkdir()
    (root / 'inside.md').write_text('# ok\n', encoding='utf-8')
    assert not doc.broken_links(root, 'a.md', '[ok](inside.md)')
    assert any('BROKEN_LINK' in s for s in doc.broken_links(root, 'a.md', '[missing](absent.md)'))
    assert any('LINK_ESCAPES_REPO' in s for s in doc.broken_links(root, 'a.md', '[bad](../outside.md)'))
    assert any('UNSAFE_LINK' in s for s in doc.broken_links(root, 'a.md', '[bad](C:\\outside.md)'))


def test_doc03a_gate_refuses_missing_context():
    texts = {p: ('# Title\n' + 'x'*1200) for p in doc.FILES}
    errors = doc.content_errors(texts)
    assert any(x.startswith('REQUIRED_CONTEXT_MISSING') for x in errors)
    assert any(x.startswith('COMMIT_PROVENANCE_MISSING') for x in errors)
