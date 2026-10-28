"""R5.3 native VTK picking/provenance and bounded interaction protocol tests."""
from __future__ import annotations

from pathlib import Path
from tempfile import TemporaryDirectory

import pytest

from scantopath.modules.viewer3d.infrastructure.resident_poc.client import ResidentRenderClient, RenderHostError
from scantopath.modules.viewer3d.infrastructure.resident_poc.async_session import CoalescingRenderSession
from scantopath.modules.viewer3d.infrastructure.resident_poc.protocol import decode_request


def _mesh(p: Path):
    p.write_text('ply\nformat ascii 1.0\nelement vertex 4\nproperty float x\nproperty float y\n'
                 'property float z\nelement face 1\nproperty list uchar int vertex_indices\nend_header\n'
                 '-1 -1 0\n1 -1 0\n1 1 0\n-1 1 0\n4 0 1 2 3\n', encoding='ascii')


def _points(p: Path):
    p.write_text('ply\nformat ascii 1.0\nelement vertex 5\nproperty float x\n'
                 'property float y\nproperty float z\nend_header\n'
                 '0 0 0\n1 0 0\n0 1 0\n-1 0 0\n0 -1 0\n', encoding='ascii')


def test_r53_protocol_bounded_and_strict():
    correct = b'{"id":1,"op":"pick","u":0.5,"v":0.5,"scene_revision":1,"frame_revision":1}\n'
    assert decode_request(correct)['u'] == .5
    invalid = [
        correct[:-1],
        b'{"id":1,"op":"pick","u":1.2,"v":0.5,"scene_revision":1,"frame_revision":1}\n',
        b'{"id":1,"op":"pick","u":true,"v":0.5,"scene_revision":1,"frame_revision":1}\n',
        b'{"id":1,"op":"pick","u":0.5,"v":0.5,"scene_revision":1,"frame_revision":-1}\n',
        b'{"id":1,"op":"set_visibility","visible":1}\n',
        b'{"id":1,"op":"set_visibility","visible":true,"extra":2}\n',
    ]
    for bad in invalid:
        with pytest.raises((ValueError, TypeError)):
            decode_request(bad)
    assert decode_request(b'{"id":3,"op":"set_visibility","visible":false}\n')['visible'] is False


def test_r53_mesh_cell_pick_and_stale_scene_guard(tmp_path):
    path = tmp_path / 'mesh.ply'
    _mesh(path)
    before = path.read_bytes()
    with ResidentRenderClient(320, 240, timeout=45) as cli:
        opened = cli.open_source(path.resolve())
        result = cli.request('pick', u=.5, v=.5, scene_revision=opened['scene_revision'],
                             frame_revision=opened['frame_revision'])
        assert result['hit'] is True, result
        assert result['kind'] == 'face' and result['element_id'] == 0
        assert abs(result['xyz'][2]) < 1e-6
        assert result['source_sha256'] == opened['source_sha256']
        with pytest.raises(RenderHostError, match='STALE_PICK_FRAME'):
            cli.request('pick', u=.5, v=.5, scene_revision=opened['scene_revision'], frame_revision=0)
        hidden = cli.request('set_visibility', visible=False)
        assert hidden['visible'] is False
        missed = cli.request('pick', u=.5, v=.5, scene_revision=opened['scene_revision'],
                             frame_revision=hidden['frame_revision'])
        assert missed['hit'] is False
        visible = cli.request('set_visibility', visible=True)
        assert visible['frame_revision'] > hidden['frame_revision']
        again = cli.request('pick', u=.5, v=.5, scene_revision=opened['scene_revision'],
                            frame_revision=visible['frame_revision'])
        assert again['hit'] is True
        assert cli.request('status')['open_count'] == 1
    assert path.read_bytes() == before


def test_r53_point_pick_and_wrong_source_revision(tmp_path):
    point = tmp_path / 'points.ply'; _points(point)
    mesh = tmp_path / 'mesh.ply'; _mesh(mesh)
    with ResidentRenderClient(320, 240, timeout=45) as cli:
        one = cli.open_source(point.resolve())
        picked = cli.request('pick', u=.5, v=.5, scene_revision=one['scene_revision'],
                              frame_revision=one['frame_revision'])
        assert picked['hit'] is True, picked
        assert picked['kind'] == 'point' and picked['element_id'] == 0
        assert tuple(picked['xyz']) == (0., 0., 0.)
        two = cli.open_source(mesh.resolve())
        assert two['scene_revision'] > one['scene_revision']
        with pytest.raises(RenderHostError, match='STALE_PICK_FRAME'):
            cli.request('pick', u=.5, v=.5, scene_revision=one['scene_revision'],
                        frame_revision=one['frame_revision'])


def test_r53_ack_session_pick_and_layer(tmp_path):
    path = tmp_path / 'mesh.ply';_mesh(path)
    s = CoalescingRenderSession(320, 240, timeout=45)
    s.start().result(timeout=30)
    try:
        opened = s.open_source(path.resolve()).result(timeout=90)
        frame = s.next_frame(timeout=5)
        picked = s.pick(.5, .5, frame.scene_revision, frame.frame_revision).result(timeout=45)
        assert picked['hit'] is True and picked['kind'] == 'face'
        s.set_visibility(False).result(timeout=45)
        blank = s.next_frame(timeout=10)
        assert blank.frame_revision > frame.frame_revision
        no_hit = s.pick(.5, .5, blank.scene_revision, blank.frame_revision).result(timeout=45)
        assert no_hit['hit'] is False
        s.set_visibility(True).result(timeout=45)
        visible = s.next_frame(timeout=10)
        assert visible.frame_revision > blank.frame_revision
        assert s.statistics['frames_dropped'] == 0
        assert opened['point_count'] == 4
    finally:
        s.stop(timeout=5)


def test_r53_no_qt_import_from_worker():
    import ast
    folder = Path(__file__).resolve().parents[3] / 'src/scantopath/modules/viewer3d/infrastructure/resident_poc'
    for path in folder.glob('*.py'):
        tree = ast.parse(path.read_text(encoding='utf-8'))
        found = [x.module for x in ast.walk(tree) if isinstance(x, ast.ImportFrom) and x.module]
        found += [a.name for x in ast.walk(tree) if isinstance(x, ast.Import) for a in x.names]
        assert not any(x.startswith(('PySide6', 'scantopath.ui')) for x in found)


def test_r53_grid_protocol_rejects_unknown_modes_and_untyped_flags():
    assert decode_request(b'{"id":1,"op":"set_grid","enabled":true,"mode":"xy"}\n')['mode'] == 'xy'
    assert decode_request(b'{"id":2,"op":"set_grid","enabled":false,"mode":"base"}\n')['enabled'] is False
    for raw in (
        b'{"id":1,"op":"set_grid","enabled":1,"mode":"xy"}\n',
        b'{"id":1,"op":"set_grid","enabled":true,"mode":"world"}\n',
        b'{"id":1,"op":"set_grid","enabled":true,"mode":"xy","path":"evil"}\n',
    ):
        with pytest.raises((ValueError, TypeError)):
            decode_request(raw)


def test_r53_reference_grid_is_not_pickable_or_source_mutation(tmp_path):
    import hashlib
    path = tmp_path / 'grid.ply'; _mesh(path)
    digest = hashlib.sha256(path.read_bytes()).hexdigest()
    with ResidentRenderClient(320, 240, timeout=45) as cli:
        opened = cli.open_source(path.resolve())
        pid = cli.pid
        after = cli.request('set_grid',enabled=False,mode='xy')
        assert after['grid_enabled'] is False
        assert after['frame_revision'] > opened['frame_revision']
        after = cli.request('set_grid',enabled=True,mode='base')
        assert after['grid_mode'] == 'base'
        picked = cli.request('pick', u=.5,v=.5,scene_revision=opened['scene_revision'],
                             frame_revision=after['frame_revision'])
        assert picked['hit'] and picked['kind']=='face' and picked['element_id']==0
        assert cli.pid == pid and cli.request('status')['open_count'] == 1
    assert hashlib.sha256(path.read_bytes()).hexdigest() == digest


def test_r53_async_grid_ack_never_reuses_stale_frame(tmp_path):
    path = tmp_path / 'grid_async.ply'; _mesh(path)
    s=CoalescingRenderSession(320,240,timeout=45)
    s.start().result(timeout=30)
    try:
        s.open_source(path.resolve()).result(timeout=90)
        first=s.next_frame(timeout=10)
        second_info=s.set_grid(False,'xy').result(timeout=30)
        second=s.next_frame(timeout=10)
        assert second_info['grid_enabled'] is False
        assert second.scene_revision == first.scene_revision
        assert second.frame_revision > first.frame_revision
        assert s.statistics['frames_dropped']==0
    finally:
        s.stop(timeout=5)
