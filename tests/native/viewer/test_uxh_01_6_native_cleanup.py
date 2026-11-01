"""UXH-01.6: real child-process/SHM lifecycle; run on Windows with VTK."""
from __future__ import annotations

from pathlib import Path

from scantopath.modules.viewer3d.infrastructure.resident_poc.client import ResidentRenderClient
from scantopath.modules.viewer3d.infrastructure.resident_poc.async_session import CoalescingRenderSession


def _points(path: Path) -> Path:
    path.write_text(
        'ply\nformat ascii 1.0\nelement vertex 5\n'
        'property float x\nproperty float y\nproperty float z\nend_header\n'
        '0 0 0\n1 0 0\n0 1 0\n-1 0 0\n0 -1 0\n', encoding='ascii')
    return path


def test_native_render_host_process_and_shm_closed_each_cycle(tmp_path):
    source = _points(tmp_path / 'lifecycle.ply')
    for _ in range(4):
        client = ResidentRenderClient(256, 256, timeout=45)
        try:
            client.start()
            result = client.open_source(source.resolve())
            assert result['point_count'] == 5
            proc = client._proc
            assert proc is not None and proc.poll() is None
        finally:
            client.close()
        assert proc.poll() is not None  # No orphaned Render Host.
        assert client._shm is None  # Shared-memory mapping unlinked.
        assert client._proc is None


def test_async_session_retirement_is_complete(tmp_path):
    source = _points(tmp_path / 'async.ply')
    session = CoalescingRenderSession(256, 256, timeout=45)
    session.start().result(timeout=45)
    try:
        opened = session.open_source(source.resolve()).result(timeout=60)
        frame = session.next_frame(timeout=20)
        assert frame.scene_revision == opened['scene_revision']
    finally:
        session.stop(timeout=5)
    assert session._thread is None
    assert session._client._proc is None
    assert session._client._shm is None
