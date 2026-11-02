"""FT-08.17 focused state machine tests; no camera, no GUI, no RAW store."""
from __future__ import annotations
from types import SimpleNamespace as NS

import numpy as np
import pytest

from scantopath.modules.reconstruction.application import sequence_tracking as sut


class FakeRaw:
    def __init__(self, i):
        self.metadata = NS(
            capture_id=f'capture{i}', measured=True,
            color=NS(frame_index=i, timestamp_us=1000000+i*150000),
            depth=NS(frame_index=i, timestamp_us=1000200+i*150000),
        )


def _result(shift=.01, *, accepted=True, reasons=()):
    pose = np.eye(4)
    pose[0, 3] = shift
    quality = NS(reject_reasons=reasons,
                 to_json=lambda: {'overlap': .81, 'inlier_rmse_m': .003,
                                  'accepted': accepted, 'reject_reasons': list(reasons)})
    return NS(accepted=accepted, T_world_depth_1=pose if accepted else None,
              quality=quality, backend='numpy_bounded_bruteforce')


def _views():
    v = NS(selected_points=500, source_ref={'isolation_status': 'CHARUCO_OBJECT_FOUND'})
    return v, v


def _setup(monkeypatch):
    monkeypatch.setattr(sut, 'RawRgbdCapture', FakeRaw)
    monkeypatch.setattr(sut, 'validate_live_pair', lambda a, b: None)


def test_three_frame_chain_in_anchor_world(monkeypatch):
    _setup(monkeypatch)
    a, b = _views()
    calls = []
    def processor(left, right, **kw):
        calls.append((left.metadata.capture_id, right.metadata.capture_id))
        assert kw['reference_mode'] == 'charuco'
        assert kw['config'].min_overlap == .28
        return a, b, _result()
    data = sut.track_sequence([FakeRaw(i) for i in range(3)], pair_processor=processor)
    assert calls == [('capture0', 'capture1'), ('capture1', 'capture2')]
    assert data['status'] == 'TRACKING'
    assert data['accepted_poses'] == 3
    assert [r['status'] for r in data['frames']] == ['ANCHOR', 'TRACKING', 'TRACKING']
    assert data['frames'][2]['T_world_depth'][0][3] == pytest.approx(.02)
    assert data['fusion_implemented'] is False


def test_reject_enters_lost_and_never_publishes_later_pose(monkeypatch):
    _setup(monkeypatch)
    a, b = _views()
    calls = []
    def processor(left, right, **kw):
        calls.append(1)
        return a, b, _result(accepted=False, reasons=('HIGH_REGISTRATION_RMSE',))
    data = sut.track_sequence([FakeRaw(i) for i in range(4)], pair_processor=processor)
    assert data['status'] == 'LOST'
    assert len(calls) == 1
    assert [x['status'] for x in data['frames']] == [
        'ANCHOR', 'LOST', 'LOST_NO_RECOVERY', 'LOST_NO_RECOVERY']
    assert all(x['T_world_depth'] is None for x in data['frames'][1:])


def test_stationary_frame_is_held_without_corrupting_reference(monkeypatch):
    _setup(monkeypatch)
    a, b = _views()
    calls = []
    def processor(left, right, **kw):
        calls.append((left.metadata.capture_id, right.metadata.capture_id))
        if len(calls) == 1:
            return a, b, _result(accepted=False, reasons=('NO_DISTINCT_VIEW_MOTION',))
        return a, b, _result()
    data = sut.track_sequence([FakeRaw(i) for i in range(3)], pair_processor=processor)
    assert data['frames'][1]['status'] == 'HELD_STATIONARY'
    assert data['frames'][1]['T_world_depth'] is None
    assert data['frames'][2]['status'] == 'TRACKING'
    assert calls == [('capture0','capture1'), ('capture0','capture2')]
    assert data['accepted_poses'] == 2


def test_invalid_se3_fails_closed(monkeypatch):
    _setup(monkeypatch)
    a, b = _views()
    def processor(left, right, **kw):
        obj = _result()
        obj.T_world_depth_1[0,0] = -2.0
        return a, b, obj
    data = sut.track_sequence([FakeRaw(i) for i in range(2)], pair_processor=processor)
    assert data['status'] == 'LOST'
    assert data['frames'][1]['reject_code'] == 'B02_POSE_NOT_SE3'


def test_backward_or_duplicate_index_lost(monkeypatch):
    _setup(monkeypatch)
    a, b = _views()
    obj = FakeRaw(1)
    obj.metadata.depth.frame_index = 0
    data = sut.track_sequence([FakeRaw(0), obj], pair_processor=lambda *a, **kw: (_ for _ in ()).throw(AssertionError('should not call')))
    assert data['frames'][1]['status'] == 'LOST'
    assert data['frames'][1]['reject_code'] == 'B02_NON_MONOTONIC_DEPTH_FRAME'


def test_input_bounds_and_no_false_metrology(monkeypatch):
    _setup(monkeypatch)
    with pytest.raises(ValueError, match='LENGTH'):
        sut.track_sequence([FakeRaw(0)])
    assert not sut._is_se3(np.ones((4, 4)))
    assert sut._is_se3(np.eye(4))


def test_sequence_evidence_hash_tamper_detection(monkeypatch, tmp_path):
    """Save/verify bounded RAW evidence through the existing B01 output guard."""
    import importlib.util
    from pathlib import Path
    script = Path(__file__).resolve().parents[3] / 'scripts' / 'b02_live_sequence.py'
    spec = importlib.util.spec_from_file_location('ft0817_script_test', script)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)

    # Stub only the already-proven safe output parent during this unit test.
    import sys
    infra = NS(_safe_output_parent=lambda path: path)
    monkeypatch.setitem(sys.modules,
        'scantopath.modules.reconstruction.infrastructure.live_artifact_writer', infra)

    class M:
        def model_dump_json(self, indent):
            return '{"schema_version": 2}'

    class P:
        metadata = M()
        color_mjpeg = b'\xff\xd8\xff\xd9'
        depth_y16_le = b'\x01\x00' * 8

    record = {'schema':'scantopath.ft08.17.sampled_pose_sequence.v1',
              'source_frame_count':2,'accepted_poses':2,'status':'TRACKING'}
    path = mod.save_evidence(tmp_path, [P(), P()], record)
    assert mod.verify_artifact(path)['verified_files'] == 7
    (path / 'frame_01_depth.y16').write_bytes(b'tampered')
    with pytest.raises(ValueError, match='INTEGRITY_FAILED'):
        mod.verify_artifact(path)
