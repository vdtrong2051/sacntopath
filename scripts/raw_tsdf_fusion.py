"""ScanToPath read-only experiment: verified FT-09 RAW -> projective TSDF surface.

No project mutation, no RAW writes, no FT-09/C1/C2 replacement, no inferred
underside claim. Camera Z-depth is integrated along projective rays; world
coordinates are the accepted FT-09 depth-optical-of-sample-0 reference.
"""
from __future__ import annotations
import argparse
import csv
from dataclasses import dataclass
from datetime import datetime, timezone
from hashlib import sha256
import json
import math
import os
from pathlib import Path
import shutil
import sys
from uuid import uuid4

import numpy as np


class TsdfError(ValueError):
    def __init__(self, code, detail=''):
        self.code=code
        super().__init__(code+((': '+str(detail)) if detail else ''))


def emit(state, **fields):
    print(json.dumps({'RAW_TSDF':state, **fields},ensure_ascii=False,allow_nan=False,sort_keys=True), flush=True)


def digest(path):
    h=sha256()
    with Path(path).open('rb') as f:
        for b in iter(lambda:f.read(1024*1024),b''): h.update(b)
    return h.hexdigest()


def json_bytes(record):
    return (json.dumps(record,ensure_ascii=False,sort_keys=True,indent=2,allow_nan=False)+'\n').encode('utf-8')


@dataclass(frozen=True)
class Config:
    voxel_mm: float=2.5
    truncation_mm: float=9.0
    support_mm: float=7.0
    depth_smooth_mm: float=4.0
    max_voxels: int=3_000_000
    max_vertices: int=550_000
    max_faces: int=1_200_000
    max_views: int=96
    max_support_points: int=230_000
    max_path_points: int=100_000

    def __post_init__(self):
        if not (1.5<=self.voxel_mm<=6 and 3<=self.truncation_mm<=20 and
                self.truncation_mm>=2*self.voxel_mm and
                self.voxel_mm<=self.support_mm<=20 and
                0<=self.depth_smooth_mm<=8 and
                10000<=self.max_voxels<=5_000_000 and
                1000<=self.max_vertices<=800_000 and
                1000<=self.max_faces<=2_000_000 and
                1<=self.max_views<=96):
            raise TsdfError('TSDF_CONFIG_INVALID')


@dataclass
class DepthView:
    sample_index: int
    capture_id: str
    raw_depth_u16: np.ndarray
    mask: np.ndarray
    fx: float
    fy: float
    cx: float
    cy: float
    scale: float
    T_world_depth: np.ndarray
    measured_xyz_world: np.ndarray
    pose_weight: float=1.0


def smooth_masked_depth(depth_u16, mask, max_change_mm):
    """3x3 median only inside valid mask; don't blur discontinuities > threshold.

    No holes are filled, no rejected pixel is made valid. The mask remains unchanged.
    """
    raw=np.asarray(depth_u16)
    mask=np.asarray(mask,dtype=bool)
    if raw.ndim!=2 or raw.shape!=mask.shape or raw.dtype!=np.uint16:
        raise TsdfError('TSDF_DEPTH_MASK_INVALID')
    if max_change_mm<=0:
        return raw
    from scipy.ndimage import median_filter, binary_erosion
    # Masked/sentinel pixels are never promoted into the object.
    inner=binary_erosion(mask,structure=np.ones((3,3),bool),border_value=0)
    filtered=median_filter(raw,size=3,mode='nearest')
    trust=inner & (np.abs(filtered.astype(np.int32)-raw.astype(np.int32))<=max_change_mm)
    out=raw.copy()
    out[trust]=filtered[trust]
    return out


def _valid_view(view):
    a=view.raw_depth_u16
    if (a.ndim!=2 or a.dtype!=np.uint16 or view.mask.shape!=a.shape or
            not np.any(view.mask) or not (0<view.scale<.1) or
            not all(np.isfinite([view.fx,view.fy,view.cx,view.cy])) or
            view.fx<=0 or view.fy<=0 or
            view.T_world_depth.shape!=(4,4) or not np.isfinite(view.T_world_depth).all() or
            not np.allclose(view.T_world_depth[3],[0,0,0,1],atol=1e-7) or
            not np.allclose(view.T_world_depth[:3,:3].T@view.T_world_depth[:3,:3],np.eye(3),atol=1e-3) or
            view.measured_xyz_world.ndim!=2 or view.measured_xyz_world.shape[1]!=3 or
            not np.isfinite(view.measured_xyz_world).all()):
        raise TsdfError('TSDF_VIEW_INVALID',view.sample_index)


def calculate_volume(views, cfg):
    """Bounds from measured, isolated object points only, never scene/background."""
    pts=np.concatenate([v.measured_xyz_world[::max(1,len(v.measured_xyz_world)//15000)] for v in views])
    if len(pts)<100:raise TsdfError('TSDF_TOO_FEW_SOURCE_POINTS')
    # Robust bounds suppress isolated depth spikes; report rather than claim whole-object coverage.
    low=np.quantile(pts,.001,axis=0)-cfg.truncation_mm/1000-2*cfg.voxel_mm/1000
    high=np.quantile(pts,.999,axis=0)+cfg.truncation_mm/1000+2*cfg.voxel_mm/1000
    voxel=cfg.voxel_mm/1000
    dims=np.ceil((high-low)/voxel).astype(np.int32)+1
    n=int(np.prod(dims.astype(np.int64)))
    if (np.any(dims<4) or n>cfg.max_voxels or np.any(dims>700)):
        raise TsdfError('TSDF_VOLUME_BUDGET_EXCEEDED',f'{dims.tolist()}={n} voxels; use --voxel-mm 3.5 or 4')
    return low,dims,n


def integrate_tsdf(views, cfg, *, progress=None):
    """Projective TSDF with signed camera-Z distances and masked RAW observations.

    The nearest-neighbor projection is deliberately not used outside the original
    FT-05.8 depth mask. Unknown space isn't integrated as free space.
    """
    if not views or len(views)>cfg.max_views:
        raise TsdfError('TSDF_VIEWS_INVALID')
    for v in views:_valid_view(v)
    low,dims,n=calculate_volume(views,cfg)
    nx,ny,nz=map(int,dims)
    voxel=cfg.voxel_mm/1000
    trunc=cfg.truncation_mm/1000
    numerator=np.zeros(n,dtype=np.float32)
    weights=np.zeros(n,dtype=np.float32)
    supports=np.zeros(n,dtype=np.uint8)
    diagnostics=[]
    for view_idx,view in enumerate(views):
        depth=smooth_masked_depth(view.raw_depth_u16,view.mask,cfg.depth_smooth_mm/view.scale/1000)
        R=view.T_world_depth[:3,:3]
        t=view.T_world_depth[:3,3]
        h,w=depth.shape
        added=0
        for start in range(0,n,120_000):
            end=min(n,start+120_000)
            linear=np.arange(start,end,dtype=np.int64)
            xx=linear//(ny*nz)
            yy=(linear//nz)%ny
            zz=linear%nz
            world=np.stack((low[0]+xx*voxel,low[1]+yy*voxel,low[2]+zz*voxel),axis=1)
            cam=(world-t)@R
            good=cam[:,2]>.05
            valid_ids=np.flatnonzero(good)
            if not len(valid_ids):continue
            cam_pts=cam[valid_ids]
            u=np.rint(view.fx*cam_pts[:,0]/cam_pts[:,2]+view.cx).astype(np.int32)
            v=np.rint(view.fy*cam_pts[:,1]/cam_pts[:,2]+view.cy).astype(np.int32)
            inside=(u>=0)&(u<w)&(v>=0)&(v<h)
            valid_ids=valid_ids[inside];u=u[inside];v=v[inside]
            if not len(valid_ids):continue
            mask_ok=view.mask[v,u]
            valid_ids=valid_ids[mask_ok];u=u[mask_ok];v=v[mask_ok]
            if not len(valid_ids):continue
            distances=(depth[v,u].astype(np.float32)*view.scale-cam[valid_ids,2]).astype(np.float32)
            band=(np.abs(distances)<=trunc)&(depth[v,u]>0)
            valid_ids=valid_ids[band];distances=distances[band]
            if not len(valid_ids):continue
            chosen=linear[valid_ids]
            s=np.clip(distances/trunc,-1,1)
            wgt=np.float32(view.pose_weight)
            numerator[chosen]+=s*wgt
            weights[chosen]+=wgt
            supports[chosen]+=1
            added+=len(chosen)
        info={'sample_index':view.sample_index,'capture_id':view.capture_id,
              'projected_voxels_near_depth':added, 'mask_pixels':int(view.mask.sum()),
              'pose_blend_weight':float(view.pose_weight)}
        diagnostics.append(info)
        if progress:progress(view_idx+1,len(views),info)
    enough=weights>.0001
    if int(enough.sum())<100:
        raise TsdfError('TSDF_NO_OBSERVATIONS')
    # Unknown voxels explicitly hold +1, but the final mesh is separately
    # gated against real sensor points to reject unknown-space boundaries.
    tsdf=np.ones(n,dtype=np.float32)
    tsdf[enough]=numerator[enough]/weights[enough]
    return tsdf.reshape((nx,ny,nz)),weights.reshape((nx,ny,nz)),supports.reshape((nx,ny,nz)),low,diagnostics


def reconstruct_mesh(tsdf,weights,low,cfg,source_xyz):
    """VTK isosurface + measured-support triangle gate, no underside fabrication."""
    try:
        from vtkmodules.vtkCommonDataModel import vtkImageData
        from vtkmodules.vtkFiltersCore import vtkFlyingEdges3D
        from vtkmodules.util.numpy_support import numpy_to_vtk, vtk_to_numpy
        from scipy.spatial import cKDTree
        from scipy.ndimage import gaussian_filter
    except ImportError as e:
        raise TsdfError('TSDF_VTK_SCIPY_REQUIRED',str(e)) from e
    known=weights>0
    # Smooth signed distance only within observed bands; do not interpolate
    # across unknown regions by normalized-convolution weight extension alone.
    numer=gaussian_filter(tsdf*known.astype(np.float32),.55)
    denom=gaussian_filter(known.astype(np.float32),.55)
    smoothed=np.ones(tsdf.shape,dtype=np.float32)
    region=known & (denom>.20)
    smoothed[region]=np.clip(numer[region]/denom[region],-1,1)
    vol=vtkImageData()
    dims=tuple(map(int,tsdf.shape))
    vol.SetDimensions(*dims)
    step=cfg.voxel_mm/1000
    vol.SetSpacing(step,step,step)
    vol.SetOrigin(*map(float,low))
    scalars=numpy_to_vtk(np.ascontiguousarray(smoothed.transpose(2,1,0)).ravel(),deep=True)
    scalars.SetName('tsdf')
    vol.GetPointData().SetScalars(scalars)
    mc=vtkFlyingEdges3D()
    mc.SetInputData(vol)
    mc.SetValue(0,0.0)
    mc.Update()
    poly=mc.GetOutput()
    if poly.GetNumberOfPoints()<3 or poly.GetNumberOfPolys()<12:
        raise TsdfError('TSDF_MESH_EMPTY')
    if poly.GetNumberOfPoints()>cfg.max_vertices or poly.GetNumberOfPolys()>cfg.max_faces:
        raise TsdfError('TSDF_MESH_BUDGET_EXCEEDED',f'{poly.GetNumberOfPoints()} vertices {poly.GetNumberOfPolys()} faces')
    vertices=vtk_to_numpy(poly.GetPoints().GetData()).astype(np.float64,copy=True)
    packed=vtk_to_numpy(poly.GetPolys().GetData())
    if len(packed)%4 or np.any(packed[::4]!=3):
        raise TsdfError('TSDF_TRIANGLE_LAYOUT_INVALID')
    faces=packed.reshape(-1,4)[:,1:].astype(np.int32,copy=True)
    # The TSDF is a smooth extrapolation; prevent unsupported face bridging.
    tree=cKDTree(np.asarray(source_xyz,dtype=np.float32))
    max_support=cfg.support_mm/1000
    dist,_=tree.query(vertices,k=1,workers=1)
    vertex_supported=(dist<=max_support)
    supported=vertex_supported[faces].all(axis=1)
    triangles=vertices[faces]
    centers=triangles.mean(axis=1)
    center_dist,_=tree.query(centers,k=1,workers=1)
    supported &= center_dist<=max_support
    edges=np.stack([np.linalg.norm(triangles[:,i]-triangles[:,j],axis=1) for i,j in [(0,1),(1,2),(2,0)]],axis=1)
    supported &= edges.max(axis=1)<=max(3*step,0.012)
    a=triangles[:,1]-triangles[:,0]
    b=triangles[:,2]-triangles[:,0]
    supported &= np.linalg.norm(np.cross(a,b),axis=1)>1e-11
    f=faces[supported]
    if len(f)<12:raise TsdfError('TSDF_INSUFFICIENT_SUPPORTED_FACES',f'{len(f)}/{len(faces)}')
    used,inverse=np.unique(f.ravel(),return_inverse=True)
    vv=vertices[used].astype(np.float32)
    ff=inverse.reshape(-1,3).astype(np.int32)
    report={
      'candidate_faces':int(len(faces)),
      'supported_faces':int(len(ff)),
      'rejected_faces':int(len(faces)-len(ff)),
      'vertices':int(len(vv)),
      'support_fraction':float(len(ff)/len(faces)),
      'support_radius_mm':cfg.support_mm,
      'raw_observation_points':int(len(source_xyz)),
      'unknown_space_surface_rejected':True,
      'underside_verified':False,
      'metric_accuracy_verified':False,
    }
    return vv,ff,report


def _input_frames(root,repo,cfg,min_depth,max_depth):
    import sys
    sys.path.insert(0,str(repo/'src'))
    sys.path.insert(0,str(repo/'scripts'))
    from b02_live_sequence import verify_artifact
    from ft10_merge_multiview import _read_trusted_packet
    from scantopath.modules.reconstruction.application.multiview_accumulation import validated_trajectory
    from scantopath.modules.reconstruction.application.live_pair import cloud_from_live_packet
    verify_artifact(root)
    record=json.loads((root/'tracking_sequence.json').read_text(encoding='utf8'))
    accepted,skipped=validated_trajectory(record)
    if len(accepted)>cfg.max_views:
        raise TsdfError('TSDF_VIEW_BUDGET_EXCEEDED',f'{len(accepted)}>{cfg.max_views}')
    hashes=json.loads((root/'sha256_manifest.json').read_text(encoding='utf8'))['files']
    views=[]
    world=[]
    for row in accepted:
        packet=_read_trusted_packet(root,row,hashes)
        meta=packet.metadata
        if (meta.alignment_mode!='disabled' or meta.depth_distortion.sdk_model not in (0,4) or
             any(v!=0 for v in meta.depth_distortion.k1_k6_p1_p2)):
            raise TsdfError('TSDF_DEPTH_DISTORTION_UNSUPPORTED',row['sample_index'])
        isolated=cloud_from_live_packet(packet,roi=None,min_depth_m=min_depth,
                    max_depth_m=max_depth,reference_mode='charuco')
        xyz=np.asarray(isolated.cloud.xyz_depth_m,dtype=np.float32)
        uv=np.asarray(isolated.cloud.depth_source_uv,dtype=np.int32)
        H,W=meta.depth.height,meta.depth.width
        mask=np.zeros((H,W),dtype=bool)
        mask[uv[:,1],uv[:,0]]=True
        T=np.asarray(row['T_world_depth'],dtype=np.float64)
        world_xyz=xyz.astype(np.float64)@T[:3,:3].T+T[:3,3]
        # A bounded, stable subset of measured points supports the final mesh.
        world.append(world_xyz[::max(1,len(world_xyz)//10000)].astype(np.float32))
        raw=np.frombuffer(packet.depth_y16_le,dtype='<u2').reshape(H,W)
        intr=meta.depth_intrinsics
        # Pose quality affects blending, but does not override FT-09 acceptance.
        quality=row.get('quality') or {}
        overlap=float(quality.get('overlap',1.0))
        rmse=float(quality.get('inlier_rmse_m',0.) or 0.)
        if not np.isfinite(overlap) or not np.isfinite(rmse):
            raise TsdfError('TSDF_POSE_QUALITY_INVALID',row['sample_index'])
        weight=float(np.clip(overlap,.28,1.0)/(1.+max(rmse,0.)/.006))
        view=DepthView(int(row['sample_index']),meta.capture_id,raw.copy(),mask,
                float(intr.fx),float(intr.fy),float(intr.cx),float(intr.cy),
                float(meta.depth_scale_m_per_unit),T,world_xyz,pose_weight=weight)
        views.append(view)
        emit('RAW_MASK_READY',sample_index=int(row['sample_index']),masked_pixels=int(mask.sum()))
    source=np.concatenate(world)
    if len(source)>cfg.max_support_points:
        take=np.rint(np.linspace(0,len(source)-1,cfg.max_support_points)).astype(int)
        source=source[take]
    return views,source,record,accepted,skipped,verify_artifact


def _parse_c1(c1_folder,source_sequence,repo):
    if c1_folder is None:return None
    sys.path.insert(0,str(repo/'src'));sys.path.insert(0,str(repo/'scripts'))
    from c1_trusted_cloud import verify
    verify(c1_folder)
    proc=json.loads((c1_folder/'processing_run.json').read_text(encoding='utf8'))
    if Path(proc['input_source']['ft09_dir']).resolve(strict=True)!=source_sequence:
        raise TsdfError('TSDF_C1_LINEAGE_MISMATCH')
    xyz=[];norm=[]
    with (c1_folder/'normal_xyz.csv').open(newline='',encoding='utf8') as f:
        reader=csv.DictReader(f)
        if reader.fieldnames!=['x_m','y_m','z_m','nx','ny','nz','source_sample_index']:
            raise TsdfError('TSDF_C1_NORMAL_CSV_INVALID')
        for row in reader:
            xyz.append([float(row[k]) for k in ['x_m','y_m','z_m']])
            norm.append([float(row[k]) for k in ['nx','ny','nz']])
    return np.asarray(xyz,float),np.asarray(norm,float),proc


def _generate_paths(vertices,faces,c1_data,repo,cfg):
    if c1_data is None:return {},{'status':'SKIPPED_NO_C1','reason':'Supply --c1 C1 artifact verified to same source sequence.'}
    sys.path.insert(0,str(repo/'src'));sys.path.insert(0,str(repo/'scripts'))
    from scantopath.modules.reconstruction.application.c2_surface_path import generate_paths,C2Config
    from c2_surface_to_path import _csv_paths,_preview_ribbon
    xyz,norm,_=c1_data
    config=C2Config(mesh_spacing_m=cfg.voxel_mm/1000,support_radius_m=max(cfg.support_mm/1000,.009),
         max_edge_m=.032,zigzag_step_m=.009,contour_step_m=.009,path_sample_m=.004,
         max_source_points=40_000,max_triangles=500_000,max_path_points=cfg.max_path_points)
    data={};report={}
    for kind,color in [('zigzag',[245,142,44]),('contour',[67,194,225])]:
        try:
            lines,stats=generate_paths(vertices,faces,xyz,norm,kind=kind,cfg=config)
            data[kind+'.csv']=_csv_paths(lines)
            data[kind+'_preview.ply']=_preview_ribbon(lines,color)
            report[kind]={'status':'READY',**stats}
        except Exception as exc:
            # A mesh can be valid while a path cannot be safely constrained.
            report[kind]={'status':'BLOCKED','code':getattr(exc,'code',type(exc).__name__),'detail':str(exc)[:180]}
    return data,report


def _ply_bytes(vertices,faces):
    # Same PLY layout as C2 (geometry only, no texture yet).
    head=('ply\nformat binary_little_endian 1.0\n'
          'comment ScanToPath EXPERIMENTAL projective TSDF; no metric/underside certification\n'
          f'element vertex {len(vertices)}\n'
          'property float x\nproperty float y\nproperty float z\n'
          f'element face {len(faces)}\nproperty list uchar int vertex_indices\nend_header\n').encode('ascii')
    dtype=np.dtype([('n','u1'),('i','<i4',(3,))])
    f=np.empty(len(faces),dtype=dtype)
    f['n']=3;f['i']=faces
    return head+np.asarray(vertices,dtype='<f4').tobytes()+f.tobytes()


def _verify_result(out):
    index=json.loads((out/'sha256_manifest.json').read_text(encoding='utf-8'))
    files=index['files']
    if set(p.name for p in out.iterdir())!=set(files)|{'sha256_manifest.json'}:
        raise TsdfError('TSDF_RESULT_FILESET_CHANGED')
    for name,check in files.items():
        if '/' in name or '\\' in name or not (out/name).is_file() or (out/name).is_symlink() or digest(out/name)!=check:
            raise TsdfError('TSDF_RESULT_CHECKSUM_MISMATCH',name)
    return True


def run(args):
    repo=Path(args.repo).resolve(strict=True)
    root=Path(args.sequence).resolve(strict=True)
    parent=Path(args.out).resolve(strict=False)
    c1=Path(args.c1).resolve(strict=True) if args.c1 else None
    if not (repo/'src/scantopath').is_dir() or not (root/'tracking_sequence.json').is_file():
        raise TsdfError('TSDF_REPO_OR_SEQUENCE_INVALID')
    project_store=repo/'scantopath-data'
    within_named_store = (parent.is_relative_to(project_store) and
                          (project_store/'metadata.sqlite3').is_file())
    if parent==repo or (parent.is_relative_to(repo) and not within_named_store) or parent==root or parent.is_relative_to(root):
        raise TsdfError('TSDF_OUTPUT_INSIDE_INPUT_OR_REPO')
    if parent.is_symlink() or (hasattr(parent,'is_junction') and parent.is_junction()):
        raise TsdfError('TSDF_OUTPUT_SYMLINK_REFUSED')
    if parent.exists() and any(p.is_symlink() or (not p.is_dir()) or
                               not p.name.startswith('raw_tsdf_')
                               for p in parent.iterdir()):
        raise TsdfError('TSDF_OUTPUT_UNEXPECTED_EXISTING_ENTRIES')
    cfg=Config(voxel_mm=args.voxel_mm,truncation_mm=args.truncation_mm,
        support_mm=args.support_mm,depth_smooth_mm=args.depth_smooth_mm,max_voxels=args.max_voxels)
    c1_data=_parse_c1(c1,root,repo) if c1 else None
    views,source,record,accepted,skipped,verifier=_input_frames(root,repo,cfg,args.min_depth_m,args.max_depth_m)
    emit('SOURCE_VERIFIED',frames=record['source_frame_count'],accepted_poses=len(accepted),
         rejected_poses=len(skipped),selected_views=len(views))
    tsdf,weights,supports,low,diagnostics=integrate_tsdf(views,cfg,
        progress=lambda i,n,info:emit('FUSING',view=i,total=n,**info))
    vertices,faces,mesh= reconstruct_mesh(tsdf,weights,low,cfg,source)
    paths,path_report=_generate_paths(vertices,faces,c1_data,repo,cfg)
    verifier(root)  # read-only source integrity recheck before publishing results
    parent.mkdir(parents=True,exist_ok=True)
    runid=uuid4().hex[:12]
    final=parent/('raw_tsdf_'+runid)
    staging=parent/('.partial_tsdf_'+runid)
    if final.exists() or staging.exists():raise TsdfError('TSDF_OUTPUT_COLLISION')
    try:
        staging.mkdir(exist_ok=False)
        files={'tsdf_fused_mesh.ply':_ply_bytes(vertices,faces),
              'fusion_report.json':json_bytes({
                'schema':'scantopath.raw_tsdf_fusion.v1','mode':'EXPERIMENTAL_READ_ONLY',
                'source_sequence':str(root),
                'source_sha256':digest(root/'sha256_manifest.json'),
                'tracking_sha256':digest(root/'tracking_sequence.json'),
                'c1_artifact_dir':str(c1) if c1 else None,
                'c1_manifest_sha256':digest(c1/'sha256_manifest.json') if c1 else None,
                'source_frames':record['source_frame_count'],
                'ft09_accepted_views':len(accepted),'ft09_rejected_views':len(skipped),
                'views_fused':len(views),'parameters':vars(cfg),
                'voxels_total':int(tsdf.size), 'voxels_observed':int(np.count_nonzero(weights)),
                'voxels_multi_view':int(np.count_nonzero(supports>=2)),
                'world_frame':'depth_optical_of_sample_0','depth_unit':'m',
                'algorithm':'PROJECTIVE_TSDF_MASKED_RAW_DEPTH+VTK_FLYING_EDGES+MEASURED_SUPPORT',
                'mask_origin':'FT05.8_CHARUCO',
                'vertex_error_vs_ground_truth_mm':None,
                'metric_accuracy_verified':False,'underside_verified':False,
                'confidence':'PROVISIONAL_FT09_POSE_ONLY',
                'mesh':mesh,'views':diagnostics}) ,
              'path_quality.json':json_bytes(path_report)}
        files.update(paths)
        for name,content in files.items(): (staging/name).write_bytes(content)
        manifest={'schema':'scantopath.raw_tsdf.sha256.v1','files':{name:sha256(blob).hexdigest() for name,blob in files.items()}}
        (staging/'sha256_manifest.json').write_bytes(json_bytes(manifest))
        _verify_result(staging)
        os.replace(staging,final)
    except BaseException:
        if staging.exists():shutil.rmtree(staging,ignore_errors=True)
        raise
    emit('READY',artifact_dir=str(final),vertices=len(vertices),faces=len(faces),views=len(views),
         voxels_observed=int(np.count_nonzero(weights)),multi_view_voxels=int(np.count_nonzero(supports>=2)),
         zigzag=path_report.get('zigzag',{}).get('status','SKIPPED'),
         contour=path_report.get('contour',{}).get('status','SKIPPED'))
    return final


def main(argv=None):
    parser=argparse.ArgumentParser(description='ScanToPath RAW projective TSDF fusion experiment')
    parser.add_argument('--verify',type=Path,help='Verify existing immutable TSDF artifact; no camera or SQLite')
    parser.add_argument('--repo',type=Path)
    parser.add_argument('--sequence',type=Path)
    parser.add_argument('--out',type=Path)
    parser.add_argument('--c1',type=Path,help='Optional verified C1 source for Zigzag/Contour + normals')
    parser.add_argument('--voxel-mm',type=float,default=2.5)
    parser.add_argument('--truncation-mm',type=float,default=9.0)
    parser.add_argument('--support-mm',type=float,default=7.0)
    parser.add_argument('--depth-smooth-mm',type=float,default=4.0)
    parser.add_argument('--min-depth-m',type=float,default=.30)
    parser.add_argument('--max-depth-m',type=float,default=1.2)
    parser.add_argument('--max-voxels',type=int,default=3_000_000)
    args=parser.parse_args(argv)
    try:
        if args.verify:
            root=Path(args.verify).resolve(strict=True)
            _verify_result(root)
            report=json.loads((root/'fusion_report.json').read_text(encoding='utf8'))
            emit('VERIFIED',artifact_dir=str(root),vertices=report['mesh']['vertices'],
                 faces=report['mesh']['supported_faces'],views=report['views_fused'])
            return 0
        if args.repo is None or args.sequence is None or args.out is None:
            raise TsdfError('TSDF_ARGUMENTS_MISSING')
        run(args)
    except Exception as e:
        emit('BLOCKED',error_code=getattr(e,'code',type(e).__name__),detail=str(e)[:450])
        return 2
    return 0

if __name__=='__main__':sys.exit(main())
