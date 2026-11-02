"""HF03 end-to-end extended frame budget (pure CPU, no Gemini/Qt)."""
from __future__ import annotations
import importlib.util
from hashlib import sha256
import json
from pathlib import Path
from types import SimpleNamespace as NS

import numpy as np
import pytest

from scantopath.modules.reconstruction.application import sequence_tracking as tracker
from scantopath.modules.reconstruction.application.multiview_accumulation import validated_trajectory, MultiviewError
from scantopath.modules.reconstruction.application.keyframe_sampling import retain_spaced_frame


class Packet:
    def __init__(self, i):
        self.metadata = NS(
            capture_id=f'hf03_{i}', measured=True,
            color=NS(frame_index=i+10, timestamp_us=2_000_000+i*1200000),
            depth=NS(frame_index=i+10, timestamp_us=2_000_300+i*1200000),
        )


def _mock_pair(*_args, **_kwargs):
    T=np.eye(4)
    T[0,3]=.012
    metrics={'overlap':.94,'inlier_rmse_m':.002,'inlier_count':500,'accepted':True,'reject_reasons':[]}
    q=NS(reject_reasons=(),overlap=.94,inlier_rmse_m=.002,inlier_count=500,to_json=lambda:metrics)
    v=NS(selected_points=3000,source_ref={'isolation_status':'CHARUCO_OBJECT_FOUND'})
    return v,v,NS(accepted=True,quality=q,T_world_depth_1=T,backend='fixture')


@pytest.mark.parametrize('n',[20,21,64,88,96])
def test_ft09_to_ft10_extended_trajectory(monkeypatch,n):
    monkeypatch.setattr(tracker,'RawRgbdCapture',Packet)
    monkeypatch.setattr(tracker,'validate_live_pair',lambda a,b:None)
    frames=[Packet(i) for i in range(n)]
    out=tracker.track_sequence(frames,pair_processor=_mock_pair)
    yes,no=validated_trajectory(out)
    assert len(yes)==n and no==[]
    assert [r['sample_index'] for r in yes]==list(range(n))
    assert out['frames'][-1]['T_world_depth'][0][3]==pytest.approx((n-1)*.012)


def test_reject_more_than_96(monkeypatch):
    monkeypatch.setattr(tracker,'RawRgbdCapture',Packet)
    with pytest.raises(ValueError,match='B02_SEQUENCE_LENGTH_INVALID'):
        tracker.track_sequence([Packet(i) for i in range(97)])
    rows=[{'sample_index':i,'capture_id':f'c{i}','depth_frame_index':i+1,
           'depth_timestamp_us':1000+i,'accepted_for_trajectory':i==0,
           'status':'ANCHOR' if i==0 else 'DEGRADED',
           'T_world_depth':np.eye(4).tolist() if i==0 else None}
          for i in range(97)]
    report={'schema':'scantopath.ft08.17.sampled_pose_sequence.v1',
            'ft09_extension':'scantopath.ft09.quality_recovery.v1',
            'units':'m','trajectory_frame':'depth_optical_of_sample_0',
            'matrix_convention':'T_A_B maps coordinates B into A; column homogeneous vectors',
            'metric_accuracy_verified':False,'fusion_implemented':False,
            'source_frame_count':97,'accepted_poses':1,'frames':rows}
    with pytest.raises(MultiviewError,match='FT10_SEQUENCE_COUNT_INVALID'):
        validated_trajectory(report)


def test_88_frame_b02_sha_verification_and_tamper(tmp_path):
    script=Path(__file__).resolve().parents[3]/'scripts'/'b02_live_sequence.py'
    spec=importlib.util.spec_from_file_location('hf03_b02_verifier',script)
    module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
    root=tmp_path/'b02_sequence_88';root.mkdir()
    hashes={}
    for i in range(88):
        for suffix in ('_color.mjpg','_depth.y16','_metadata.json'):
            name=f'frame_{i:02d}'+suffix
            content=(name+' fixture').encode('utf8')
            (root/name).write_bytes(content)
            hashes[name]=sha256(content).hexdigest()
    record={'schema':'scantopath.ft08.17.sampled_pose_sequence.v1',
            'source_frame_count':88,'accepted_poses':45,'status':'TRACKING'}
    (root/'tracking_sequence.json').write_text(json.dumps(record),encoding='utf8')
    hashes['tracking_sequence.json']=sha256((root/'tracking_sequence.json').read_bytes()).hexdigest()
    (root/'sha256_manifest.json').write_text(json.dumps({
        'schema':'scantopath.ft08.17.sha256_manifest.v1','files':hashes}),encoding='utf8')
    result=module.verify_artifact(root)
    assert result['source_frame_count']==88 and result['verified_files']==265
    (root/'frame_50_depth.y16').write_bytes(b'tampered')
    with pytest.raises(ValueError,match='INTEGRITY_FAILED'):
        module.verify_artifact(root)


def test_online_88_keeps_all_and_120_stays_bounded():
    frames=[]
    originals=[Packet(i) for i in range(88)]
    for packet in originals:retain_spaced_frame(frames,packet)
    assert all(a is b for a,b in zip(frames,originals))
    for i in range(88,120):retain_spaced_frame(frames,Packet(i))
    assert len(frames)==96
    assert frames[0] is originals[0]
    assert frames[-1].metadata.depth.frame_index==129
    assert all(frames[i].metadata.depth.frame_index < frames[i+1].metadata.depth.frame_index
               for i in range(len(frames)-1))
