"""FT-09.18 + FT-09.19: no camera/Qt/SDK, reuse FT-08.17 test contracts."""
from __future__ import annotations

from types import SimpleNamespace as NS

import numpy as np
import pytest

from scantopath.modules.reconstruction.application import sequence_tracking as sut


class Packet:
    def __init__(self, i):
        self.metadata = NS(
            capture_id=f'c{i}', measured=True,
            color=NS(frame_index=i+10, timestamp_us=1000000+i*160000),
            depth=NS(frame_index=i+10, timestamp_us=1000600+i*160000),
        )


def setup(monkeypatch):
    monkeypatch.setattr(sut, 'RawRgbdCapture', Packet)
    monkeypatch.setattr(sut, 'validate_live_pair', lambda a, b: None)


def pair(shift=.01, *, accepted=True, reasons=(), overlap=.90,
         rmse=.003, inliers=120, angle=0):
    T = np.eye(4)
    from math import radians, cos, sin
    v = radians(angle)
    T[:2, :2] = [[cos(v), -sin(v)], [sin(v), cos(v)]]
    T[0,3] = shift
    stats = {'overlap': overlap, 'inlier_rmse_m': rmse,
             'inlier_count': inliers, 'accepted': accepted,
             'reject_reasons': list(reasons)}
    q = NS(reject_reasons=reasons, overlap=overlap,
           inlier_rmse_m=rmse, inlier_count=inliers, to_json=lambda: stats)
    return NS(accepted=accepted, quality=q,
              T_world_depth_1=T if accepted else None,
              backend='numpy_bounded_bruteforce')


def views():
    v = NS(selected_points=16187,
           source_ref={'isolation_status':'CHARUCO_OBJECT_FOUND'})
    return v,v


def test_transient_degeneracy_then_recovered_against_last_trusted_keyframe(monkeypatch):
    setup(monkeypatch)
    a,b = views()
    calls=[]
    def processor(left,right,**kw):
        calls.append((left.metadata.capture_id,right.metadata.capture_id))
        if right.metadata.capture_id=='c2':
            return a,b,pair(accepted=False, reasons=('GEOMETRY_DEGENERATE',),
                            overlap=.823, rmse=.0025)
        return a,b,pair()
    data=sut.track_sequence([Packet(i) for i in range(4)],pair_processor=processor)
    assert [r['status'] for r in data['frames']] == ['ANCHOR','TRACKING','DEGRADED','RECOVERED']
    assert [r['accepted_for_trajectory'] for r in data['frames']] == [True,True,False,True]
    assert data['frames'][2]['T_world_depth'] is None
    assert data['frames'][2]['quality']['overlap']==.823
    assert calls == [('c0','c1'), ('c1','c2'), ('c1','c3')]
    assert data['frames'][3]['T_world_depth'][0][3] == pytest.approx(.02)
    assert data['frames'][3]['reference_sample_index'] == 1
    assert 'T_prev_depth_from_curr_depth' not in data['frames'][3]
    assert data['recovered_poses'] == 1
    assert data['recovery_implemented'] is True
    assert data['fusion_implemented'] is False
    assert data['metric_accuracy_verified'] is False


def test_multiple_bad_frames_enter_lost_then_continue_recovery(monkeypatch):
    setup(monkeypatch)
    a,b = views()
    attempts=[]
    def processor(left,right,**kw):
        attempts.append(right.metadata.capture_id)
        if right.metadata.capture_id in ('c1','c2'):
            return a,b,pair(accepted=False,reasons=('LOW_BIDIRECTIONAL_OVERLAP',),overlap=.12)
        return a,b,pair(shift=.08)
    data=sut.track_sequence([Packet(i) for i in range(4)],pair_processor=processor)
    assert [r['status'] for r in data['frames']] == ['ANCHOR','DEGRADED','LOST','RECOVERED']
    assert attempts==['c1','c2','c3']
    assert data['accepted_poses']==2
    assert data['frames'][3]['T_world_depth'][0][3] == pytest.approx(.08)


def test_near_stationary_accepted_does_not_add_redundant_pose(monkeypatch):
    setup(monkeypatch)
    a,b=views()
    refs=[]
    def processor(left,right,**kw):
        refs.append((left.metadata.capture_id,right.metadata.capture_id))
        if right.metadata.capture_id=='c1':
            return a,b,pair(shift=.003,angle=.3,overlap=.99,rmse=.001)
        return a,b,pair(shift=.018)
    data=sut.track_sequence([Packet(i) for i in range(3)],pair_processor=processor)
    assert [r['status'] for r in data['frames']] == ['ANCHOR','STATIONARY','TRACKING']
    assert data['frames'][1]['T_world_depth'] is None
    assert data['frames'][2]['T_world_depth'][0][3] == pytest.approx(.018)
    assert refs == [('c0','c1'),('c0','c2')]
    assert data['stationary_frames']==1


def test_bad_quality_rejection_cannot_be_mislabeled_stationary(monkeypatch):
    setup(monkeypatch)
    a,b=views()
    def processor(*args,**kw):
        return a,b,pair(accepted=False,reasons=('GEOMETRY_DEGENERATE','NO_DISTINCT_VIEW_MOTION'),
                        overlap=1.0,rmse=.001)
    record=sut.track_sequence([Packet(0),Packet(1)],pair_processor=processor)
    assert record['frames'][1]['status']=='DEGRADED'
    assert record['frames'][1]['T_world_depth'] is None


def test_recovery_can_use_earlier_accepted_keyframe_when_latest_has_no_overlap(monkeypatch):
    setup(monkeypatch)
    a,b=views()
    attempted=[]
    def processor(left,right,**kw):
        k=(left.metadata.capture_id,right.metadata.capture_id)
        attempted.append(k)
        if k in (('c1','c2'),('c1','c3')):
            return a,b,pair(accepted=False,reasons=('LOW_BIDIRECTIONAL_OVERLAP',),overlap=.2)
        if k==('c0','c3'):
            return a,b,pair(shift=.035)
        return a,b,pair(shift=.01)
    r=sut.track_sequence([Packet(i) for i in range(4)],pair_processor=processor)
    assert r['frames'][3]['status']=='RECOVERED'
    assert r['frames'][3]['reference_sample_index']==0
    assert r['frames'][3]['T_world_depth'][0][3]==pytest.approx(.035)
    assert ('c1','c3') in attempted and ('c0','c3') in attempted


def test_chronology_violation_fails_closed_but_does_not_stop_sampling(monkeypatch):
    setup(monkeypatch)
    a,b=views()
    packets=[Packet(i) for i in range(4)]
    packets[1].metadata.depth.frame_index=10
    got=[]
    def processor(left,right,**kw):
        got.append(right.metadata.capture_id)
        return a,b,pair(shift=.01)
    result=sut.track_sequence(packets,pair_processor=processor)
    assert result['frames'][1]['status']=='LOST'
    assert result['frames'][1]['reject_code']=='B02_NON_MONOTONIC_DEPTH_FRAME'
    assert result['frames'][2]['status']=='RECOVERED'
    assert got==['c2','c3']


def test_bad_se3_never_accepts_pose_even_if_reported_accepted(monkeypatch):
    setup(monkeypatch)
    a,b=views()
    def processor(*args,**kw):
        p=pair()
        p.T_world_depth_1[0,0]=2.0
        return a,b,p
    r=sut.track_sequence([Packet(i) for i in range(3)],pair_processor=processor)
    assert all(x['T_world_depth'] is None for x in r['frames'][1:])
    assert r['frames'][1]['status']=='LOST'
    assert r['frames'][1]['reject_code']=='B02_POSE_NOT_SE3'


def test_fixed_bounds_and_policy_validation(monkeypatch):
    setup(monkeypatch)
    with pytest.raises(ValueError,match='FT09_POLICY_INVALID'):
        sut.TrackingQualityPolicy(max_recovery_references=0)
    with pytest.raises(ValueError,match='FT09_POLICY_INVALID'):
        sut.TrackingQualityPolicy(stationary_min_overlap=1.1)
    with pytest.raises(ValueError,match='B02_SEQUENCE_LENGTH_INVALID'):
        sut.track_sequence([Packet(0)])


def test_event_hook_emits_every_frame_even_after_lost(monkeypatch):
    setup(monkeypatch)
    a,b=views()
    events=[]
    def processor(*args,**kw):
        return a,b,pair(accepted=False,reasons=('HIGH_REGISTRATION_RMSE',),overlap=.02)
    r=sut.track_sequence([Packet(i) for i in range(5)],pair_processor=processor,
                         on_event=events.append)
    assert len(events)==5
    assert [x['sample_index'] for x in events]==list(range(5))
    assert r['source_frame_count']==5
    assert r['accepted_poses']==1
    assert r['status']=='LOST'
    assert all(not x['accepted_for_trajectory'] for x in events[1:])


def test_b02_reprocess_cli_option_is_explicit():
    import importlib.util
    from pathlib import Path
    path = Path(__file__).resolve().parents[3] / 'scripts' / 'b02_live_sequence.py'
    spec = importlib.util.spec_from_file_location('_ft09_b02_replay_parser', path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    args = mod.parser().parse_args(['--input-sequence-artifact', 'some_b02_folder',
                                    '--out', 'a_different_folder'])
    assert str(args.input_sequence_artifact) == 'some_b02_folder'
    assert args.input_artifact is None


def test_b02_verified_replay_does_not_modify_source_and_rejects_tampering(monkeypatch, tmp_path):
    import importlib.util
    import json
    import sys
    from pathlib import Path
    script = Path(__file__).resolve().parents[3] / 'scripts' / 'b02_live_sequence.py'
    spec = importlib.util.spec_from_file_location('_ft09_b02_replay_test', script)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)

    class M:
        def __init__(self, i):
            self.i = i
            self.capture_id = f'c{i}'
            self.depth = NS(frame_index=i+20, timestamp_us=100000+i*100000)
        def model_dump_json(self, indent):
            return json.dumps({'idx': self.i})

    class Model:
        @staticmethod
        def model_validate_json(raw):
            return M(json.loads(raw)['idx'])

    class R:
        def __init__(self, metadata, color_mjpeg, depth_y16_le):
            self.metadata = metadata
            self.color_mjpeg = color_mjpeg
            self.depth_y16_le = depth_y16_le

    from types import ModuleType
    raw_mod = ModuleType('scantopath.acquisition.raw_rgbd')
    raw_mod.RawRgbdCapture = R
    meta_mod = ModuleType('scantopath.domain.raw_rgbd')
    meta_mod.RawRgbdCaptureMetadataV2 = Model
    infra_mod = ModuleType('scantopath.modules.reconstruction.infrastructure.live_artifact_writer')
    infra_mod._safe_output_parent = lambda p: p
    pair_mod = ModuleType('scantopath.modules.reconstruction.application.live_pair')
    pair_mod.validate_live_pair = lambda a,b: None
    for key, value in (('scantopath.acquisition.raw_rgbd',raw_mod),
                       ('scantopath.domain.raw_rgbd',meta_mod),
                       ('scantopath.modules.reconstruction.infrastructure.live_artifact_writer',infra_mod),
                       ('scantopath.modules.reconstruction.application.live_pair',pair_mod)):
        monkeypatch.setitem(sys.modules,key,value)

    packets = [R(M(i),b'\xff\xd8\xff\xd9',b'\x01\x00'*16) for i in range(3)]
    record = {'schema':'scantopath.ft08.17.sampled_pose_sequence.v1',
              'source_frame_count':3,'accepted_poses':2,'status':'TRACKING'}
    folder = mod.save_evidence(tmp_path, packets, record)
    before = sorted((p.name,mod._hash_file(p)) for p in folder.iterdir())
    restored = mod._verified_b02_sequence(folder)
    assert [p.metadata.capture_id for p in restored] == ['c0','c1','c2']
    assert before == sorted((p.name,mod._hash_file(p)) for p in folder.iterdir())
    (folder/'frame_01_depth.y16').write_bytes(b'corrupt')
    with pytest.raises(ValueError, match='INTEGRITY_FAILED'):
        mod._verified_b02_sequence(folder)
