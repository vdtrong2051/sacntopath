from __future__ import annotations
from hashlib import sha256
from pathlib import Path
import json
import numpy as np
import pytest
from scantopath.modules.reconstruction.application.contracts import (
    RegistrationConfig, InputCloud, RegistrationError)
from scantopath.modules.reconstruction.application.two_view_registration import register_two_views
from scantopath.modules.reconstruction.infrastructure.artifact_writer import write_pair_artifact


def test_accepted_pair_has_pose_and_consistent_checksums(tmp_path):
    store = tmp_path / 'store'; store.mkdir()
    output = tmp_path / 'outside'
    rng = np.random.default_rng(4)
    points = rng.uniform(-0.11, 0.11, size=(2500, 3)) + [0, 0, 0.85]
    p0 = InputCloud('a', points, 'f' * 64, ())
    p1 = InputCloud('b', points + [0.014, 0, 0], 'f' * 64, ())
    result = register_two_views(p0, p1)
    assert result.accepted, result.quality.reject_reasons
    src = lambda n: {'capture_id': n, 'calibration_fingerprint': 'f'*64}
    destination = write_pair_artifact(output, store_root=store, source0=src('a'),
                                      source1=src('b'), result=result,
                                      config=RegistrationConfig())
    record = json.loads((destination / 'registration_record.json').read_text('utf-8'))
    assert record['state'] == 'ACCEPTED'
    assert record['metric_accuracy_verified'] is False
    assert record['processing_run_registered_in_sqlite'] is False
    assert set(record['output_sha256']) == {'registered_measured.ply', 'debug_pair_overlay.ply', 'poses.json'}
    for name, digest in record['output_sha256'].items():
        assert sha256((destination / name).read_bytes()).hexdigest() == digest
    assert 'T_world_depth_1' in json.loads((destination / 'poses.json').read_text('utf-8'))


def test_cannot_write_unregistered_reconstruction_inside_raw_store(tmp_path):
    store = tmp_path / 'store'; store.mkdir()
    rng = np.random.default_rng(4)
    p = rng.uniform(-.1, .1, size=(2000, 3)) + [0, 0, .8]
    result = register_two_views(InputCloud('0', p, '0'*64, ()),
                                 InputCloud('1', p + [0.014, 0, 0], '0'*64, ()))
    assert result.accepted
    with pytest.raises(RegistrationError, match='outside RAW store'):
        write_pair_artifact(store / 'derived', store_root=store,
                            source0={'capture_id':'0'}, source1={'capture_id':'1'},
                            result=result, config=RegistrationConfig())
    assert not (store / 'derived' / 'registration_record.json').exists()


def test_rejected_pair_writes_reject_record_only(tmp_path):
    store = tmp_path / 'store'; store.mkdir()
    rng = np.random.default_rng(18)
    p0 = rng.uniform(-.09, .09, size=(1500, 3)) + [0, 0, .8]
    p1 = rng.uniform(1.5, 1.8, size=(1500, 3))
    result = register_two_views(InputCloud('a', p0, 'f'*64, ()),
                                 InputCloud('b', p1, 'f'*64, ()))
    assert not result.accepted
    out = write_pair_artifact(tmp_path / 'out', store_root=store,
            source0={'capture_id':'a'}, source1={'capture_id':'b'},
            result=result, config=RegistrationConfig())
    assert {p.name for p in out.iterdir()} == {'registration_record.json'}
    doc = json.loads((out / 'registration_record.json').read_text('utf-8'))
    assert doc['state'] == 'REJECTED'
    assert doc['registration_quality']['reject_reasons']
