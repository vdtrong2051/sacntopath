"""Project-owned multiview RAW and derived artifact index.

Single authority: existing v2 SQLite session and numbered storage mapping. RAW is
registered through the official persistence adapter, never rewritten in place.
An immutable B02 sequence and its derived artifacts are collocated under the
session's 02_SCAN_PIPELINE tree, with an atomic relative-path index.
"""
from __future__ import annotations

from datetime import datetime, timezone
from hashlib import sha256
import json
import os
from pathlib import Path
import sqlite3
import tempfile
from typing import Any


class ProjectLinkError(ValueError):
    pass


def _check_root(root: Path) -> Path:
    path = Path(root).absolute()
    if path.is_symlink() or not (path / 'metadata.sqlite3').is_file():
        raise ProjectLinkError('PROJECT_STORE_NOT_OPEN')
    return path.resolve(strict=True)


def session_context(root: str | Path, project_id: str, specimen_id: str, session_id: str, *, allow_closed: bool=False) -> dict:
    """Read-only ownership check; does not initialize/migrate a database."""
    path = _check_root(Path(root))
    with sqlite3.connect((path/'metadata.sqlite3').as_uri()+'?mode=ro', uri=True) as db:
        if db.execute('PRAGMA user_version').fetchone()[0] != 2:
            raise ProjectLinkError('PROJECT_SCHEMA_V2_REQUIRED')
        row = db.execute('SELECT ss.state FROM scan_sessions ss '
                         'JOIN specimens sp ON sp.specimen_id=ss.specimen_id '
                         'JOIN projects pr ON pr.project_id=sp.project_id '
                         'WHERE ss.session_id=? AND sp.specimen_id=? AND pr.project_id=?',
                         (session_id,specimen_id,project_id)).fetchone()
    if row is None or (row[0] != 'open' and not allow_closed):
        raise ProjectLinkError('PROJECT_SESSION_NOT_OPEN_OR_MISMATCH')
    return {'store_root':str(path),'project_id':project_id,
            'specimen_id':specimen_id,'session_id':session_id}


def project_pipeline_root(context: dict, *, create: bool=False) -> Path:
    """Resolve session using authoritative numbered-storage mapping."""
    from scantopath.storage.numbered import NumberedStorageRegistry
    root = _check_root(Path(context['store_root']))
    registry = NumberedStorageRegistry(root)
    place = registry.resolve_id('session', context['session_id'])
    session = root / place.relative_path
    if not session.resolve(strict=False).is_relative_to(root) or session.is_symlink():
        raise ProjectLinkError('UNSAFE_SESSION_PATH')
    pipeline = session / '02_SCAN_PIPELINE'
    if create:
        pipeline.mkdir(parents=True, exist_ok=True)
    if pipeline.is_symlink():
        raise ProjectLinkError('UNSAFE_PIPELINE_PATH')
    return pipeline


def active_ui_session(view) -> dict | None:
    """Only a selected real scan session can own newly captured multiview RAW."""
    explorer = view.project_explorer
    selection = explorer.selection
    if selection is None or selection.entity_type != 'scan_session':
        return None
    ctx = view.project_workspace.project_dashboard.panel.session_context()
    if ctx is None or ctx[3] != selection.entity_id:
        return None
    return session_context(ctx[0],ctx[1],ctx[2],ctx[3])


def selected_ui_session(view) -> dict | None:
    explorer = view.project_explorer
    selection = explorer.selection
    if selection is None or selection.entity_type != 'scan_session':
        return None
    ctx = view.project_workspace.project_dashboard.panel.session_context()
    if ctx is None or ctx[3] != selection.entity_id:
        return None
    return session_context(ctx[0],ctx[1],ctx[2],ctx[3],allow_closed=True)


def _verify_files(folder: Path) -> None:
    """Before publishing links, verify every B02/C1/C2 byte against manifest."""
    manifest=folder/'sha256_manifest.json'
    if not manifest.is_file() or manifest.is_symlink():
        raise ProjectLinkError('ARTIFACT_MANIFEST_MISSING')
    item=json.loads(manifest.read_text(encoding='utf8'))
    files=item.get('files')
    if not isinstance(files,dict) or not files:
        raise ProjectLinkError('ARTIFACT_MANIFEST_INVALID')
    for name,digest in files.items():
        if (not isinstance(name,str) or name in ('','.', '..') or '/' in name or '\\' in name
                or not isinstance(digest,str) or len(digest)!=64):
            raise ProjectLinkError('ARTIFACT_MANIFEST_INVALID')
        f=folder/name
        if f.is_symlink() or not f.is_file() or _digest(f)!=digest:
            raise ProjectLinkError('ARTIFACT_SHA256_MISMATCH '+name)


def context_for_c1(c1_folder: Path) -> dict | None:
    """Recover a C1's *true* project owner from its verified FT09 source."""
    p=Path(c1_folder).resolve(strict=True)
    _verify_files(p)
    record=json.loads((p/'processing_run.json').read_text(encoding='utf8'))
    source=record.get('input_source',{}).get('ft09_dir')
    if not source:
        return None
    context=sequence_context(Path(source))
    if context is None:
        return None
    if not p.is_relative_to(project_pipeline_root(context)):
        raise ProjectLinkError('C1_ARTIFACT_WRONG_SESSION')
    return context

def latest_raw_sequence(context: dict) -> Path:
    """Newest verified B02 sequence under the selected session, not global history."""
    folder=project_pipeline_root(context)/'00_RAW_SEQUENCES'
    if not folder.is_dir() or folder.is_symlink():
        raise ProjectLinkError('NO_SAVED_RAW_SEQUENCE')
    candidates=sorted((p for p in folder.iterdir() if p.is_dir() and p.name.startswith('b02_sequence_')),
                      key=lambda p:p.stat().st_mtime_ns,reverse=True)
    for folder in candidates:
        if folder.is_symlink():continue
        try:
            _verify_files(folder)
            if (folder/'tracking_sequence.json').is_file():
                sequence_context(folder)
                return folder
        except (ProjectLinkError,ValueError,OSError,KeyError):
            continue
    raise ProjectLinkError('NO_VERIFIED_RAW_SEQUENCE')

def sequence_context(sequence: str | Path) -> dict | None:
    """Never trust paths embedded in standalone RAW to claim arbitrary ownership."""
    folder=Path(sequence).resolve(strict=True)
    _verify_files(folder)
    record=json.loads((folder/'tracking_sequence.json').read_text(encoding='utf8'))
    item=record.get('project_context')
    if not isinstance(item,dict):
        return None
    ctx=session_context(item['store_root'],item['project_id'],item['specimen_id'],item['session_id'],allow_closed=True)
    base=project_pipeline_root(ctx)
    if not folder.is_relative_to(base/'00_RAW_SEQUENCES'):
        raise ProjectLinkError('SEQUENCE_NOT_IN_OWNED_SESSION')
    return ctx


def register_raw(context: dict, packets, progress=None) -> list[str]:
    """Register actual RAW-v2 bytes and metadata in SQLite (not just an external link)."""
    from scantopath.modules.capture.infrastructure.capture_writer import NumberedCapturePersistenceAdapter
    from scantopath.modules.capture.application.contracts import CaptureContext
    # Re-check live ownership prior to each transaction; a session may be closed
    # while camera capture is in progress. B02 RAW remains separately recoverable.
    adapter=NumberedCapturePersistenceAdapter()
    ids=[]
    for raw in packets:
        session_context(context['store_root'],context['project_id'],context['specimen_id'],context['session_id'])
        if raw.metadata.session_id!=context['session_id'] or raw.metadata.specimen_id!=context['specimen_id']:
            raise ProjectLinkError('RAW_SESSION_MISMATCH')
        c=CaptureContext(context['store_root'],context['project_id'],context['specimen_id'],
                         context['session_id'],raw.metadata.capture_id)
        ids.append(adapter.commit(c,raw))
        if progress is not None:progress(len(ids),len(packets))
    return ids


def _digest(path):
    h=sha256()
    with Path(path).open('rb') as f:
        for chunk in iter(lambda:f.read(1024*1024),b''):
            h.update(chunk)
    return h.hexdigest()


def _atomic_json(path: Path, doc: dict) -> None:
    path.parent.mkdir(parents=True,exist_ok=True)
    payload=(json.dumps(doc,ensure_ascii=False,sort_keys=True,indent=2,allow_nan=False)+'\n').encode('utf8')
    with tempfile.NamedTemporaryFile(dir=path.parent,prefix='.pipeline-',delete=False) as handle:
        temp=Path(handle.name)
        handle.write(payload);handle.flush();os.fsync(handle.fileno())
    try:os.replace(temp,path)
    finally:temp.unlink(missing_ok=True)


def record_c2(context: dict, sequence: Path, c1: Path, c2: Path) -> dict:
    """Verified C2 is the published result; no inferred metric or robot PASS."""
    from scantopath.metadata.store import MetadataStore
    from scantopath.storage.numbered import NumberedStorageRegistry
    sequence_context(sequence)
    _verify_files(c1);_verify_files(c2)
    pipeline=project_pipeline_root(context,create=True)
    for folder in (sequence,c1,c2):
        p=Path(folder).resolve(strict=True)
        if not p.is_relative_to(pipeline):
            raise ProjectLinkError('ARTIFACT_OUTSIDE_SESSION')
    c1doc=json.loads((c1/'processing_run.json').read_text(encoding='utf8'))
    c2doc=json.loads((c2/'processing_run.json').read_text(encoding='utf8'))
    if (Path(c1doc['input_source']['ft09_dir']).resolve(strict=True)!=Path(sequence).resolve(strict=True)
        or c2doc.get('input',{}).get('c1_manifest_sha256')!=_digest(c1/'sha256_manifest.json')
        or c2doc.get('input',{}).get('c1_run_id')!=c1doc.get('run_id')):
        raise ProjectLinkError('PIPELINE_LINEAGE_MISMATCH')
    ids=c1doc.get('accepted_capture_ids') or []
    if not ids:
        raise ProjectLinkError('NO_REGISTERED_C1_CAPTURES')
    with MetadataStore(context['store_root']) as db:
        for identity in ids:
            row=db.get_capture(identity,verify_raw=False)
            if row['session_id']!=context['session_id']:
                raise ProjectLinkError('C2_CAPTURE_OWNERSHIP_MISMATCH')
        run_id=c2doc['run_id']
        try:
            db.get_processing_run(run_id)
        except LookupError:
            db.create_processing_run(run_id=run_id,session_id=context['session_id'],
                stage='C2_SURFACE_TO_PATH',algorithm='VTK_SURFACE_ZIGZAG_CONTOUR',version='C2.0.0',
                input_capture_ids=list(ids),parameters={'metric_verified':False,'robot_executable':False,
                                        'mesh_faces':int(c2doc['output_mesh_faces'])})
            db.start_processing_run(run_id)
            db.finish_processing_run(run_id,state='succeeded',output_files=[str(c2)])
    NumberedStorageRegistry(context['store_root']).assign('run',c2doc['run_id'])
    index_path=pipeline/'reconstruction_index.json'
    if index_path.is_file():
        old=json.loads(index_path.read_text(encoding='utf8'))
        if old.get('schema')!='scantopath.project.pipeline_index.v1':
            raise ProjectLinkError('UNRECOGNIZED_SESSION_INDEX')
        rows=old.get('runs',[])
    else:rows=[]
    def item(path):
        p=Path(path).resolve(strict=True)
        return {'relative_path':p.relative_to(pipeline).as_posix(),
                'sha256_manifest':_digest(p/'sha256_manifest.json')}
    entry={'run_id':c2doc['run_id'],'created_utc':datetime.now(timezone.utc).isoformat(),
           'sequence':item(sequence),'c1':item(c1),'c2':item(c2),
           'input_capture_ids':list(ids),'metric_verified':False,'robot_executable':False}
    rows=[r for r in rows if r.get('run_id')!=entry['run_id']]+[entry]
    _atomic_json(index_path,{'schema':'scantopath.project.pipeline_index.v1',
             'project_id':context['project_id'],'specimen_id':context['specimen_id'],
             'session_id':context['session_id'],'runs':rows})
    return entry


def latest_result(context: dict, kind: str='c2') -> Path:
    if kind not in ('sequence','c1','c2'):
        raise ProjectLinkError('INVALID_RESULT_KIND')
    pipeline=project_pipeline_root(context)
    index=pipeline/'reconstruction_index.json'
    if not index.is_file():
        raise ProjectLinkError('NO_SAVED_PIPELINE_RESULT')
    data=json.loads(index.read_text(encoding='utf8'))
    if data.get('schema')!='scantopath.project.pipeline_index.v1' or data.get('session_id')!=context['session_id']:
        raise ProjectLinkError('SESSION_INDEX_MISMATCH')
    for row in reversed(data.get('runs',[])):
        info=row.get(kind)
        if not isinstance(info,dict):continue
        p=(pipeline/info['relative_path']).resolve(strict=True)
        if not p.is_relative_to(pipeline.resolve(strict=True)) or p.is_symlink():
            raise ProjectLinkError('UNSAFE_RESULT_REFERENCE')
        if _digest(p/'sha256_manifest.json')!=info['sha256_manifest']:
            raise ProjectLinkError('RESULT_SHA256_MISMATCH')
        return p
    raise ProjectLinkError('NO_RESULT_FOR_KIND')
