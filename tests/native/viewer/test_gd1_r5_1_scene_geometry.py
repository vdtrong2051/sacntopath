"""R5.1: scene source, vertex-only and polygon meshes, provenance, IPC compatibility."""
from __future__ import annotations

import hashlib
from pathlib import Path

import pytest

from scantopath.modules.viewer3d.application.scene_contracts import (
    SceneDescriptor, SceneSelectionRef, SceneSource,
)
from scantopath.modules.viewer3d.infrastructure.resident_poc.client import (
    ResidentRenderClient, RenderHostError,
)
from scantopath.modules.viewer3d.infrastructure.resident_poc.async_session import CoalescingRenderSession
from scantopath.modules.viewer3d.infrastructure.resident_poc.protocol import decode_request


def _ply(path: Path, *, faces: bool = False, rgb: bool = False) -> Path:
    data = ('ply\nformat ascii 1.0\nelement vertex 4\n'
            'property float x\nproperty float y\nproperty float z\n')
    if rgb:
        data += 'property uchar red\nproperty uchar green\nproperty uchar blue\n'
    if faces:
        data += 'element face 1\nproperty list uchar int vertex_indices\n'
    data += 'end_header\n'
    for row in ((0, 0, 0), (1, 0, 0), (1, 1, 0), (0, 1, 0)):
        data += ' '.join(map(str, row)) + (' 255 0 0' if rgb else '') + '\n'
    if faces:
        data += '4 0 1 2 3\n'
    path.write_text(data, encoding='ascii')
    return path


def _obj(path: Path) -> Path:
    path.write_text('o Plane\nv 0 0 0\nv 1 0 0\nv 1 1 0\nv 0 1 0\nf 1 2 3 4\n', encoding='utf8')
    return path


def _digest(p: Path) -> str:
    return hashlib.sha256(p.read_bytes()).hexdigest()


@pytest.mark.parametrize('fmt,faces,rgb', [('ply', False, False), ('ply', False, True),
                                         ('ply', True, False), ('obj', True, False)])
def test_r51_native_geometry_kind_counts_fingerprint_and_continuous_camera(tmp_path, fmt, faces, rgb):
    path = _obj(tmp_path/'plane.obj') if fmt == 'obj' else _ply(tmp_path/'plane.ply', faces=faces, rgb=rgb)
    before = path.read_bytes()
    sha = _digest(path)
    with ResidentRenderClient(160, 128, timeout=50) as client:
        opened = client.open_source(path.resolve(), expected_sha256=sha)
        dto = SceneDescriptor.from_result(opened)
        assert dto.geometry_kind == ('mesh' if faces else 'points')
        assert dto.point_count == 4
        assert dto.face_count == int(faces)
        assert dto.source_format == fmt
        assert dto.has_rgb is rgb
        assert dto.source_sha256 == sha
        assert dto.bounds == pytest.approx((0, 1, 0, 1, 0, 0))
        assert dto.units == dto.coordinate_frame == 'unknown'
        assert len(client.latest_rgb()) == 160*128*3
        pid = client.pid
        for _ in range(3):
            frame = client.camera('orbit', 12.0, 5.0)
            assert frame['open_count'] == 1
            assert frame['frame_revision'] > opened['frame_revision']
            assert client.pid == pid
        assert client.request('status')['active_scene'] is True
    assert path.read_bytes() == before


def test_r51_r41_legacy_ply_mesh_rejection_preserved(tmp_path):
    mesh = _ply(tmp_path/'surface.ply', faces=True)
    with ResidentRenderClient(160, 128, timeout=50) as client:
        with pytest.raises(RenderHostError, match='MESH_DEFERRED_R5_1'):
            client.open_ply(mesh)
        assert not client.request('status')['active_scene']
        assert client.open_source(mesh)['geometry_kind'] == 'mesh'


def test_r51_async_ack_and_geometry_descriptor(tmp_path):
    obj = _obj(tmp_path/'surface.obj')
    with CoalescingRenderSession(160, 128, timeout=50) as session:
        response = session.open_source(obj, _digest(obj)).result(timeout=50)
        assert SceneDescriptor.from_result(response).face_count == 1
        first = session.next_frame(timeout=15)
        assert len(first.rgb) == 160*128*3
        input_revision = session.camera('orbit', 14, 6)
        subsequent = session.next_frame(timeout=15)
        assert subsequent.input_revision == input_revision
        assert subsequent.frame_revision > first.frame_revision
        closed = session.close_scene().result(timeout=15)
        assert not closed['active_scene']


def test_r51_bad_fingerprint_rejected_clears_active_scene(tmp_path):
    points = _ply(tmp_path/'point.ply')
    with ResidentRenderClient(160, 128, timeout=45) as client:
        client.open_source(points)
        with pytest.raises(RenderHostError, match='SOURCE_FINGERPRINT_MISMATCH'):
            client.open_source(points, 'f'*64)
        assert client.request('status')['active_scene'] is False


@pytest.mark.parametrize('body', [
    'v 0 0 0\nv 1 0 0\nv 0 1 0\nf 1 2 99\n',
    'v 0 0 0\nv 1 0 0\nv 0 1 0\nmtllib danger.mtl\nf 1 2 3\n',
    'v 0 0 0\nv 1 0 0\nv nan 1 0\nf 1 2 3\n',
    'v 0 0 0\nv 1 0 0\nv 0 1 0\nf -3 -2 -1\n',
    'v 0 0 0\nv 1 0 0\nv 0 1 0\n',
    'v 0 0 0\nv 1 0 0\nv 0 1 0\nf 1 1 2\n',
])
def test_r51_untrusted_obj_rejected_without_source_mutation(tmp_path, body):
    source = tmp_path/'bad.obj'
    source.write_text(body, encoding='utf8')
    blob = source.read_bytes()
    with ResidentRenderClient(160, 128, timeout=30) as client:
        with pytest.raises(RenderHostError):
            client.open_source(source)
        assert not client.request('status')['active_scene']
    assert source.read_bytes() == blob


def test_r51_scene_contract_rejects_fabricated_unit_and_bad_face_count():
    valid = {'name':'a.ply','source_sha256':'a'*64,'source_bytes':100,
             'source_format':'ply','geometry_kind':'mesh','point_count':4,
             'face_count':1,'bounds':[0,1,0,1,0,0], 'has_rgb':False,
             'units':'unknown', 'coordinate_frame':'unknown'}
    assert SceneDescriptor.from_result(valid).face_count == 1
    for field, value in (('units','mm'),('coordinate_frame','world'),('face_count',0),
                         ('point_count',True),('bounds',[0,1,0,1,0,float('nan')]),
                         ('source_sha256','x'*64),('geometry_kind','points')):
        with pytest.raises(ValueError):
            SceneDescriptor.from_result({**valid, field:value})
    with pytest.raises(ValueError):
        SceneSource('a.ply', expected_sha256='unsafe')
    with pytest.raises(ValueError):
        SceneSelectionRef('a'*64, 1, 'face', 2, (0,0,float('nan')))
    assert SceneSelectionRef('a'*64, 1, 'face', 0, (0.,0.,0.)).kind == 'face'


def test_r51_ipc_operation_strictly_typed_and_separate_from_legacy():
    ok = b'{"id":1,"op":"open_scene","path":"C:/tmp/a.obj","expected_sha256":null}\n'
    assert decode_request(ok)['op'] == 'open_scene'
    for raw in (
        b'{"id":1,"op":"open_scene","path":"a.obj","expected_sha256":"bad"}\n',
        b'{"id":1,"op":"open_scene","path":"a.obj","other":1}\n',
        b'{"id":1,"op":"open","path":"a.ply","expected_sha256":null}\n',
    ):
        with pytest.raises(ValueError):
            decode_request(raw)


def test_r51_no_qt_in_core_or_vtk_in_application():
    import ast
    root=Path(__file__).resolve().parents[3]/'src/scantopath/modules/viewer3d'
    for part in ('application/scene_contracts.py','infrastructure/scene_reader.py'):
        path=root/part
        tree=ast.parse(path.read_text('utf8'))
        imports=[x.module for x in ast.walk(tree) if isinstance(x,ast.ImportFrom)]
        imports += [alias.name for x in ast.walk(tree) if isinstance(x,ast.Import) for alias in x.names]
        assert not any(n and n.startswith('PySide6') for n in imports)
        if part.startswith('application/'):
            assert not any(n and n.startswith('vtk') for n in imports)


def test_r51_obj_normals_and_texture_index_validated(tmp_path):
    obj = tmp_path/'normals.obj'
    obj.write_text('v 0 0 0\nv 1 0 0\nv 0 1 0\n'
                   'vn 0 0 1\nvt 0 0\nvt 1 0\nvt 0 1\n'
                   'f 1/1/1 2/2/1 3/3/1\n', encoding='ascii')
    with ResidentRenderClient(160, 128, timeout=50) as client:
        dto = SceneDescriptor.from_result(client.open_source(obj))
        assert dto.face_count == 1 and dto.geometry_kind == 'mesh'
    obj.write_text('v 0 0 0\nv 1 0 0\nv 0 1 0\n'
                   'vt 0 0\nf 1/1 2/2 3/1\n', encoding='ascii')
    with ResidentRenderClient(160, 128, timeout=50) as client:
        with pytest.raises(RenderHostError, match='OBJ_INVALID_TEXTURE_INDEX'):
            client.open_source(obj)


def test_r51_scene_source_reopen_mesh_as_points_clears_revision_and_state(tmp_path):
    mesh = _ply(tmp_path/'m.ply', faces=True)
    point = _ply(tmp_path/'p.ply', faces=False)
    with ResidentRenderClient(160, 128, timeout=50) as client:
        a = client.open_source(mesh)
        b = client.open_source(point)
        assert a['geometry_kind'] == 'mesh' and b['geometry_kind'] == 'points'
        assert b['scene_revision'] > a['scene_revision']
        assert b['open_count'] == a['open_count'] + 1
        assert b['source_sha256'] != a['source_sha256']
