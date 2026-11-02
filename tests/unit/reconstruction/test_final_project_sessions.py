"""Final integration: owned session paths, SHA manifest verification, no silent cross-project links."""
from __future__ import annotations
from hashlib import sha256
import json
from pathlib import Path
import sqlite3
import sys
from types import ModuleType, SimpleNamespace
import pytest
from scantopath.modules.reconstruction.application import project_sessions as ps


def fixture_store(tmp_path, monkeypatch):
    root=tmp_path/'store';root.mkdir()
    db=root/'metadata.sqlite3'
    with sqlite3.connect(db) as conn:
        conn.execute('PRAGMA user_version=2')
        conn.execute('CREATE TABLE projects(project_id TEXT PRIMARY KEY)')
        conn.execute('CREATE TABLE specimens(specimen_id TEXT PRIMARY KEY,project_id TEXT)')
        conn.execute('CREATE TABLE scan_sessions(session_id TEXT PRIMARY KEY,specimen_id TEXT,state TEXT)')
        conn.execute('INSERT INTO projects VALUES("p")')
        conn.execute('INSERT INTO specimens VALUES("s","p")')
        conn.execute('INSERT INTO scan_sessions VALUES("t","s","open")')
    fake=ModuleType('scantopath.storage.numbered')
    class Registry:
        def __init__(self,root): self.root=Path(root)
        def resolve_id(self,kind,identity):
            assert kind=='session' and identity=='t'
            return SimpleNamespace(relative_path='01_PROJECTS/P0001/S0001/T0001')
    fake.NumberedStorageRegistry=Registry
    monkeypatch.setitem(sys.modules,'scantopath.storage.numbered',fake)
    ctx=ps.session_context(root,'p','s','t')
    return ctx,ps.project_pipeline_root(ctx,create=True)


def write_manifest(root, docs):
    root.mkdir(parents=True,exist_ok=True)
    hashes={}
    for name,payload in docs.items():
        (root/name).write_bytes(payload)
        hashes[name]=sha256(payload).hexdigest()
    (root/'sha256_manifest.json').write_text(json.dumps({'schema':'test','files':hashes}),encoding='utf8')


def test_session_ownership_and_raw_reopen(tmp_path,monkeypatch):
    ctx,base=fixture_store(tmp_path,monkeypatch)
    raw=base/'00_RAW_SEQUENCES'/'b02_sequence_x'
    doc={'project_context':ctx,'source_frame_count':2}
    write_manifest(raw,{'tracking_sequence.json':json.dumps(doc).encode('utf8')})
    assert ps.latest_raw_sequence(ctx)==raw
    assert ps.sequence_context(raw)==ctx
    (raw/'tracking_sequence.json').write_text('{}')
    with pytest.raises(ps.ProjectLinkError):ps.sequence_context(raw)


def test_reject_other_project_and_closed_capture(tmp_path,monkeypatch):
    ctx,base=fixture_store(tmp_path,monkeypatch)
    with pytest.raises(ps.ProjectLinkError):ps.session_context(ctx['store_root'],'another','s','t')
    db=Path(ctx['store_root'])/'metadata.sqlite3'
    with sqlite3.connect(db) as conn:
        conn.execute('UPDATE scan_sessions SET state="closed"')
    with pytest.raises(ps.ProjectLinkError):ps.session_context(ctx['store_root'],'p','s','t')
    assert ps.session_context(ctx['store_root'],'p','s','t',allow_closed=True)==ctx


def test_index_reopen_and_reject_tamper(tmp_path,monkeypatch):
    ctx,base=fixture_store(tmp_path,monkeypatch)
    result=base/'03_RECONSTRUCTION'/'C2_Results'/'c2_demo'
    write_manifest(result,{'surface_mesh.ply':b'ply\nend_header\n'})
    idx={'schema':'scantopath.project.pipeline_index.v1','session_id':'t',
         'runs':[{'run_id':'demo','c2':{'relative_path':result.relative_to(base).as_posix(),
            'sha256_manifest':sha256((result/'sha256_manifest.json').read_bytes()).hexdigest()}}]}
    ps._atomic_json(base/'reconstruction_index.json',idx)
    assert ps.latest_result(ctx)==result
    (result/'sha256_manifest.json').write_text('tampered')
    with pytest.raises(ps.ProjectLinkError):ps.latest_result(ctx)
