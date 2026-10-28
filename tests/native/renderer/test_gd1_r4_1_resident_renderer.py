"""R4.1: real VTK-in-child contract tests; this does not certify Windows HMI."""
from __future__ import annotations
import hashlib
import importlib.util
from pathlib import Path

import pytest

from scantopath.modules.viewer3d.infrastructure.resident_poc.client import (
    ResidentRenderClient, RenderHostError,
)
from scantopath.modules.viewer3d.infrastructure.resident_poc.protocol import (
    MAX_MESSAGE_BYTES, decode_request,
)


@pytest.fixture
def points_ply(tmp_path: Path) -> Path:
    path = tmp_path / 'fixture.ply'
    path.write_text(
        'ply\nformat ascii 1.0\nelement vertex 4\n'
        'property float x\nproperty float y\nproperty float z\nend_header\n'
        '0 0 0\n1 0 0\n0 1 0\n0 0 1\n', encoding='ascii',
    )
    return path


def _native_vtk_required() -> None:
    assert importlib.util.find_spec('vtkmodules') is not None, (
        'R4.1 native acceptance requires VTK; do not silently skip it.')


def test_r41_protocol_rejects_bad_payloads_before_vtk():
    invalid = (
        b'not-json\n', b'{}\n', b'[]\n',
        b'{"id":true,"op":"hello"}\n',
        b'{"id":1,"op":"mystery"}\n',
        b'{"id":1,"op":"open","path":"."}\n'[:-1],
        b'{"id":1,"op":"camera","action":"zoom","dx":NaN,"dy":0}\n',
        b'{"id":1,"op":"hello","extra":false}\n',
        (b' ' * MAX_MESSAGE_BYTES) + b'\n',
    )
    for item in invalid:
        with pytest.raises((ValueError, TypeError)):
            decode_request(item)
    assert decode_request(b'{"id":1,"op":"hello"}\n') == {'id': 1, 'op': 'hello'}


def test_r41_single_host_single_ply_load_continuous_frames(points_ply: Path):
    _native_vtk_required()
    original = points_ply.read_bytes()
    with ResidentRenderClient(320, 240, timeout=45) as client:
        opened = client.open_ply(points_ply.resolve())
        pid = client.pid
        assert opened['point_count'] == 4
        assert opened['source_sha256'] == hashlib.sha256(original).hexdigest()
        assert opened['units'] == opened['coordinate_frame'] == 'unknown'
        assert opened['frame_revision'] == 1 and opened['open_count'] == 1
        assert len(client.latest_rgb()) == 320 * 240 * 3
        initial = hashlib.sha256(client.latest_rgb()).hexdigest()
        last = opened['frame_revision']
        for i in range(18):
            action, dx, dy = (('orbit', 4, 2), ('pan', 3, -2), ('zoom', 1, 0))[i % 3]
            result = client.camera(action, dx, dy)
            assert result['frame_revision'] == last + 1
            assert result['open_count'] == 1
            assert result['scene_revision'] == opened['scene_revision']
            assert result['slot'] in (0, 1)
            assert client.pid == pid
            last = result['frame_revision']
        assert client.request('status')['frame_revision'] == last
        assert hashlib.sha256(client.latest_rgb()).hexdigest() != initial
    assert points_ply.read_bytes() == original


def test_r41_invalid_file_clears_scene_without_mutation(points_ply: Path, tmp_path: Path):
    _native_vtk_required()
    invalid = tmp_path / 'invalid.ply'
    invalid.write_text('not ply', encoding='ascii')
    original = invalid.read_bytes()
    with ResidentRenderClient(256, 192, timeout=45) as client:
        client.open_ply(points_ply.resolve())
        with pytest.raises(RenderHostError):
            client.open_ply(invalid.resolve())
        assert client.request('status')['active_scene'] is False
        assert client.request('status')['point_count'] == 0
        with pytest.raises(RenderHostError, match='NO_SCENE'):
            client.camera('orbit', 1, 0)
        with pytest.raises(RenderHostError, match='NO_FRAME'):
            client.latest_rgb()
    assert invalid.read_bytes() == original
    assert not list(tmp_path.glob('*.png'))


def test_r41_mesh_must_not_be_silently_displayed_as_points(tmp_path: Path):
    _native_vtk_required()
    path = tmp_path / 'mesh.ply'
    path.write_text(
        'ply\nformat ascii 1.0\nelement vertex 3\n'
        'property float x\nproperty float y\nproperty float z\n'
        'element face 1\nproperty list uchar int vertex_indices\nend_header\n'
        '0 0 0\n1 0 0\n0 1 0\n3 0 1 2\n', encoding='ascii',
    )
    with ResidentRenderClient(256, 192, timeout=45) as client:
        with pytest.raises(RenderHostError, match='MESH_DEFERRED_R5_1'):
            client.open_ply(path.resolve())
        assert not client.request('status')['active_scene']


def test_r41_close_and_reopen_reuses_process_and_window(points_ply: Path):
    _native_vtk_required()
    with ResidentRenderClient(256, 192, timeout=45) as client:
        first = client.open_ply(points_ply.resolve())
        pid = client.pid
        client.camera('orbit', 10, 5)
        closed = client.request('close_scene')
        assert closed['active_scene'] is False
        with pytest.raises(RenderHostError, match='NO_FRAME'):
            client.latest_rgb()
        second = client.open_ply(points_ply.resolve())
        assert second['scene_revision'] > first['scene_revision']
        assert second['frame_revision'] > first['frame_revision']
        assert second['open_count'] == 2
        assert client.pid == pid


def test_r41_host_crash_isolation_and_cleanup(points_ply: Path):
    _native_vtk_required()
    client = ResidentRenderClient(256, 192, timeout=20)
    client.start()
    try:
        client.open_ply(points_ply.resolve())
        pid = client.pid
        assert pid is not None
        assert client._proc is not None
        client._proc.kill()  # Synthetic host crash; test process remains alive.
        client._proc.wait(timeout=10)
        with pytest.raises(RenderHostError):
            client.request('status')
    finally:
        client.close()
    assert client.pid is None
    assert client._shm is None


def test_r41_no_runtime_integration_with_desktop_shell():
    import ast
    folder = Path(__file__).resolve().parents[3] / 'src' / 'scantopath' / 'modules' / 'viewer3d' / 'infrastructure' / 'resident_poc'
    for file in folder.glob('*.py'):
        tree = ast.parse(file.read_text(encoding='utf-8'))
        imports = [x.module for x in ast.walk(tree) if isinstance(x, ast.ImportFrom) and x.module]
        imports += [a.name for x in ast.walk(tree) if isinstance(x, ast.Import) for a in x.names]
        assert not any(s.startswith(('PySide6', 'scantopath.ui', 'scantopath.metadata', 'scantopath.storage')) for s in imports)
    assert not (folder / 'qt_widget.py').exists()
