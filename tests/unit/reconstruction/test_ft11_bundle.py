"""FT11 portable bundle round-trip / tampering tests, no camera/Qt required."""
import importlib.util
import json
from hashlib import sha256
from pathlib import Path
import struct
import sys
import types

import pytest

SCRIPT = Path(__file__).resolve().parents[3] / 'scripts' / 'ft11_bundle.py'


def load():
    spec = importlib.util.spec_from_file_location('ft11_bundle_test', SCRIPT)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def ply(rgb=False):
    props = 'property uchar red\nproperty uchar green\nproperty uchar blue\n' if rgb else ''
    header = (f'ply\nformat binary_little_endian 1.0\nelement vertex 1\n'
              f'property float x\nproperty float y\nproperty float z\n{props}end_header\n').encode()
    return header + struct.pack('<fff', 1., 2., 3.) + (b'\x20\x60\xff' if rgb else b'')


def write_j(path, obj):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(obj), encoding='utf-8')


def fixture_bundle(tmp_path):
    m=load()
    folder=tmp_path/'bundle'
    folder.mkdir()
    for name, data in [('cloud/merged_measured.ply', ply()),
                       ('cloud/debug_view_colored.ply', ply(True))]:
        p=folder/name; p.parent.mkdir(parents=True, exist_ok=True); p.write_bytes(data)
    track={'source_frame_count': 3, 'accepted_poses': 2, 'frames': []}
    write_j(folder/'poses/tracking_sequence.json', track)
    track_hash=m.sha_file(folder/'poses/tracking_sequence.json')
    write_j(folder/'reports/accumulation_report.json', {
        'schema': 'scantopath.ft10.multiview.v1',
        'source_tracking_record_sha256': track_hash,
        'accepted_view_count': 2, 'source_frame_count': 3,
        'merged_measured_points': 1, 'world_frame': 'depth_optical_of_sample_0',
        'units': 'm',
    })
    write_j(folder/'reconstruction.json', {
        'schema':m.SCHEMA, 'points':1,'accepted_views':2,
        'world_frame':'depth_optical_of_sample_0','units':'m',
        'metric_accuracy_verified':False,
    })
    write_j(folder/'sha256_manifest.json', {
        'schema':m.MANIFEST_SCHEMA,
        'files':{name:m.sha_file(folder/name) for name in sorted(set(m.FILES)|{'reconstruction.json'})},
    })
    return folder


@pytest.fixture(autouse=True)
def stub_viewer_if_missing(monkeypatch):
    try:
        from scantopath.modules.viewer3d.infrastructure.ply_header import inspect_ply
        return
    except ImportError:
        pass
    names = ['scantopath', 'scantopath.modules', 'scantopath.modules.viewer3d',
             'scantopath.modules.viewer3d.infrastructure',
             'scantopath.modules.viewer3d.infrastructure.ply_header']
    for n in names:
        pkg = types.ModuleType(n)
        pkg.__path__=[]
        monkeypatch.setitem(sys.modules,n,pkg)
    def inspect_ply(path):
        data = Path(path).read_bytes().split(b'end_header\n',1)[0].decode('ascii')
        return types.SimpleNamespace(vertex_count=int(data.split('element vertex ')[1].split('\n')[0]),
                                    has_rgb='property uchar red' in data)
    sys.modules[names[-1]].inspect_ply=inspect_ply


def test_verified_bundle(tmp_path):
    folder=fixture_bundle(tmp_path)
    result=load().verify_bundle(folder)
    assert (result['points'],result['accepted_views'],result['source_frames'])==(1,2,3)
    assert result['metric_accuracy_verified'] is False


def test_detect_tampered_ply(tmp_path):
    folder=fixture_bundle(tmp_path)
    with (folder/'cloud/merged_measured.ply').open('ab') as fd: fd.write(b'!')
    m=load()
    with pytest.raises(m.BundleError,match='HASH_MISMATCH'):
        m.verify_bundle(folder)


def test_reject_added_file(tmp_path):
    folder=fixture_bundle(tmp_path)
    (folder/'unexpected.txt').write_text('x')
    m=load()
    with pytest.raises(m.BundleError,match='FILESET_CHANGED'):
        m.verify_bundle(folder)


def test_reject_missing_pose(tmp_path):
    folder=fixture_bundle(tmp_path)
    (folder/'poses/tracking_sequence.json').unlink()
    m=load()
    with pytest.raises(m.BundleError,match='FILESET_CHANGED'):
        m.verify_bundle(folder)


def test_reject_modified_pose_even_if_manifest_rehashed(tmp_path):
    folder=fixture_bundle(tmp_path)
    track=folder/'poses/tracking_sequence.json'
    track.write_text('{"source_frame_count":4,"accepted_poses":2}')
    m=load()
    manifest=json.loads((folder/'sha256_manifest.json').read_text())
    manifest['files']['poses/tracking_sequence.json']=m.sha_file(track)
    write_j(folder/'sha256_manifest.json',manifest)
    with pytest.raises(m.BundleError,match='PROVENANCE_MISMATCH'):
        m.verify_bundle(folder)


def test_reject_symlink(tmp_path):
    folder=fixture_bundle(tmp_path)
    target=folder/'cloud/merged_measured.ply'
    copy=tmp_path/'real.ply'
    copy.write_bytes(target.read_bytes())
    target.unlink()
    try: target.symlink_to(copy)
    except (OSError,NotImplementedError): pytest.skip('symlinks unavailable')
    m=load()
    with pytest.raises(m.BundleError,match='SYMLINK'):
        m.verify_bundle(folder)


def test_fail_closed_source_without_raw(tmp_path):
    m=load()
    a=tmp_path/'sequence'; b=tmp_path/'cloud'; o=tmp_path/'output'
    for p in (a,b,o): p.mkdir()
    with pytest.raises((m.BundleError,ImportError,ValueError,OSError)):
        m.export_bundle(a,b,o)


def test_export_then_reopen_without_source_raw(tmp_path, monkeypatch):
    m=load()
    source=tmp_path/'source'; cloud=tmp_path/'cloud'; out=tmp_path/'out'
    for d in (source,cloud,out): d.mkdir()
    tracking={'source_frame_count':3,'accepted_poses':2,'frames':[]}
    write_j(source/'tracking_sequence.json',tracking)
    hash_tracking=m.sha_file(source/'tracking_sequence.json')
    for name,blob in [('merged_measured.ply',ply()),('debug_view_colored.ply',ply(True))]:
        (cloud/name).write_bytes(blob)
    write_j(cloud/'accumulation_report.json',{
        'schema':'scantopath.ft10.multiview.v1',
        'source_tracking_record_sha256':hash_tracking,
        'accepted_view_count':2,'source_frame_count':3,
        'merged_measured_points':1, 'world_frame':'depth_optical_of_sample_0',
        'units':'m', 'pose_source':'FT09_ACCEPTED_SE3_NOT_METRIC_VERIFIED',
        'source_manifest_sha256':'a'*64,
    })
    monkeypatch.setitem(sys.modules,'b02_live_sequence',
                        types.SimpleNamespace(verify_artifact=lambda x:{'verified_files':0}))
    monkeypatch.setitem(sys.modules,'ft10_merge_multiview',
                        types.SimpleNamespace(verify_output=lambda x:{'points':1}))
    folder=m.export_bundle(source,cloud,out)
    # The new bundle is portable even when the RAW and accumulation folders are gone.
    import shutil
    shutil.rmtree(source)
    shutil.rmtree(cloud)
    result=m.verify_bundle(folder)
    assert result['source_frames']==3 and result['points']==1
    assert not (folder/'raw').exists()
    assert json.loads((folder/'reconstruction.json').read_text())['raw_included'] is False
