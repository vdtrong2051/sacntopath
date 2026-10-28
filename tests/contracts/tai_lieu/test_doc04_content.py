"""DOC-04 static contract tests. No app import, camera, Qt or SQLite writes."""
from __future__ import annotations

from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / 'scripts'))
import check_doc04_content as doc


def test_doc04_expected_document_set_is_unique_and_complete():
    assert len(doc.FILES) == 11 and len(set(doc.FILES)) == 11
    assert sum(p.startswith('docs/05-quan-ly/') for p in doc.FILES) == 4
    assert sum(p.startswith('docs/06-giai-doan/') for p in doc.FILES) == 3
    assert sum(p.startswith('docs/07-nghiem-thu/') for p in doc.FILES) == 4
    assert all((ROOT / p).is_file() for p in doc.FILES)


def test_doc04_task_ids_have_no_duplicates_and_critical_tasks_exist():
    body = (ROOT / doc.FILES[0]).read_text(encoding='utf-8')
    ids = doc.task_ids(body)
    assert len(ids) >= 12 and len(ids) == len(set(ids))
    for task in ('DOC-04', 'DOC-05', 'GD1-08-06-6', 'HW-CURRENT-BASELINE'):
        assert task in ids


def test_doc04_content_all_documents_explain_provenance_and_limitations():
    for path in doc.FILES:
        body = (ROOT / path).read_text(encoding='utf-8')
        assert doc.document_errors(path, body) == [], path


def test_doc04_links_resolve_and_reject_unsafe_target(tmp_path):
    for name in (*doc.FILES, doc.PORTAL, doc.HANDOVER):
        path = ROOT / name
        assert doc.markdown_link_errors(ROOT, path, path.read_text(encoding='utf-8')) == [], name
    folder = tmp_path / 'r'
    folder.mkdir()
    a = folder / 'test.md'
    assert any('BROKEN_LINK' in x for x in doc.markdown_link_errors(folder, a, '[a](absent.md)'))
    assert any('LINK_ESCAPES_REPO' in x for x in doc.markdown_link_errors(folder, a, '[a](../outside.md)'))
    assert any('UNSAFE_LINK' in x for x in doc.markdown_link_errors(folder, a, r'[a](C:\secret.md)'))


def test_doc04_detects_missing_information_and_bad_task_registry():
    assert any('MISSING_METADATA' in x for x in doc.document_errors(doc.FILES[8], '# Short\n'))
    texts = {doc.FILES[0]: '# Short\n', doc.FILES[1]: '', doc.FILES[4]: '', doc.FILES[5]: '', doc.FILES[8]: ''}
    assert any('TASK_ID_MISSING' in x for x in doc.ledger_errors(texts))


def test_doc04_mapping_and_r7_alias_compatibility():
    assert doc.mapping_errors(ROOT) == []
    assert (ROOT / 'docs/INDEX.md').is_file()
    assert (ROOT / 'docs/modules/VIEWER3D.md').is_file()
    assert 'R6_OVERALL_PENDING' in (ROOT / 'docs/04-phat-trien/TIEU_CHUAN_KY_THUAT.md').read_text('utf-8')


def test_doc04_gate_runs_and_keeps_manual_pending():
    result = doc.verify(ROOT)
    assert result['status'] == 'PASS', result['errors']
    assert result['files_checked'] == 11
    assert result['manual_hmi'] == 'NOT_TESTED'
    assert result['gd1_overall'] == 'PENDING_08_06_6'


def test_doc04_mapping_reconciles_primary_secondary_and_content_trace(tmp_path):
    import csv

    folder = tmp_path / 'docs/standardization'
    folder.mkdir(parents=True)
    task = 'docs/05-quan-ly/TASK_REGISTER.md'
    gd0 = 'docs/06-giai-doan/GD0_SOFTWARE_FOUNDATION.md'
    gd1 = 'docs/06-giai-doan/GD1_DESKTOP_VIEWER.md'
    secondary_targets = {task, gd0, gd1}
    mapping_path = folder / 'DOC02_BAN_DO_65.csv'
    headers = ('id', 'stage', 'primary_target', 'additional_destination_or_rule')
    with mapping_path.open('w', encoding='utf-8', newline='') as stream:
        writer = csv.DictWriter(stream, fieldnames=headers)
        writer.writeheader()
        writer.writerow({'id': 'DOC-004', 'stage': 'DOC-04',
                         'primary_target': 'docs/01-tong-quan/LO_TRINH_PHAT_TRIEN.md',
                         'additional_destination_or_rule': task + ' (only tasks)'})
        for i, target in enumerate(sorted(doc.EXPECTED_MAPPED_TARGETS - secondary_targets -
                                          {'docs/01-tong-quan/LO_TRINH_PHAT_TRIEN.md'}), 1):
            writer.writerow({'id': 'SIM-%02d' % i, 'stage': 'DOC-04',
                             'primary_target': target})
    trace_path = folder / 'DOC02_TRUY_VET_43.csv'
    trace_headers = ('id', 'stage', 'type', 'target_documents')
    def write_traces(gd1_included):
        with trace_path.open('w', encoding='utf-8', newline='') as stream:
            writer = csv.DictWriter(stream, fieldnames=trace_headers)
            writer.writeheader()
            writer.writerow({'id': 'CW-22', 'stage': 'DOC-04', 'type': 'CONTENT',
                             'target_documents': task})
            writer.writerow({'id': 'CW-24', 'stage': 'DOC-04', 'type': 'CONTENT',
                             'target_documents': gd0 + (';' + gd1 if gd1_included else '')})
    write_traces(True)
    assert doc.mapping_errors(tmp_path) == []
    write_traces(False)
    assert any(s.startswith('DOC02_CONTENT_TRACE_MISSING:CW-24:')
               for s in doc.mapping_errors(tmp_path))
    write_traces(True)
    # No blanket bypass: removing a real primary mapping must still fail.
    content = mapping_path.read_text(encoding='utf-8')
    one = sorted(doc.EXPECTED_MAPPED_TARGETS - secondary_targets -
                 {'docs/01-tong-quan/LO_TRINH_PHAT_TRIEN.md'})[0]
    mapping_path.write_text(content.replace(one, 'docs/EXCLUDED.md'), encoding='utf-8')
    assert any(s.startswith('DOC02_EXPECTED_PRIMARY_TARGET_ABSENT:')
               for s in doc.mapping_errors(tmp_path))
