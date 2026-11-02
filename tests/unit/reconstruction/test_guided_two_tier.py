"""Minimal fake-RAW contract tests: no camera, SQLite or QThread."""
import json
from types import SimpleNamespace
import numpy as np
import pytest

from scantopath.modules.reconstruction.application.guided_two_tier import (
    track_two_tier, TwoTierError,
)


def packet(i):
    md = SimpleNamespace(
        capture_id=f'capture_{i}',
        depth=SimpleNamespace(timestamp_us=10_000+i*1_000,frame_index=i+100),
    )
    return SimpleNamespace(metadata=md)


def tracker(packets):
    rows=[]
    for i,p in enumerate(packets):
        T=np.eye(4);T[0,3]=i*.01
        rows.append({'sample_index':i,'capture_id':p.metadata.capture_id,
                     'depth_frame_index':p.metadata.depth.frame_index,
                     'depth_timestamp_us':p.metadata.depth.timestamp_us,
                     'status':'ANCHOR' if i==0 else 'TRACKING',
                     'accepted_for_trajectory':True,'T_world_depth':T.tolist()})
    return {'schema':'scantopath.ft08.17.sampled_pose_sequence.v1',
            'ft09_extension':'scantopath.ft09.quality_recovery.v1',
            'units':'m','trajectory_frame':'depth_optical_of_sample_0',
            'matrix_convention':'T_A_B maps coordinates B into A; column homogeneous vectors',
            'metric_accuracy_verified':False,'fusion_implemented':False,
            'source_frame_count':len(packets),'accepted_poses':len(packets),
            'status':'TRACKING','frames':rows}


def test_independent_tiers_bridge_in_same_world(monkeypatch):
    import scantopath.modules.reconstruction.application.live_pair as lp
    monkeypatch.setattr(lp,'validate_live_pair',lambda a,b:None)
    def anchor(p):
        T=np.eye(4)
        if p.metadata.capture_id=='capture_3':T[0,3]=.1
        return T
    rows=track_two_tier([packet(i) for i in range(6)],3,tracker=tracker,
                        board_provider=anchor)
    assert rows['two_tier']['tier_1']['frames']==3
    assert rows['two_tier']['tier_2']['frames']==3
    assert rows['accepted_poses']==6
    assert np.isclose(rows['frames'][3]['T_world_depth'][0][3],-.1)
    assert rows['frames'][3]['status']=='TRACKING'
    assert rows['frames'][3]['tier']==2
    json.dumps(rows,allow_nan=False)


def test_reject_invalid_board(monkeypatch):
    import scantopath.modules.reconstruction.application.live_pair as lp
    monkeypatch.setattr(lp,'validate_live_pair',lambda a,b:None)
    with pytest.raises(TwoTierError,match='TWO_TIER_BOARD_ANCHOR_INVALID'):
        track_two_tier([packet(i) for i in range(4)],2,tracker=tracker,
                       board_provider=lambda x:np.zeros((4,4)))


def test_reject_sample_budget():
    with pytest.raises(TwoTierError,match='TWO_TIER_SAMPLE_BUDGET_INVALID'):
        track_two_tier([packet(i) for i in range(4)],1,tracker=tracker)


def test_reject_nonmonotonic_raw(monkeypatch):
    import scantopath.modules.reconstruction.application.live_pair as lp
    monkeypatch.setattr(lp,'validate_live_pair',lambda a,b:None)
    seq=[packet(i) for i in range(4)]
    seq[3].metadata.depth.timestamp_us=seq[2].metadata.depth.timestamp_us
    with pytest.raises(TwoTierError,match='TWO_TIER_NON_MONOTONIC_RAW'):
        track_two_tier(seq,2,tracker=tracker)
