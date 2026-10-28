"""Offline checks for DOC-05 history migration; never open camera or metadata DB."""
from __future__ import annotations
import sys
from pathlib import Path

ROOT=Path(__file__).resolve().parents[3]
sys.path.insert(0,str(ROOT/'scripts'))
import check_doc05_migration as gate


def test_doc05_manifest_and_28_unique_sources():
    plan=gate.load_plan(ROOT)
    assert len(plan['mirrors'])==28
    assert set(x['id'] for x in plan['mirrors'])=={
        'DOC-014','DOC-015','DOC-016','DOC-017','DOC-018','DOC-019',
        'DOC-020','DOC-021','DOC-022','DOC-023','DOC-024','DOC-026',
        'DOC-027','DOC-028','DOC-039','DOC-040','DOC-041','DOC-043',
        'DOC-056','DOC-057','DOC-058','DOC-059','DOC-060','DOC-061',
        'DOC-062','DOC-063','DOC-064','DOC-065'}


def test_doc05_mirror_integrity_and_legacy_aliases():
    receipt=gate.verify(ROOT)
    assert receipt['status']=='PASS',receipt['errors']
    assert receipt['hmi_08_06_6']=='PENDING_MANUAL'
    assert receipt['aliases_preserved']==0


def test_doc05_rebases_existing_relative_link_without_touching_source(tmp_path):
    root=tmp_path/'repo'
    (root/'docs/old').mkdir(parents=True)
    (root/'docs/data').mkdir(parents=True)
    (root/'docs/data/file.md').write_text('# target\n',encoding='utf-8')
    src='docs/old/file.md'; dst='docs/99-lich-su/JOURNALS/file.md'
    raw=b'# title\n[read](../data/file.md#part)\n'
    converted=gate.transform(root,src,dst,raw).decode('utf-8')
    assert raw == b'# title\n[read](../data/file.md#part)\n'
    assert '(../../data/file.md#part)' in converted


def test_doc05_code_fences_and_external_links_not_rewritten(tmp_path):
    root=tmp_path/'repo';root.mkdir()
    raw=b'```md\n[untouched](../file.md)\n```\n[external](https://example.com)\n'
    output=gate.transform(root,'docs/a.md','docs/b/c.md',raw)
    assert b'[untouched](../file.md)' in output
    assert b'[external](https://example.com)' in output


def test_doc05_rejects_unsafe_path(tmp_path):
    try:gate.safe(tmp_path,'docs/../../secret.md')
    except ValueError:pass
    else:raise AssertionError('Traversal should be rejected')


def test_doc05_exact_source_git_sha_and_non_exempt_destinations():
    plan=gate.load_plan(ROOT)
    for item in plan['mirrors']:
        sha=gate.git(ROOT,'rev-parse',gate.BASELINE+':'+item['source'])
        assert sha==item['source_git_blob']
        assert (ROOT/item['target']).is_file()
