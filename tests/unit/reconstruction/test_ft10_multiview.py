"""FT-10 focused acceptance tests. Fake clouds validate orchestration;
real sensor ChArUco processing is independently exercised by existing FT05/B01 tests.
"""
from __future__ import annotations
from hashlib import sha256
import json
import sys
from types import ModuleType, SimpleNamespace as NS
from pathlib import Path

import numpy as np
import pytest

from scantopath.modules.reconstruction.application.multiview_accumulation import (
    AccumulationConfig, MeasuredVoxelAccumulator, MultiviewError, validated_trajectory,
)
from ft10_merge_multiview import _ply_bytes, process, verify_output


def pose(dx=0.0):
    T = np.eye(4)
    T[0,3] = dx
    return T.tolist()


def record():
    statuses = ('ANCHOR','STATIONARY','RECOVERED','DEGRADED','TRACKING','LOST')
    rows = []
    for i,s in enumerate(statuses):
        accepted = s in ('ANCHOR','RECOVERED','TRACKING')
        rows.append(dict(sample_index=i, status=s,
                         capture_id=f'cap{i}', depth_frame_index=100+i,
                         depth_timestamp_us=100000+i*1000,
                         accepted_for_trajectory=accepted,
                         T_world_depth=pose(i*.002) if accepted else None,
                         reject_code='GEOMETRY_DEGENERATE' if s=='LOST' else None))
    return {'schema':'scantopath.ft08.17.sampled_pose_sequence.v1',
            'ft09_extension':'scantopath.ft09.quality_recovery.v1',
            'units':'m','trajectory_frame':'depth_optical_of_sample_0',
            'matrix_convention':'T_A_B maps coordinates B into A; column homogeneous vectors',
            'metric_accuracy_verified':False, 'fusion_implemented':False,
            'source_frame_count':len(rows),'accepted_poses':3,'status':'LOST','frames':rows}


def test_ft09_accepted_only_and_statuses():
    yes,no = validated_trajectory(record())
    assert [r['sample_index'] for r in yes] == [0,2,4]
    assert [r['status'] for r in no] == ['STATIONARY','DEGRADED','LOST']


@pytest.mark.parametrize('tamper,code', [
    (lambda r: r['frames'][3].update(accepted_for_trajectory=True), 'FT10_TRUSTED_POSE_INVALID'),
    (lambda r: r['frames'][3].update(T_world_depth=pose()), 'FT10_UNTRUSTED_POSE_PUBLISHED'),
    (lambda r: r['frames'][4].update(T_world_depth=[[0]*4]*4), 'FT10_TRUSTED_POSE_INVALID'),
    (lambda r: r['frames'][1].update(capture_id='cap0'), 'FT10_CAPTURE_ORDER_INVALID'),
    (lambda r: r.update(accepted_poses=4), 'FT10_INSUFFICIENT_TRUSTED_VIEWS'),
    (lambda r: r.update(ft09_extension='no'), 'FT10_FT09_TRAJECTORY_REQUIRED'),
    (lambda r: r['frames'][0].update(T_world_depth=pose(.01)), 'FT10_ANCHOR_INVALID'),
])
def test_reject_invalid_or_fake_pose(tamper,code):
    r=record();tamper(r)
    with pytest.raises(MultiviewError,match=code):validated_trajectory(r)


def test_rigid_transform_preserves_measured_points():
    acc=MeasuredVoxelAccumulator(AccumulationConfig(voxel_m=.004,max_points=1000))
    p=np.asarray([[.10,0,0],[.12,0,0]],dtype=float)
    first=acc.insert(0,p,np.eye(4)); assert first['measured_points']==2
    T=np.eye(4);T[:3,3]=[.04,.03,.02]
    acc.insert(2,np.asarray([[.02,0,0],[.04,0,0]],dtype=float),T)
    xyz,origin=acc.result()
    assert len(xyz)==4
    assert {tuple(np.round(x,3)) for x in xyz}=={(.1,0,0),(.12,0,0),(.06,.03,.02),(.08,.03,.02)}
    assert set(origin)=={0,2}


def test_deduplicate_without_creating_centroids():
    acc=MeasuredVoxelAccumulator(AccumulationConfig(voxel_m=.01,max_points=1000))
    acc.insert(0,np.asarray([[.101,0,0],[.102,0,0]]),np.eye(4))
    acc.insert(1,np.asarray([[.103,0,0],[.12,0,0]]),np.eye(4))
    xyz,ids=acc.result()
    assert len(xyz)==2
    assert list(ids)==[0,1]
    assert tuple(xyz[0])==(.101,0,0)
    assert acc.diagnostics(ids)['voxel_collisions_total']==2


def test_adaptive_voxel_bounded_and_no_inferred_points():
    acc=MeasuredVoxelAccumulator(AccumulationConfig(voxel_m=.0005,max_voxel_m=.032,max_points=1000))
    cloud=np.asarray([[i*.0004,0.05,0.10] for i in range(3000)])
    acc.insert(0,cloud,np.eye(4));acc.insert(1,cloud,np.eye(4))
    xyz,ids=acc.result()
    assert len(xyz)<=1000 and acc.promotions>0
    originals={tuple(p) for p in cloud}
    assert all(tuple(row) in originals for row in xyz)


def test_budget_fail_closed():
    acc=MeasuredVoxelAccumulator(AccumulationConfig(voxel_m=.001,max_voxel_m=.002,max_points=1000))
    cloud=np.asarray([[i*.1,0.,0.] for i in range(1200)])
    with pytest.raises(MultiviewError, match='FT10_RESOURCE_BUDGET_EXCEEDED'):
        acc.insert(0,cloud,np.eye(4))


def test_ply_reuses_b01_writer_and_has_two_modes():
    xyz=np.asarray([[1.0,2.,3.],[4.,5.,6.]],dtype=float)
    measured=_ply_bytes(xyz)
    colored=_ply_bytes(xyz,np.asarray([0,2],dtype=np.int32))
    assert b'element vertex 2' in measured
    assert b'comment ScanToPath FT-10' in measured
    assert b'property uchar red' not in measured
    assert b'property uchar red' in colored
    assert len(colored)>len(measured)


def test_bad_source_config():
    with pytest.raises(MultiviewError):AccumulationConfig(voxel_m=0.)
    with pytest.raises(MultiviewError):AccumulationConfig(max_points=5_000_000)


def _put(path, data):
    path.write_bytes(data)
    return sha256(data).hexdigest()


def create_fixture(tmp_path,monkeypatch):
    """Make a B02-like source with authentic file layout, synthetic pose test data."""
    root=tmp_path/'source';root.mkdir()
    r=record();files={}
    # Original b02 validator expects 3 files per frame + tracking_sequence.json.
    for row in r['frames']:
        i=row['sample_index'];stem=f'frame_{i:02d}'
        metadata={'capture_id':row['capture_id'],'measured':True,
                  'depth':{'frame_index':row['depth_frame_index'],'timestamp_us':row['depth_timestamp_us']}}
        files[stem+'_metadata.json']=_put(root/(stem+'_metadata.json'),json.dumps(metadata).encode())
        files[stem+'_color.mjpg']=_put(root/(stem+'_color.mjpg'),b'color'+bytes([i]))
        files[stem+'_depth.y16']=_put(root/(stem+'_depth.y16'),b'depth'+bytes([i]))
    files['tracking_sequence.json']=_put(root/'tracking_sequence.json',
                                         (json.dumps(r)+'\n').encode())
    (root/'sha256_manifest.json').write_text(json.dumps({
        'schema':'scantopath.ft08.17.sha256_manifest.v1','files':files}),encoding='utf-8')

    class Metadata:
        @staticmethod
        def model_validate_json(data):
            d=json.loads(data)
            return NS(capture_id=d['capture_id'],measured=d['measured'],
                      depth=NS(**d['depth']))
    class Packet:
        def __init__(self,m,c,d): self.metadata=m;self.color_mjpeg=c;self.depth_y16_le=d
    module=ModuleType('scantopath.domain.raw_rgbd')
    module.RawRgbdCaptureMetadataV2=Metadata
    monkeypatch.setitem(sys.modules,'scantopath.domain', ModuleType('scantopath.domain'))
    monkeypatch.setitem(sys.modules,'scantopath.domain.raw_rgbd', module)
    import scantopath.acquisition.raw_rgbd as raw
    monkeypatch.setattr(raw,'RawRgbdCapture',Packet)
    # Only the PLY header is stubbed in fixture; on user system the existing FT07 viewer does this.
    viewer=ModuleType('scantopath.modules.viewer3d.infrastructure.ply_header')
    def inspect(path):
        b=path.read_bytes().split(b'end_header\n',1)[0]
        return NS(vertex_count=int(b.split(b'element vertex ',1)[1].split(b'\n',1)[0]),
                  has_rgb=b'property uchar red' in b)
    viewer.inspect_ply=inspect
    monkeypatch.setitem(sys.modules,'scantopath.modules.viewer3d',ModuleType('scantopath.modules.viewer3d'))
    monkeypatch.setitem(sys.modules,'scantopath.modules.viewer3d.infrastructure',ModuleType('scantopath.modules.viewer3d.infrastructure'))
    monkeypatch.setitem(sys.modules,'scantopath.modules.viewer3d.infrastructure.ply_header',viewer)
    return root


def test_end_to_end_artifact_write_and_verify(tmp_path,monkeypatch):
    source=create_fixture(tmp_path,monkeypatch)
    xyz=np.asarray([[.01+0.01*i,.01, .5] for i in range(25)])
    def extractor(packet,**kwargs):
        return NS(cloud=NS(capture_id=packet.metadata.capture_id,xyz_depth_m=xyz),
                  source_ref={'isolation_source':'FT-05.8_CHARUCO',
                              'isolation_status':'CHARUCO_OBJECT_FOUND'},
                  selected_points=len(xyz))
    out=process(source,tmp_path/'FT10_output',config=AccumulationConfig(max_points=1000),
                min_depth_m=.30,max_depth_m=1.2,cloud_extractor=extractor)
    assert (out/'merged_measured.ply').is_file()
    assert (out/'debug_view_colored.ply').is_file()
    validated=verify_output(out)
    assert validated['accepted_views']==3
    report=json.loads((out/'accumulation_report.json').read_text())
    assert report['used_source_samples']==[0,2,4]
    assert [row['status'] for row in report['skipped_frames']]==['STATIONARY','DEGRADED','LOST']
    assert report['metric_accuracy_verified'] is False
    assert report['AI_ESTIMATED_points']==0
    assert len(list((tmp_path/'FT10_output').iterdir()))==1
    assert source.joinpath('frame_00_color.mjpg').read_bytes()==b'color\x00'


def test_checksum_tamper_blocks_before_output(tmp_path,monkeypatch):
    source=create_fixture(tmp_path,monkeypatch)
    (source/'frame_02_color.mjpg').write_bytes(b'changed')
    with pytest.raises(ValueError,match='B02_ARTIFACT_INTEGRITY_FAILED'):
        process(source,tmp_path/'output',config=AccumulationConfig(),
                min_depth_m=.3,max_depth_m=1.2,cloud_extractor=lambda *_a,**_k:None)
    assert not (tmp_path/'output').exists()


def test_untrusted_raw_never_opened(tmp_path,monkeypatch):
    source=create_fixture(tmp_path,monkeypatch)
    # Fixture replaces sys.modules; package attributes can point to an old module.
    raw_meta = sys.modules['scantopath.domain.raw_rgbd']
    counter=[]
    old=raw_meta.RawRgbdCaptureMetadataV2.model_validate_json
    def capture(data):
        m=old(data);counter.append(m.capture_id);return m
    monkeypatch.setattr(raw_meta.RawRgbdCaptureMetadataV2,'model_validate_json',capture)
    xyz=np.asarray([[.01+i*.01,.02,.6] for i in range(20)])
    def extractor(p,**kwargs):
        return NS(cloud=NS(capture_id=p.metadata.capture_id,xyz_depth_m=xyz),
                  source_ref={'isolation_source':'FT-05.8_CHARUCO',
                              'isolation_status':'CHARUCO_OBJECT_FOUND'},selected_points=20)
    process(source,tmp_path/'output',config=AccumulationConfig(),
            min_depth_m=.3,max_depth_m=1.2,cloud_extractor=extractor)
    assert counter==['cap0','cap2','cap4']
