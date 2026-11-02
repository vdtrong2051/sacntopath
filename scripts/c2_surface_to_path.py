"""C2 FT16-18: verified C1 artifact -> supported mesh + Zigzag/Contour + path exports.

Offline command, no camera/Qt, no RAW or SQLite modifications. All newly
synthesized mesh vertices are labeled interpolated; support is nearest measured
C1 cloud. Robot-executable motion planning is strictly out of scope.
"""
from __future__ import annotations

import argparse
import csv
from datetime import datetime, timezone
from hashlib import sha256
import io
import json
import os
from pathlib import Path
import shutil
import sys
from uuid import uuid4
import numpy as np

from scantopath.modules.reconstruction.application.c2_surface_path import (
    C2Config, C2Error, reconstruct_surface, generate_paths,
)

SCHEMA='scantopath.c2.surface_to_path.v1'
OUTPUT_FILES=(
    'surface_mesh.ply','zigzag.csv','contour.csv',
    'zigzag_preview.ply','contour_preview.ply',
    'surface_coverage.json','path_quality.json','processing_run.json',
)


def emit(state, **kwargs):
    print(json.dumps({'C2_STATUS':state, **kwargs},ensure_ascii=False,sort_keys=True,allow_nan=False),flush=True)


def blob(doc):
    return (json.dumps(doc,ensure_ascii=False,sort_keys=True,indent=2,allow_nan=False)+'\n').encode('utf8')


def digest_file(path):
    dig=sha256()
    with Path(path).open('rb') as f:
        for block in iter(lambda:f.read(1024*1024),b''):dig.update(block)
    return dig.hexdigest()


def _check_dir(path, code):
    root=Path(path)
    if root.is_symlink() or not root.is_dir() or (hasattr(root,'is_junction') and root.is_junction()):
        raise C2Error(code)
    return root.resolve(strict=True)


def _ply_mesh(vertices, faces, *, colors=None):
    points=np.asarray(vertices,dtype=np.float64)
    polys=np.asarray(faces,dtype=np.int32)
    if (points.ndim!=2 or points.shape[1]!=3 or len(points)<3
        or not np.isfinite(points).all() or polys.ndim!=2 or polys.shape[1]!=3
        or len(polys)<1 or np.min(polys)<0 or np.max(polys)>=len(points)):
        raise C2Error('C2_PLY_GEOMETRY_INVALID')
    if colors is not None:
        colors=np.asarray(colors,dtype=np.uint8)
        if colors.shape!=points.shape:raise C2Error('C2_PLY_COLOR_INVALID')
    head=['ply','format binary_little_endian 1.0',
          'comment ScanToPath C2 surface or path visualization: metric unverified',
          f'element vertex {len(points)}',
          'property float x','property float y','property float z']
    if colors is not None:
        head.extend(('property uchar red','property uchar green','property uchar blue'))
    head.extend((f'element face {len(polys)}', 'property list uchar int vertex_indices', 'end_header'))
    if colors is None:
        verts=np.asarray(points,dtype='<f4').tobytes()
    else:
        rec=np.empty(len(points),dtype=[('x','<f4'),('y','<f4'),('z','<f4'),
                                        ('red','u1'),('green','u1'),('blue','u1')])
        for j,a in enumerate(('x','y','z')):rec[a]=points[:,j]
        for j,a in enumerate(('red','green','blue')):rec[a]=colors[:,j]
        verts=rec.tobytes()
    records=np.empty(len(polys),dtype=[('n','u1'),('v','<i4',(3,))])
    records['n']=3;records['v']=polys
    return ('\n'.join(head)+'\n').encode('ascii')+verts+records.tobytes()


def _preview_ribbon(lines, color):
    """Thin mesh ribbon for the existing VTK PLY viewer. NOT the path export."""
    vertices=[];faces=[]
    for path in lines:
        xyz=path['points'];normals=path['normals']
        if len(xyz)<2:continue
        tangent=np.zeros_like(xyz)
        tangent[1:-1]=xyz[2:]-xyz[:-2]
        tangent[0]=xyz[1]-xyz[0]; tangent[-1]=xyz[-1]-xyz[-2]
        side=np.cross(tangent,normals)
        size=np.linalg.norm(side,axis=1)
        # Path is surface-constrained; avoid ill-defined ribbon orientation.
        fallback=size<1e-10
        if np.any(fallback):
            side[fallback]=np.cross(tangent[fallback],np.array([1.,0.,0.]))
            size=np.linalg.norm(side,axis=1)
            fallback=size<1e-10
            side[fallback]=np.cross(tangent[fallback],np.array([0.,1.,0.]))
            size=np.linalg.norm(side,axis=1)
        side=side / np.maximum(size[:,None],1e-12)*.0006
        start=len(vertices)
        for p,s in zip(xyz,side):vertices.extend((p-s,p+s))
        for j in range(len(xyz)-1):
            u=start+2*j;faces.extend(((u,u+1,u+2),(u+1,u+3,u+2)))
    if not faces:raise C2Error('C2_PREVIEW_EMPTY')
    cols=np.tile(np.asarray(color,dtype=np.uint8),(len(vertices),1))
    return _ply_mesh(np.asarray(vertices),np.asarray(faces),colors=cols)


def _csv_paths(lines):
    stream=io.StringIO(newline='')
    writer=csv.writer(stream,lineterminator='\n')
    writer.writerow(('segment_id','sample','strip_index','x_m','y_m','z_m','nx','ny','nz','source_point_index'))
    for i,line in enumerate(lines):
        for j,(p,n,index) in enumerate(zip(line['points'],line['normals'],line['source_indices'])):
            writer.writerow((i,j,line['strip_index'],*(f'{float(v):.9g}' for v in p),
                             *(f'{float(v):.9g}' for v in n),int(index)))
    return stream.getvalue().encode('utf8')


def verify(folder):
    root=_check_dir(folder,'C2_OUTPUT_MISSING')
    manifest=json.loads((root/'sha256_manifest.json').read_text(encoding='utf8'))
    if (manifest.get('schema')!='scantopath.c2.sha256.v1'
        or set(manifest.get('files',{}))!=set(OUTPUT_FILES)
        or {p.name for p in root.iterdir()}!=set(OUTPUT_FILES)|{'sha256_manifest.json'}):
        raise C2Error('C2_MANIFEST_INVALID')
    for name,digest in manifest['files'].items():
        f=root/name
        if f.is_symlink() or not f.is_file() or digest_file(f)!=digest:
            raise C2Error('C2_OUTPUT_SHA_MISMATCH',name)
    q=json.loads((root/'path_quality.json').read_text(encoding='utf8'))
    surf=json.loads((root/'surface_coverage.json').read_text(encoding='utf8'))
    if (surf['mesh_faces']<12 or surf['underside_coverage_verified'] is not False
        or any(q[k]['path_points']<2 for k in ('zigzag','contour'))):
        raise C2Error('C2_OUTPUT_QUALITY_INVALID')
    for kind in ('zigzag','contour'):
        with (root/(kind+'.csv')).open(newline='',encoding='utf8') as fh:
            reader=csv.DictReader(fh)
            if reader.fieldnames!=['segment_id','sample','strip_index','x_m','y_m','z_m','nx','ny','nz','source_point_index']:
                raise C2Error('C2_CSV_HEADER_INVALID')
            count=0
            for row in reader:
                values=[float(row[key]) for key in ('x_m','y_m','z_m','nx','ny','nz')]
                if not all(np.isfinite(values)) or abs(np.linalg.norm(values[3:])-1)>0.03:
                    raise C2Error('C2_CSV_COORDINATE_INVALID')
                count+=1
            if count!=q[kind]['path_points']:raise C2Error('C2_CSV_COUNT_INVALID')
    return {'faces':surf['mesh_faces'],'vertices':surf['mesh_vertices'],
            'zigzag_points':q['zigzag']['path_points'],'contour_points':q['contour']['path_points']}


def execute(c1_folder, output_parent, *, cfg=None):
    from c1_trusted_cloud import verify as verify_c1
    cfg=cfg or C2Config()
    c1=_check_dir(c1_folder,'C2_INPUT_MISSING')
    verify_c1(c1)  # fail before touching output if C1 artifact changed
    quality=json.loads((c1/'object_quality.json').read_text(encoding='utf8'))
    reg=json.loads((c1/'registration_quality.json').read_text(encoding='utf8'))
    process=json.loads((c1/'processing_run.json').read_text(encoding='utf8'))
    if (quality.get('no_inferred_geometry') is not True or
        reg.get('views_accepted',0)<2 or
        process.get('metric_accuracy_verified') is not False or
        process.get('output_points') != quality.get('output_measured_points')):
        raise C2Error('C2_C1_LINEAGE_INVALID')
    xyz=[];normals=[]
    with (c1/'normal_xyz.csv').open('r',encoding='utf8',newline='') as handle:
        reader=csv.DictReader(handle)
        if reader.fieldnames!=['x_m','y_m','z_m','nx','ny','nz','source_sample_index']:
            raise C2Error('C2_NORMAL_INPUT_HEADER_INVALID')
        for row in reader:
            xyz.append(tuple(float(row[k]) for k in ('x_m','y_m','z_m')))
            normals.append(tuple(float(row[k]) for k in ('nx','ny','nz')))
    xyz=np.asarray(xyz,dtype=float);normals=np.asarray(normals,dtype=float)
    verts,faces,surface=reconstruct_surface(xyz,normals,cfg)
    zig,zig_report=generate_paths(verts,faces,xyz,normals,kind='zigzag',cfg=cfg)
    contour,contour_report=generate_paths(verts,faces,xyz,normals,kind='contour',cfg=cfg)
    source={'c1_artifact_dir':str(c1),'c1_manifest_sha256':digest_file(c1/'sha256_manifest.json'),
            'c1_processing_run_sha256':digest_file(c1/'processing_run.json'),
            'c1_run_id':process['run_id'],'source_capture_ids':process.get('accepted_capture_ids',[])}
    surface.update({'source':source,'world_frame':quality['world_frame'],'depth_units':'m',
                    'physical_10mm_gate':process.get('metric_gate','NOT_TESTED')})
    path_report={'schema':'scantopath.c2.paths.v1','zigzag':zig_report,'contour':contour_report,
                 'normal_provenance':'NEAREST_C1_MEASURED_POINT_PCA_NORMAL',
                 'path_frame':quality['world_frame'],'units':'m',
                 'object_up_axis_confirmed':False,
                 'robot_executable':False,'controller_code_generated':False}
    record={'schema':SCHEMA,'run_id':uuid4().hex,'created_utc':datetime.now(timezone.utc).isoformat(),
            'stage':'C2_FT16_FT17_FT18','state':'SUCCEEDED_GEOMETRIC_REFERENCE_ONLY',
            'algorithm':'VTK_IMPLICIT_SURFACE_SUPPORT_GATE+TRIANGLE_SLICING',
            'params':vars(cfg),'input':source,
            'output_mesh_faces':len(faces),'output_zigzag_points':zig_report['path_points'],
            'output_contour_points':contour_report['path_points'],
            'physical_accuracy_verified':False,'underside_coverage_verified':False,
            'robot_executable':False,'raw_unchanged':True}
    parent=Path(output_parent).absolute()
    if parent.is_symlink() or (hasattr(parent,'is_junction') and parent.is_junction()):
        raise C2Error('C2_OUTPUT_LINK_REFUSED')
    p=parent.resolve(strict=False)
    repo=Path(__file__).resolve().parents[1]
    if any(p==v or p.is_relative_to(v) for v in (repo,c1)):
        raise C2Error('C2_OUTPUT_INSIDE_SOURCE_OR_REPO')
    parent.mkdir(parents=True,exist_ok=True)
    run=record['run_id']
    final=parent/('c2_'+run[:12]);partial=parent/('.c2-partial-'+run)
    if final.exists() or partial.exists():raise C2Error('C2_OUTPUT_COLLISION')
    try:
        partial.mkdir(exist_ok=False)
        contents={
            'surface_mesh.ply':_ply_mesh(verts,faces),
            'zigzag.csv':_csv_paths(zig),
            'contour.csv':_csv_paths(contour),
            'zigzag_preview.ply':_preview_ribbon(zig,[245,142,44]),
            'contour_preview.ply':_preview_ribbon(contour,[67,194,225]),
            'surface_coverage.json':blob(surface),
            'path_quality.json':blob(path_report),
            'processing_run.json':blob(record),
        }
        for name,data in contents.items():(partial/name).write_bytes(data)
        (partial/'sha256_manifest.json').write_bytes(blob({'schema':'scantopath.c2.sha256.v1',
                           'files':{name:sha256(data).hexdigest() for name,data in contents.items()}}))
        verify(partial)
        verify_c1(c1)  # TOCTOU source integrity recheck
        os.replace(partial,final)
    except BaseException:
        shutil.rmtree(partial,ignore_errors=True)
        raise
    return final


def main(argv=None):
    parser=argparse.ArgumentParser(description='ScanToPath C2 FT16/17/18 mesh + Zigzag/Contour path')
    parser.add_argument('--c1',type=Path)
    parser.add_argument('--out',type=Path)
    parser.add_argument('--verify',type=Path)
    args=parser.parse_args(argv)
    if args.verify:
        emit('VERIFIED',artifact_dir=str(args.verify),**verify(args.verify));return 0
    if not args.c1 or not args.out:
        emit('BLOCKED',code='C2_ARGUMENTS_REQUIRED');return 2
    result=execute(args.c1,args.out)
    emit('READY',artifact_dir=str(result),**verify(result),
         underside_coverage_verified=False,robot_executable=False)
    return 0

if __name__=='__main__':
    try:sys.exit(main())
    except (OSError,ValueError,RuntimeError,KeyError,TypeError) as exc:
        emit('BLOCKED',code=getattr(exc,'code',type(exc).__name__),detail=str(exc)[:250]);sys.exit(2)
