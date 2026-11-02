"""C1 end-to-end functional fixture using monkeypatched FT09/FT10 contracts.

Never touches real Gemini, SQLite or user RAW. Tests atomic output/lineage/reopen.
"""
import importlib.util
import json
from pathlib import Path
import sys
import types

import numpy as np
import pytest

from scantopath.modules.reconstruction.application.c1_trusted_geometry import C1Error


def load_script():
    source=Path(__file__).resolve().parents[3]/'scripts'/'c1_trusted_cloud.py'
    spec=importlib.util.spec_from_file_location('c1_trusted_cloud_test',source)
    module=importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class FakeView:
    def __init__(self, capture_id,xyz):
        self.cloud=types.SimpleNamespace(capture_id=capture_id,xyz_depth_m=xyz)
        self.source_ref={'isolation_source':'FT-05.8_CHARUCO',
                         'isolation_status':'CHARUCO_OBJECT_FOUND',
                         'semantic_object_identity_verified':False}


def test_c1_full_mocked_pipeline_retains_lineage_and_catches_tamper(tmp_path,monkeypatch):
    script=load_script()
    sequence=tmp_path/'ft09'; sequence.mkdir()
    cloud=tmp_path/'ft10'; cloud.mkdir()
    rng=np.random.default_rng(4)
    world=np.column_stack((rng.uniform(-.045,.045,(1200,2)),
                           np.ones(1200)*.65+rng.normal(0,.0002,1200)))
    # Planar curve is enough to exercise normal PCA and independent registration.
    rows=[]
    for i in range(3):
        rows.append({'sample_index':i,'capture_id':'cap'+str(i),
                     'T_world_depth':np.eye(4).tolist(),
                     'status':'ANCHOR' if i==0 else 'TRACKING'})
    (sequence/'tracking_sequence.json').write_text(json.dumps({'source_frame_count':3}))
    (sequence/'sha256_manifest.json').write_text(json.dumps({'files':{}}))
    (cloud/'sha256_manifest.json').write_text('{}')
    (cloud/'accumulation_report.json').write_text('{}')
    report={'world_frame':'depth_optical_of_sample_0'}
    orig_inputs=script._inputs
    monkeypatch.setattr(script,'_inputs',lambda a,b:(sequence,cloud,{},report,rows,[]))
    monkeypatch.setattr(script,'_safe_output',lambda out,*unused:Path(out))

    ft09=types.ModuleType('b02_live_sequence')
    ft09.verify_artifact=lambda path: {'accepted_poses':3}
    monkeypatch.setitem(sys.modules,'b02_live_sequence',ft09)

    ft10=types.ModuleType('ft10_merge_multiview')
    ft10.verify_output=lambda path:{'points':1200}
    ft10._read_trusted_packet=lambda root,row,hashes: types.SimpleNamespace(row=row)
    def ply_bytes(points):
        header=('ply\nformat binary_little_endian 1.0\n'
                'element vertex '+str(len(points))+'\nproperty float x\n'
                'property float y\nproperty float z\nend_header\n').encode()
        return header+np.asarray(points,dtype='<f4').tobytes()
    ft10._ply_bytes=ply_bytes
    monkeypatch.setitem(sys.modules,'ft10_merge_multiview',ft10)

    mod=types.ModuleType('scantopath.modules.reconstruction.application.live_pair')
    mod.cloud_from_live_packet=lambda packet,**kw: FakeView(
        packet.row['capture_id'],world+np.array([.0002*packet.row['sample_index'],0,0]))
    monkeypatch.setitem(sys.modules,mod.__name__,mod)

    ply_mod=types.ModuleType('scantopath.modules.viewer3d.infrastructure.ply_header')
    def inspect_ply(path):
        content=path.read_bytes().split(b'end_header\n',1)[0].decode('ascii')
        count=int(next(l.split()[-1] for l in content.splitlines() if l.startswith('element vertex')))
        return types.SimpleNamespace(vertex_count=count)
    ply_mod.inspect_ply=inspect_ply
    monkeypatch.setitem(sys.modules,ply_mod.__name__,ply_mod)

    out=tmp_path/'external';out.mkdir()
    folder=script.execute(sequence,cloud,out)
    stats=script.verify(folder)
    assert stats['accepted_views']==3
    assert stats['points']>100
    process=json.loads((folder/'processing_run.json').read_text())
    assert process['metric_gate']=='NOT_TESTED'
    assert process['sqlite_processing_run_registered'] is False
    assert process['input_capture_ids']==['cap0','cap1','cap2']
    assert process['source_raw_immutable'] is True
    registration=json.loads((folder/'registration_quality.json').read_text())
    assert registration['trust_level']=='PROVISIONAL_GEOMETRIC_CONSISTENCY_ONLY'
    assert registration['group_C_underside_registered'] is False
    # An altered artifact must not reopen, even if PLY still visually renders.
    with (folder/'normal_xyz.csv').open('ab') as f: f.write(b'unsafe\n')
    with pytest.raises(C1Error,match='C1_OUTPUT_CORRUPT'):
        script.verify(folder)
