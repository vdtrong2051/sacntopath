"""DOC-03C handbook audit: static-only, no Qt/SDK/data access."""
from __future__ import annotations

from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / 'scripts'))
import check_doc03c_content as checker


def test_doc03c_four_canonical_handbooks_and_source_baseline():
    assert len(checker.DOCS) == 4
    for name in checker.DOCS:
        body = (ROOT / 'docs/04-phat-trien' / name).read_text('utf-8')
        assert checker.doc_errors(name, body) == []
        assert checker.BASELINE in body


def test_doc03c_links_resolve_without_escaping_repo():
    for name in checker.DOCS:
        rel = 'docs/04-phat-trien/' + name
        body = (ROOT / rel).read_text('utf-8')
        assert checker.markdown_link_errors(ROOT, rel, body) == []


def test_doc03c_all_references_and_aliases_still_exist():
    for rel in checker.SOURCE_PATHS + checker.LEGACY_COMPATIBILITY:
        assert (ROOT / rel).is_file(), rel


def test_doc03c_handover_and_portal_consistent():
    report = checker.verify(ROOT)
    assert report['status'] == 'PASS', report['errors']
    assert report['docs_checked'] == 4
    assert report['manual_hmi'] == 'NOT_TESTED'
    assert report['windows_full'] == 'NOT_TESTED'


def test_doc03c_checker_rejects_missing_contracts():
    doc = '# Test\n' + 'x' * 8000
    assert any(x.startswith('MISSING_HANDBOOK_ELEMENT:') for x in
               checker.doc_errors('KIEM_THU_VA_NGHIEM_THU.md', doc))


def test_doc03c_checker_rejects_unsafe_and_missing_links(tmp_path):
    root = tmp_path / 'repo'
    page = root / 'docs/04-phat-trien/test.md'
    page.parent.mkdir(parents=True)
    assert any(x.startswith('BROKEN_LINK:') for x in
               checker.markdown_link_errors(root, 'docs/04-phat-trien/test.md', '[bad](missing.md)'))
    assert any(x.startswith('LINK_ESCAPES_REPO:') for x in
               checker.markdown_link_errors(root, 'docs/04-phat-trien/test.md', '[bad](../../../outside.md)'))
    assert any(x.startswith('UNSAFE_LINK:') for x in
               checker.markdown_link_errors(root, 'docs/04-phat-trien/test.md', '[bad](C:\\secret.md)'))
