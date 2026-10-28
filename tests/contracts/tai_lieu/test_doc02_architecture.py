"""DOC-02: map/trace/template regression. No Qt, hardware or writes to user RAW."""
from __future__ import annotations

import csv
from copy import deepcopy
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / "scripts"))
import check_doc02_architecture as doc02


def _data():
    baseline = doc02.baseline_files(ROOT)
    return (doc02.read_csv(ROOT / doc02.MAP), doc02.read_csv(ROOT / doc02.TRACE),
            doc02.read_csv(ROOT / doc02.ISSUES), baseline,
            (ROOT / doc02.SPEC).read_text(encoding="utf-8"),
            (ROOT / doc02.TEMPLATE).read_text(encoding="utf-8"))


def test_doc02_all_65_baseline_documents_have_decision():
    result = doc02.verify(ROOT)
    assert result["status"] == "PASS", result["errors"]
    assert result["count"]["documents"] == 65


def test_doc02_27_content_and_16_contracts_traceable():
    result = doc02.verify(ROOT)
    assert result["count"]["contents"] == 27
    assert result["count"]["contracts"] == 16


def test_doc02_rejects_missing_document_mapping():
    m,t,i,b,s,tm = _data()
    assert 'DOC02_65_SOURCE_MAPPING_INCOMPLETE' in doc02.validate(m[:-1],t,i,b,s,tm)


def test_doc02_rejects_unsafe_destinations():
    m,t,i,b,s,tm = _data()
    m=deepcopy(m)
    m[0]['primary_target'] = '../RAW_SECRETS.md'
    assert 'DOC02_UNSAFE_DESTINATION' in doc02.validate(m,t,i,b,s,tm)


def test_doc02_enforces_redirects_and_preserves_archives():
    m,t,i,b,s,tm = _data()
    m=deepcopy(m)
    alias=next(x for x in m if x['doc02_role']=='ALIAS')
    alias['compatibility_or_preservation'] = 'DELETE_NOW'
    assert 'DOC02_ALIAS_POLICY_NOT_LOCKED' in doc02.validate(m,t,i,b,s,tm)


def test_doc02_keeps_hardware_decision_open():
    m,t,i,b,s,tm = _data()
    i=deepcopy(i)
    issue=next(x for x in i if x['issue_id']=='DOC01-07')
    issue['decision']='HARDWARE_APPROVED_WITHOUT_EVIDENCE'
    assert 'DOC02_HARDWARE_DECISION_FABRICATED' in doc02.validate(m,t,i,b,s,tm)


def test_doc02_rejects_missing_contract_and_issue():
    m,t,i,b,s,tm = _data()
    assert 'DOC02_43_TRACE_INCOMPLETE' in doc02.validate(m,t[:-1],i,b,s,tm)
    assert 'DOC02_20_ISSUES_INCOMPLETE' in doc02.validate(m,t,i[:-1],b,s,tm)


def test_doc02_evidence_location_outside_repository(tmp_path):
    root=tmp_path/'repo';root.mkdir()
    outside=tmp_path/'evidence'
    assert outside.resolve().is_relative_to(root.resolve()) is False
    assert (root/'evidence').resolve().is_relative_to(root.resolve()) is True


def test_doc02_one_owner_per_destination():
    m,t,i,b,s,tm = _data()
    m=deepcopy(m)
    dup=next(r for r in m if r['primary_target']=='docs/02-kien-truc/KIEN_TRUC_HE_THONG.md')
    dup['target_owner']='OTHER_OWNER'
    assert any(e.startswith('DOC02_MULTIPLE_OWNERS_FOR_ONE_TARGET') for e in doc02.validate(m,t,i,b,s,tm))
