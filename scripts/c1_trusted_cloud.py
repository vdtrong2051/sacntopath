"""C1 FT12-15: verified FT09 + FT10 -> object cloud/normals/provenance/metric/pose-quality.

The C1 trusted gate is provisional geometric consistency. It is NEVER a
physical 10-mm certification. RAW and FT09/FT10 source artifacts remain immutable.
Run through FT-11 Reconstruction UI or invoke offline using --sequence --cloud --out.
"""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
from hashlib import sha256
import json
import os
from pathlib import Path
import shutil
import sys
from uuid import uuid4

import numpy as np

from scantopath.modules.reconstruction.application.c1_trusted_geometry import (
    C1Config, C1Error, filter_outliers, estimate_normals, measured_voxel,
    registration_check, validate_metric,
)

SCHEMA='scantopath.c1.processing.v1'
OUTPUT_FILES=('trusted_object_cloud.ply', 'normal_xyz.csv', 'object_quality.json',
              'registration_quality.json', 'metric_validation.json', 'processing_run.json')


def emit(code, **fields):
    print(json.dumps({'C1_STATUS':code,**fields}, ensure_ascii=False, sort_keys=True), flush=True)


def json_blob(obj):
    return (json.dumps(obj, ensure_ascii=False, sort_keys=True, indent=2, allow_nan=False)+'\n').encode('utf-8')


def file_hash(file):
    hash_=sha256()
    with Path(file).open('rb') as handle:
        for chunk in iter(lambda: handle.read(1024*1024), b''):
            hash_.update(chunk)
    return hash_.hexdigest()


def _safe_source(path, kind):
    p=Path(path)
    if p.is_symlink() or not p.is_dir(): raise C1Error('C1_'+kind+'_UNSAFE_OR_MISSING')
    return p.resolve(strict=True)


def _safe_output(parent, *sources):
    p=Path(parent).absolute()
    if p.is_symlink() or (hasattr(p,'is_junction') and p.is_junction()):
        raise C1Error('C1_OUTPUT_LINK_REFUSED')
    repo=Path(__file__).resolve().parents[1]
    resolved=p.resolve(strict=False)
    forbidden=[repo,*sources]
    if any(resolved==s or resolved.is_relative_to(s) for s in forbidden):
        raise C1Error('C1_OUTPUT_INSIDE_SOURCE_OR_REPO')
    p.mkdir(parents=True,exist_ok=True)
    return p.resolve(strict=True)


def _inputs(sequence,cloud):
    from b02_live_sequence import verify_artifact
    from ft10_merge_multiview import verify_output
    from scantopath.modules.reconstruction.application.multiview_accumulation import validated_trajectory
    seq=_safe_source(sequence,'FT09')
    merged=_safe_source(cloud,'FT10')
    verify_artifact(seq)
    verify_output(merged)
    track=json.loads((seq/'tracking_sequence.json').read_text(encoding='utf8'))
    accepted,skipped=validated_trajectory(track)
    report=json.loads((merged/'accumulation_report.json').read_text(encoding='utf8'))
    manifest_sha=file_hash(seq/'sha256_manifest.json')
    if (report.get('source_manifest_sha256')!=manifest_sha
            or report.get('source_tracking_record_sha256')!=file_hash(seq/'tracking_sequence.json')
            or report.get('source_frame_count')!=track['source_frame_count']
            or report.get('accepted_view_count')!=len(accepted)
            or report.get('used_source_samples')!=[int(row['sample_index']) for row in accepted]
            or report.get('world_frame')!='depth_optical_of_sample_0'
            or report.get('sensor_measured_points_only') is not True):
        raise C1Error('C1_FT09_FT10_LINEAGE_MISMATCH')
    return seq,merged,track,report,accepted,skipped


def _read_ref(reference_file):
    if reference_file is None: return None
    p=Path(reference_file)
    if p.is_symlink() or not p.is_file():raise C1Error('C1_REFERENCE_FILE_INVALID')
    record=json.loads(p.read_text(encoding='utf8'))
    return record


def _normal_csv(points,normals,origins):
    import io
    stream=io.StringIO()
    stream.write('x_m,y_m,z_m,nx,ny,nz,source_sample_index\n')
    for xyz,n,src in zip(points,normals,origins):
        stream.write(','.join(f'{float(x):.9g}' for x in (*xyz,*n))+','+str(int(src))+'\n')
    return stream.getvalue().encode('utf8')


def verify(folder):
    from scantopath.modules.viewer3d.infrastructure.ply_header import inspect_ply
    root=_safe_source(folder,'OUTPUT')
    manifest=json.loads((root/'sha256_manifest.json').read_text(encoding='utf8'))
    if manifest.get('schema')!='scantopath.c1.sha256.v1' or set(manifest.get('files',{}))!=set(OUTPUT_FILES):
        raise C1Error('C1_MANIFEST_INVALID')
    if {p.name for p in root.iterdir()}!=set(OUTPUT_FILES)|{'sha256_manifest.json'}:
        raise C1Error('C1_OUTPUT_FILESET_INVALID')
    for name,digest in manifest['files'].items():
        file=root/name
        if file.is_symlink() or not file.is_file() or file_hash(file)!=digest:
            raise C1Error('C1_OUTPUT_CORRUPT',name)
    ply=inspect_ply(root/'trusted_object_cloud.ply')
    quality=json.loads((root/'object_quality.json').read_text(encoding='utf8'))
    registration=json.loads((root/'registration_quality.json').read_text(encoding='utf8'))
    processing=json.loads((root/'processing_run.json').read_text(encoding='utf8'))
    if (ply.vertex_count!=quality['normal_statistics']['count']
            or ply.vertex_count!=processing['output_points']
            or registration['views_accepted']<2 or ply.vertex_count<50):
        raise C1Error('C1_OUTPUT_INCONSISTENT')
    # CSV cardinality and finite values are verified without loading every row into memory.
    with (root/'normal_xyz.csv').open('r',encoding='utf8') as fh:
        if fh.readline().strip()!='x_m,y_m,z_m,nx,ny,nz,source_sample_index':
            raise C1Error('C1_NORMAL_CSV_HEADER_INVALID')
        if sum(1 for _ in fh)!=ply.vertex_count:
            raise C1Error('C1_NORMAL_CSV_COUNT_INVALID')
    return {'points':int(ply.vertex_count),'accepted_views':registration['views_accepted'],
            'rejected_views':registration['views_rejected'], 'verified_files':len(OUTPUT_FILES)}


def execute(sequence,cloud,output_parent,*,reference_file=None,config=None,store_root=None):
    from b02_live_sequence import verify_artifact
    from ft10_merge_multiview import verify_output, _read_trusted_packet, _ply_bytes
    from scantopath.modules.reconstruction.application.live_pair import cloud_from_live_packet

    cfg=config or C1Config()
    seq,ft10,record,ft10_report,accepted,skipped=_inputs(sequence,cloud)
    source_sha_manifest=json.loads((seq/'sha256_manifest.json').read_text(encoding='utf8'))['files']
    reference=_read_ref(reference_file)
    if reference is not None and reference.get('source_ft09') is not None:
        if Path(reference['source_ft09']).resolve(strict=False) != seq:
            raise C1Error('C1_REFERENCE_SOURCE_MISMATCH')
    run_id=uuid4().hex
    # Precheck optional SQLite ownership. NEVER create a store automatically.
    store_session=None
    if store_root is not None:
        path=Path(store_root)
        if not (path/'metadata.sqlite3').is_file() or path.is_symlink():
            raise C1Error('C1_SQLITE_STORE_NOT_EXISTING')
        from scantopath.metadata.store import MetadataStore
        with MetadataStore(path) as db:
            session_set=set()
            for row in accepted:
                cap=db.get_capture(row['capture_id'],verify_raw=False)
                session_set.add(cap['session_id'])
            if len(session_set)!=1:raise C1Error('C1_SQLITE_SESSION_MISMATCH')
            store_session=next(iter(session_set))

    retained_points=[]; retained_origin=[]; cameras={}
    accepted_ids=[]; checks=[]; ref_cloud=None
    for row in accepted:
        i=int(row['sample_index'])
        packet=_read_trusted_packet(seq,row,source_sha_manifest)
        view=cloud_from_live_packet(packet,roi=None,min_depth_m=0.30,
                                    max_depth_m=1.20,reference_mode='charuco')
        if (view.cloud.capture_id != row['capture_id']
                or view.source_ref.get('isolation_source')!='FT-05.8_CHARUCO'
                or view.source_ref.get('isolation_status')!='CHARUCO_OBJECT_FOUND'
                or view.source_ref.get('semantic_object_identity_verified') is not False):
            raise C1Error('C1_FT058_ISOLATION_UNVERIFIED',str(i))
        transform=np.asarray(row['T_world_depth'],dtype=np.float64)
        xyz=np.asarray(view.cloud.xyz_depth_m,dtype=np.float64)
        mapped=xyz @ transform[:3,:3].T + transform[:3,3]
        if not np.isfinite(mapped).all():raise C1Error('C1_MAPPED_POINTS_INVALID',str(i))
        if ref_cloud is None:
            decision={'state':'ACCEPTED_PROVISIONAL','reason':None,
                      'overlap':None,'rmse_m':None,'pose_adjusted_by_c1':False,
                      'metric_accuracy_verified':False}
        else:
            decision=registration_check(ref_cloud,mapped,cfg)
        decision.update({'sample_index':i,'capture_id':row['capture_id'],
                         'source_pose_status':row['status'],
                         'measured_points':len(mapped),
                         'isolation_source':view.source_ref['isolation_source']})
        checks.append(decision)
        if decision['state']=='ACCEPTED_PROVISIONAL':
            retained_points.append(mapped)
            retained_origin.append(np.full(len(mapped),i,dtype=np.int32))
            cameras[i]=transform[:3,3].copy()
            accepted_ids.append(row['capture_id'])
            concat=np.concatenate(retained_points)
            origin=np.concatenate(retained_origin)
            # Quality reference = measured voxel representatives only.
            ref_cloud,_=measured_voxel(concat,origin,cfg)
        emit('VIEW_ASSESSED', sample=i, status=decision['state'],
             overlap=decision.get('overlap'), rmse_m=decision.get('rmse_m'))
    if len(accepted_ids)<2:raise C1Error('C1_INSUFFICIENT_CONSISTENT_VIEWS',str(len(accepted_ids)))
    cloud_points=np.concatenate(retained_points)
    origin_ids=np.concatenate(retained_origin)
    voxel,origins=measured_voxel(cloud_points,origin_ids,cfg)
    cleaned,clean_origin,outlier_report=filter_outliers(voxel,origins,cfg)
    normals,normal_report=estimate_normals(cleaned,clean_origin,cameras,cfg)
    metric=validate_metric(cleaned,reference)
    registration={
        'schema':'scantopath.c1.registration.v1','kind':'FT09_POSE_CANDIDATE_INDEPENDENT_GEOMETRIC_RECHECK',
        'source_accepted':len(accepted), 'source_skipped':skipped,
        'views_accepted':len(accepted_ids),
        'views_rejected':len(checks)-len(accepted_ids),
        'views':checks,
        'accepted_capture_ids':accepted_ids,
        'trust_level':'PROVISIONAL_GEOMETRIC_CONSISTENCY_ONLY',
        'absolute_registration_accuracy_verified':False,
        'under_surface_registration_verified':False,
        'group_C_underside_registered':False,
        'no_new_pose_optimization':True,
        'world_frame':ft10_report['world_frame'],
    }
    object_quality={
        'schema':'scantopath.c1.object_normals.v1',
        'input_measured_points_from_accepted_views':int(len(cloud_points)),
        'voxel_filtered_points':int(len(voxel)),
        'output_measured_points':int(len(cleaned)),
        'outlier_filter':outlier_report,'normal_statistics':normal_report,
        'per_point_origin_sample_preserved':True,
        'no_inferred_geometry':True,
        'depth_units':'m', 'world_frame':ft10_report['world_frame'],
    }
    processing={
        'schema':SCHEMA, 'run_id':run_id,
        'stage':'C1_FT12_FT13_FT14_FT15',
        'algorithm':'FT05.8+FT09_SE3+FT10_voxel+C1_SOR_PCA_NN_GATE',
        'version':'C1.0.0','created_utc':datetime.now(timezone.utc).isoformat(),
        'state':'SUCCEEDED_FUNCTIONAL_METRIC_'+metric['gate'],
        'input_capture_ids':[r['capture_id'] for r in accepted],
        'accepted_capture_ids':accepted_ids,
        'input_source':{'ft09_dir':str(seq),'ft10_dir':str(ft10),
                        'ft09_manifest_sha256':file_hash(seq/'sha256_manifest.json'),
                        'ft09_tracking_sha256':file_hash(seq/'tracking_sequence.json'),
                        'ft10_manifest_sha256':file_hash(ft10/'sha256_manifest.json'),
                        'ft10_report_sha256':file_hash(ft10/'accumulation_report.json'),
                        'metric_reference_sha256':file_hash(reference_file) if reference_file else None},
        'config':vars(cfg), 'output_points':int(len(cleaned)),
        'metric_gate':metric['gate'],
        'metric_accuracy_verified':False,
        'registration_trust':'PROVISIONAL',
        'sqlite_processing_run_registered':False,
        'sqlite_registration_requested':store_root is not None,
        'source_raw_immutable':True,
        'mesh_implemented':False,'robot_executable':False,
    }
    parent=_safe_output(output_parent,seq,ft10)
    final=parent/('c1_'+run_id[:12]); stage=parent/('.c1-partial-'+run_id)
    if final.exists() or stage.exists():raise C1Error('C1_OUTPUT_COLLISION')
    try:
        stage.mkdir(exist_ok=False)
        files={
            'trusted_object_cloud.ply':_ply_bytes(cleaned),
            'normal_xyz.csv':_normal_csv(cleaned,normals,clean_origin),
            'object_quality.json':json_blob(object_quality),
            'registration_quality.json':json_blob(registration),
            'metric_validation.json':json_blob(metric),
            'processing_run.json':json_blob(processing),
        }
        for name,data in files.items(): (stage/name).write_bytes(data)
        (stage/'sha256_manifest.json').write_bytes(json_blob({
            'schema':'scantopath.c1.sha256.v1',
            'files':{name:sha256(data).hexdigest() for name,data in files.items()},
        }))
        verify(stage)
        verify_artifact(seq)
        verify_output(ft10)
        os.replace(stage,final)
    except BaseException:
        shutil.rmtree(stage,ignore_errors=True)
        raise
    if store_root is not None:
        from scantopath.metadata.store import MetadataStore
        with MetadataStore(store_root) as db:
            try:
                db.create_processing_run(run_id=run_id,session_id=store_session,
                    stage='C1_TRUSTED_GEOMETRY',algorithm='C1_SOR_PCA_POSE_RECHECK',version='C1.0.0',
                    input_capture_ids=accepted_ids,
                    parameters={'metric_gate':metric['gate'], 'voxel_m':cfg.voxel_m,
                                'provisional_registration':True})
                db.start_processing_run(run_id)
                db.finish_processing_run(run_id,state='succeeded',output_files=[str(final)])
            except Exception as exc:
                emit('SQLITE_REGISTRATION_FAILED',artifact_dir=str(final),detail=str(exc)[:240])
                raise C1Error('C1_SQLITE_REGISTRATION_FAILED',str(final)) from exc
    return final


def main(argv=None):
    p=argparse.ArgumentParser(description='C1 FT12–15 trusted geometric cloud (metric verification separate)')
    p.add_argument('--sequence',type=Path)
    p.add_argument('--cloud',type=Path)
    p.add_argument('--out',type=Path)
    p.add_argument('--reference',type=Path,help='Optional operator-measured x/y/z mm JSON')
    p.add_argument('--store-root',type=Path,help='OPTIONAL existing SQLite store where captures are registered')
    p.add_argument('--voxel-mm',type=float,default=4.0)
    p.add_argument('--sor-sigma',type=float,default=2.5)
    p.add_argument('--verify',type=Path)
    a=p.parse_args(argv)
    if a.verify:
        emit('VERIFIED',artifact_dir=str(a.verify),**verify(a.verify))
        return 0
    if not a.sequence or not a.cloud or not a.out:
        emit('INPUT_MISSING',required='--sequence FT09 --cloud FT10 --out OUT')
        return 2
    config=C1Config(voxel_m=a.voxel_mm/1000.0,sor_sigma=a.sor_sigma)
    result=execute(a.sequence,a.cloud,a.out,reference_file=a.reference,store_root=a.store_root,config=config)
    metric=json.loads((result/'metric_validation.json').read_text(encoding='utf8'))
    emit('READY',artifact_dir=str(result),metric_gate=metric['gate'],
         **verify(result),physical_accuracy_verified=False)
    return 0

if __name__=='__main__':
    try:sys.exit(main())
    except (ValueError,OSError,RuntimeError,KeyError,TypeError) as e:
        emit('BLOCKED',code=getattr(e,'code',type(e).__name__),detail=str(e)[:260]);sys.exit(2)
