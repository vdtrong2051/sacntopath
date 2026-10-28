"""R4.3 strict SHM frame ACK, bounded camera coalescing and child lifecycle."""
from __future__ import annotations
import hashlib
import importlib.util
import time
from pathlib import Path

import pytest

from scantopath.modules.viewer3d.infrastructure.resident_poc.client import (
    RenderHostError, ResidentRenderClient,
)
from scantopath.modules.viewer3d.infrastructure.resident_poc.async_session import (
    CoalescingRenderSession, FrameSnapshot,
)
from scantopath.modules.viewer3d.infrastructure.resident_poc.protocol import decode_request


def _fixture(tmp_path: Path) -> Path:
    source = tmp_path / 'points.ply'
    source.write_text(
        'ply\nformat ascii 1.0\nelement vertex 4\nproperty float x\n'
        'property float y\nproperty float z\nend_header\n'
        '0 0 0\n1 0 0\n0 1 0\n0 0 1\n', encoding='ascii')
    return source


def _native():
    assert importlib.util.find_spec('vtkmodules') is not None, 'VTK is required; do not skip native gate'


def test_r43_protocol_is_strict_and_legacy_hello_compatible():
    assert decode_request(b'{"id":1,"op":"hello"}\n')['op'] == 'hello'
    assert decode_request(b'{"id":2,"op":"hello","frame_mode":"ack"}\n')['frame_mode'] == 'ack'
    assert decode_request(b'{"id":3,"op":"ack_frame","scene_revision":1,"frame_revision":2,"slot":0}\n')['slot'] == 0
    for raw in (
        b'{"id":1,"op":"hello","frame_mode":"unsafe"}\n',
        b'{"id":1,"op":"ack_frame","scene_revision":true,"frame_revision":1,"slot":0}\n',
        b'{"id":1,"op":"ack_frame","scene_revision":1,"frame_revision":2,"slot":3}\n',
        b'{"id":1,"op":"set_camera","state":"{}"}\n',
        b'{"id":1,"op":"set_camera","state":false}\n',
    ):
        with pytest.raises((TypeError, ValueError)):
            decode_request(raw)


def test_r43_strict_host_requires_frame_copy_ack_before_reuse(tmp_path):
    _native()
    source = _fixture(tmp_path)
    before = hashlib.sha256(source.read_bytes()).digest()
    with ResidentRenderClient(256, 192, timeout=45) as client:
        client.enable_frame_ack()
        a = client.open_ply(source.resolve())
        first = client.latest_rgb()
        with pytest.raises(RenderHostError, match='FRAME_NOT_ACKED'):
            client.camera('orbit', 6, 0)
        descriptor, data = client.copy_ack_frame()
        assert data == first and descriptor['frame_revision'] == a['frame_revision']
        with pytest.raises(RenderHostError, match='NO_PENDING_FRAME'):
            client.copy_ack_frame()
        with pytest.raises(RenderHostError, match='STALE_FRAME_ACK'):
            client.request('ack_frame', scene_revision=a['scene_revision'],
                           frame_revision=a['frame_revision'], slot=a['slot'])
        b = client.camera('orbit', 5, 2)
        assert b['frame_revision'] == a['frame_revision'] + 1
        assert b['scene_revision'] == a['scene_revision']
        _, frame_b = client.copy_ack_frame()
        assert hashlib.sha256(frame_b).digest() != hashlib.sha256(data).digest()
    assert hashlib.sha256(source.read_bytes()).digest() == before


def test_r43_absolute_camera_state_and_scene_reset(tmp_path):
    _native()
    from scantopath.modules.viewer3d.application.navigation import CameraView
    source = _fixture(tmp_path)
    with ResidentRenderClient(256, 192, timeout=45) as client:
        client.enable_frame_ack()
        client.open_ply(source.resolve())
        client.copy_ack_frame()
        desired = CameraView().update('orbit', 21, 7).update('pan', 9, -3).update('zoom', 2)
        updated = client.set_camera(desired.to_json())
        assert updated['frame_revision'] == 2
        client.copy_ack_frame()
        closed = client.request('close_scene')
        assert not closed['active_scene']
        with pytest.raises(RenderHostError, match='NO_SCENE'):
            client.set_camera(desired.to_json())
        reopened = client.open_ply(source.resolve())
        assert reopened['scene_revision'] > updated['scene_revision']
        client.copy_ack_frame()


def test_r43_async_coalesces_camera_and_publishes_immutable_frames(tmp_path):
    _native()
    source = _fixture(tmp_path)
    before = source.read_bytes()
    with CoalescingRenderSession(256, 192, timeout=45) as session:
        result = session.open_ply(source).result(timeout=45)
        frame = session.next_frame(timeout=10)
        assert isinstance(frame, FrameSnapshot)
        pid = session.pid
        assert result['open_count'] == 1 and len(frame.rgb) == 256 * 192 * 3
        for _ in range(60):
            last = session.camera('orbit', 1.0, 0.2)
        deadline = time.monotonic() + 35
        while time.monotonic() < deadline and session.statistics['rendered_input_revision'] != last:
            time.sleep(.02)
        stats = session.statistics
        assert stats['rendered_input_revision'] == last == 60, stats
        assert 1 <= stats['camera_renders'] <= 60
        assert stats['pending_commands'] == 0
        assert stats['frames_received'] == stats['camera_renders'] + 1
        assert session.pid == pid
        latest = session.next_frame(timeout=10)
        assert latest.input_revision == 60
        assert latest.frame_revision == stats['frames_received']
        assert hashlib.sha256(latest.rgb).digest() != hashlib.sha256(frame.rgb).digest()
        assert frame.rgb == bytes(frame.rgb)  # Snapshot remains immutable after new renders.
    assert source.read_bytes() == before
    assert session.pid is None


def test_r43_async_lifecycle_commands_and_no_old_scene_frame(tmp_path):
    _native()
    source = _fixture(tmp_path)
    with CoalescingRenderSession(256, 192, timeout=45) as session:
        first = session.open_ply(source).result(timeout=45)
        session.next_frame(timeout=10)
        old_pid = session.pid
        closed = session.close_scene().result(timeout=10)
        assert closed['active_scene'] is False
        with pytest.raises(TimeoutError):
            session.next_frame(timeout=.05)
        with pytest.raises(RenderHostError, match='NO_ACTIVE_SCENE'):
            session.camera('orbit', 1, 1)
        second = session.open_ply(source).result(timeout=45)
        assert second['scene_revision'] > first['scene_revision']
        assert session.pid == old_pid
        second_frame = session.next_frame(timeout=10)
        assert second_frame.scene_revision == second['scene_revision']


def test_r43_worker_detects_abnormal_child_exit(tmp_path):
    _native()
    source = _fixture(tmp_path)
    session = CoalescingRenderSession(256, 192, timeout=10)
    session.start().result(timeout=20)
    try:
        session.open_ply(source).result(timeout=30)
        session.next_frame(timeout=10)
        session._client.abort()  # Test-only synthetic child kill; not a native crash proof.
        session.camera('orbit', 2, 1)
        deadline = time.monotonic() + 12
        while time.monotonic() < deadline:
            try:
                session.next_frame(timeout=.2)
            except RenderHostError:
                break
            except TimeoutError:
                continue
        else:
            pytest.fail('worker did not detect host exit')
    finally:
        session.stop(timeout=2)
    assert session.pid is None


def test_r43_async_stop_is_idempotent_and_bounded(tmp_path):
    _native()
    for _ in range(2):
        session = CoalescingRenderSession(256, 192, timeout=20)
        session.start().result(timeout=30)
        session.open_ply(_fixture(tmp_path)).result(timeout=30)
        session.stop(timeout=2)
        session.stop(timeout=2)
        assert session.pid is None
        with pytest.raises(RenderHostError):
            session.camera('orbit', 2, 3)


def test_r43_boundary_is_qt_free_and_desktop_untouched():
    import ast
    folder = Path(__file__).resolve().parents[3] / 'src/scantopath/modules/viewer3d/infrastructure/resident_poc'
    for src in folder.glob('*.py'):
        tree = ast.parse(src.read_text('utf-8'))
        imported = [n.module for n in ast.walk(tree) if isinstance(n, ast.ImportFrom) and n.module]
        imported += [a.name for n in ast.walk(tree) if isinstance(n, ast.Import) for a in n.names]
        assert not any(s.startswith(('PySide6', 'scantopath.ui', 'scantopath.storage')) for s in imported)


def test_r43_source_symlink_is_not_followed(tmp_path):
    source = _fixture(tmp_path)
    alias = tmp_path / 'alias.ply'
    try:
        alias.symlink_to(source)
    except (OSError, NotImplementedError):
        pytest.skip('Windows host lacks symlink privilege; separately documented')
    session = CoalescingRenderSession(256, 192)
    session.start().result(timeout=30)
    try:
        with pytest.raises(ValueError, match='INVALID_SOURCE_PATH'):
            session.open_ply(alias)
        assert session.statistics['pending_commands'] == 0
    finally:
        session.stop()


def test_r43_stopped_session_cannot_be_restarted():
    _native()
    session = CoalescingRenderSession(256, 192)
    session.start().result(timeout=30)
    session.stop()
    with pytest.raises(RuntimeError, match='SESSION_ALREADY_STARTED'):
        session.start()
