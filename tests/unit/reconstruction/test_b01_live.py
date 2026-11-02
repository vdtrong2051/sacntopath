"""Small scope tests: a live view is new measured data, NOT old SQLite records."""
from __future__ import annotations
from dataclasses import dataclass
from pathlib import Path
from types import SimpleNamespace
import json

import numpy as np
import pytest

from scantopath.modules.reconstruction.application.contracts import (
    PairQuality, RegistrationConfig, RegistrationError, TwoViewResult,
)
from scantopath.modules.reconstruction.application import live_pair
from scantopath.modules.reconstruction.infrastructure.live_artifact_writer import (
    write_live_pair_artifact, verify_live_artifact,
)


@dataclass
class FakePacket:
    metadata: object
    color_mjpeg: bytes = b'newcolorbytes'
    depth_y16_le: bytes = b'newdepthbytes'


def sample(name: str, frame_id: int):
    metadata = SimpleNamespace(
        capture_id=name, session_id='live1', specimen_id='liveobj1',
        kind='ORBBEC', measured=True,
        color=SimpleNamespace(frame_index=frame_id),
        depth=SimpleNamespace(frame_index=frame_id, width=1280, height=800),
        device=SimpleNamespace(name='Gemini 2', pid=1648, serial=None),
        alignment_mode='disabled', depth_intrinsics='fixed_intrinsics',
        depth_distortion='none', depth_scale_m_per_unit=.001,
        model_dump_json=lambda indent: json.dumps({'capture_id': name}, indent=indent),
    )
    return FakePacket(metadata)


def test_duplicate_direct_live_frame_rejected(monkeypatch):
    monkeypatch.setattr(live_pair, 'RawRgbdCapture', FakePacket)
    with pytest.raises(RegistrationError, match='distinct'):
        live_pair.validate_live_pair(sample('a', 1), sample('a', 1))


def test_new_live_pair_allowed_without_store(monkeypatch):
    monkeypatch.setattr(live_pair, 'RawRgbdCapture', FakePacket)
    live_pair.validate_live_pair(sample('a', 1), sample('b', 2))


def test_live_artifact_accepted_has_new_sensor_evidence_and_pose(tmp_path):
    quality = PairQuality(.7, .7, .7, .004, 600, 2000, 2000, .2, .2,
                          .02, 4., True, ())
    matrix = np.eye(4)
    moved = np.eye(4); moved[0, 3] = .02
    r = TwoViewResult(quality, matrix, moved,
                      np.ones((20, 3)), np.ones((20, 3)) + .02, 'numpy_bounded_bruteforce')
    a, b = sample('a', 1), sample('b', 2)
    view = lambda n: SimpleNamespace(source_ref={'capture_id': n})
    folder = write_live_pair_artifact(tmp_path / 'new', packet0=a, packet1=b,
              view0=view('a'), view1=view('b'), result=r, config=RegistrationConfig())
    verified = verify_live_artifact(folder)
    assert verified['status'] == 'ACCEPTED'
    assert (folder / 'registered_measured.ply').is_file()
    assert (folder / 'view0_depth.y16').read_bytes() == a.depth_y16_le
    assert (folder / 'view1_depth.y16').read_bytes() == b.depth_y16_le
    assert (folder / 'poses.json').is_file()


def test_live_artifact_rejected_has_no_false_merged_cloud(tmp_path):
    quality = PairQuality(.1, .1, .1, .02, 20, 200, 200, .1, .1,
                          .8, 60., False, ('LOW_BIDIRECTIONAL_OVERLAP',))
    r = TwoViewResult(quality, np.eye(4), None, None, None, 'numpy_bounded_bruteforce')
    a, b = sample('a', 1), sample('b', 2)
    folder = write_live_pair_artifact(tmp_path / 'out', packet0=a, packet1=b,
          view0=SimpleNamespace(source_ref={'capture_id': 'a'}),
          view1=SimpleNamespace(source_ref={'capture_id': 'b'}),
          result=r, config=RegistrationConfig())
    assert verify_live_artifact(folder)['status'] == 'REJECTED'
    assert not (folder / 'registered_measured.ply').exists()
