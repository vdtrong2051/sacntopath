"""R4.3 bounded, Qt-independent resident renderer scheduler.

The worker owns the child process. Camera inputs coalesce into one absolute
CameraView; each completed RGB frame is copied and ACKed before the next render.
"""
from __future__ import annotations

from collections import deque
from concurrent.futures import Future
from dataclasses import dataclass
from pathlib import Path
import queue
import threading
from typing import Any

from ...application.navigation import CameraView
from .client import RenderHostError, ResidentRenderClient


@dataclass(frozen=True, slots=True)
class FrameSnapshot:
    scene_revision: int
    frame_revision: int
    width: int
    height: int
    rgb: bytes
    host_pid: int
    input_revision: int


class CoalescingRenderSession:
    """Async proof-of-concept; never call worker I/O on Qt's GUI thread.

    Commands: bounded FIFO for scene lifecycle; latest-wins absolute camera.
    Frames: one immutable snapshot, older frames dropped when consumer is slow.
    """

    def __init__(self, width: int = 320, height: int = 240, *, timeout: float = 30.0):
        self._client = ResidentRenderClient(width, height, timeout=timeout)
        self._cv = threading.Condition()
        self._commands: deque[tuple[str, Any, Future]] = deque()
        self._frames: queue.Queue[FrameSnapshot] = queue.Queue(maxsize=1)
        self._thread: threading.Thread | None = None
        self._ready: Future = Future()
        self._stopping = False
        self._ever_started = False
        self._active = False
        self._desired = CameraView()
        self._wanted_revision = 0
        self._sent_revision = 0
        self._failure: Exception | None = None
        self._frames_received = 0
        self._frames_dropped = 0
        self._camera_renders = 0

    @property
    def pid(self) -> int | None:
        return self._client.pid

    @property
    def statistics(self) -> dict[str, int]:
        with self._cv:
            return {'input_revision': self._wanted_revision, 'rendered_input_revision': self._sent_revision,
                    'frames_received': self._frames_received, 'frames_dropped': self._frames_dropped,
                    'camera_renders': self._camera_renders, 'pending_commands': len(self._commands)}

    def start(self) -> Future:
        with self._cv:
            if self._ever_started:
                raise RuntimeError('SESSION_ALREADY_STARTED')
            self._ever_started = True
            self._thread = threading.Thread(target=self._run, name='R4.3-render-worker', daemon=True)
            self._thread.start()
            return self._ready

    def _queue_command(self, op: str, value: Any = None) -> Future:
        result: Future = Future()
        with self._cv:
            if self._thread is None or self._stopping or self._failure is not None:
                raise RenderHostError('SESSION_NOT_RUNNING')
            if len(self._commands) >= 8:
                raise RenderHostError('CONTROL_QUEUE_FULL')
            self._commands.append((op, value, result))
            self._cv.notify()
        return result

    def open_ply(self, path: str | Path) -> Future:
        source = Path(path)
        if not source.is_absolute() or source.is_symlink() or not source.is_file():
            raise ValueError('INVALID_SOURCE_PATH')
        return self._queue_command('open', str(source))

    def open_source(self, path: str | Path, expected_sha256: str | None = None) -> Future:
        # Queue geometry load for PLY points/mesh or OBJ.
        from ...application.scene_contracts import SceneSource
        source = Path(path)
        if (not source.is_absolute() or source.is_symlink() or not source.is_file() or
                source.suffix.lower() not in ('.ply', '.obj')):
            raise ValueError('INVALID_SOURCE_PATH')
        dto = SceneSource(str(source), expected_sha256)
        return self._queue_command('open_scene', dto)

    def pick(self, u: float, v: float, scene_revision: int,
             frame_revision: int) -> Future:
        """Bounded worker request; never block Qt or accept a pending camera."""
        from .protocol import decode_request, encode_response
        # Validate at the source and again inside the isolated host.
        decode_request(encode_response({'id': 1, 'op': 'pick', 'u': u, 'v': v,
                                         'scene_revision': scene_revision,
                                         'frame_revision': frame_revision}))
        with self._cv:
            if not self._active or self._wanted_revision != self._sent_revision:
                raise ValueError('CAMERA_NOT_SETTLED')
        return self._queue_command('pick', (u, v, scene_revision, frame_revision))

    def set_grid(self, enabled: bool, mode: str = 'xy') -> Future:
        if type(enabled) is not bool or mode not in ('xy', 'base'):
            raise ValueError('INVALID_REFERENCE_GRID')
        return self._queue_command('grid', (enabled, mode))

    def set_visibility(self, visible: bool) -> Future:
        if type(visible) is not bool:
            raise ValueError('INVALID_LAYER_VISIBILITY')
        return self._queue_command('visibility', visible)

    def close_scene(self) -> Future:
        return self._queue_command('close_scene')

    def camera(self, action: str, dx: float = 0.0, dy: float = 0.0) -> int:
        """Nonblocking input: always preserve the last cumulative camera intent."""
        with self._cv:
            if not self._active or self._stopping or self._failure is not None:
                raise RenderHostError('NO_ACTIVE_SCENE')
            self._desired = self._desired.update(action, dx, dy)
            self._wanted_revision += 1
            self._cv.notify()
            return self._wanted_revision

    def next_frame(self, *, timeout: float = 2.0) -> FrameSnapshot:
        try:
            return self._frames.get(timeout=timeout)
        except queue.Empty as exc:
            with self._cv:
                failure = self._failure
            if failure is not None:
                raise RenderHostError('RENDER_WORKER_FAILED') from failure
            raise TimeoutError('NO_NEW_FRAME') from exc

    def _publish_frame(self, descriptor: dict[str, Any], rgb: bytes, revision: int) -> None:
        if len(rgb) != descriptor['byte_count']:
            raise RenderHostError('INVALID_RGB_LENGTH')
        frame = FrameSnapshot(
            scene_revision=descriptor['scene_revision'], frame_revision=descriptor['frame_revision'],
            width=descriptor['width'], height=descriptor['height'], rgb=rgb,
            host_pid=self._client.pid or 0, input_revision=revision)
        with self._cv:
            self._frames_received += 1
            if self._frames.full():
                self._frames.get_nowait()
                self._frames_dropped += 1
            self._frames.put_nowait(frame)

    def _clear_frames(self) -> None:
        while not self._frames.empty():
            try:
                self._frames.get_nowait()
            except queue.Empty:
                break

    def _run(self) -> None:
        current: Future | None = None
        try:
            self._client.start()
            self._client.enable_frame_ack()
            self._ready.set_result(True)
            while True:
                with self._cv:
                    while (not self._stopping and not self._commands and
                           (not self._active or self._wanted_revision == self._sent_revision)):
                        self._cv.wait()
                    if self._stopping:
                        break
                    if self._commands:
                        op, value, current = self._commands.popleft()
                        revision = self._wanted_revision
                    else:
                        op, value, current = 'set_camera', self._desired.to_json(), None
                        revision = self._wanted_revision
                if op in ('open', 'open_scene'):
                    with self._cv:
                        self._active = False
                        self._desired = CameraView()
                        self._wanted_revision = self._sent_revision = 0
                    self._clear_frames()
                    try:
                        response = (self._client.open_ply(value) if op == 'open' else
                                    self._client.open_source(value.path, value.expected_sha256))
                        descriptor, rgb = self._client.copy_ack_frame()
                        self._publish_frame(descriptor, rgb, 0)
                    except Exception:
                        self._clear_frames()
                        raise
                    with self._cv:
                        self._active = True
                    current.set_result(response)
                elif op == 'pick':
                    u, v, scene_revision, frame_revision = value
                    current.set_result(self._client.request(
                        'pick', u=u, v=v, scene_revision=scene_revision,
                        frame_revision=frame_revision))
                elif op == 'grid':
                    enabled, mode = value
                    response = self._client.request('set_grid', enabled=enabled, mode=mode)
                    descriptor, rgb = self._client.copy_ack_frame()
                    self._publish_frame(descriptor, rgb, revision)
                    current.set_result(response)
                elif op == 'visibility':
                    response = self._client.request('set_visibility', visible=value)
                    descriptor, rgb = self._client.copy_ack_frame()
                    self._publish_frame(descriptor, rgb, revision)
                    current.set_result(response)
                elif op == 'close_scene':
                    response = self._client.request('close_scene')
                    with self._cv:
                        self._active = False
                        self._desired = CameraView()
                        self._wanted_revision = self._sent_revision = 0
                    self._clear_frames()
                    current.set_result(response)
                else:
                    response = self._client.set_camera(value)
                    descriptor, rgb = self._client.copy_ack_frame()
                    self._publish_frame(descriptor, rgb, revision)
                    with self._cv:
                        self._sent_revision = revision
                        self._camera_renders += 1
                current = None
        except Exception as exc:
            with self._cv:
                self._failure = exc
                self._active = False
                while self._commands:
                    _, _, pending = self._commands.popleft()
                    pending.set_exception(RenderHostError('RENDER_WORKER_FAILED'))
            if current is not None and not current.done():
                current.set_exception(exc)
            if not self._ready.done():
                self._ready.set_exception(exc)
        finally:
            self._client.close()

    def stop(self, *, timeout: float = 2.0) -> None:
        with self._cv:
            if self._thread is None:
                return
            self._stopping = True
            self._active = False
            while self._commands:
                _, _, future = self._commands.popleft()
                future.set_exception(RenderHostError('SESSION_STOPPED'))
            self._cv.notify_all()
            thread = self._thread
        if thread is threading.current_thread():
            raise RuntimeError('CANNOT_STOP_FROM_RENDER_WORKER')
        thread.join(timeout=timeout)
        if thread.is_alive():
            self._client.abort()
            thread.join(timeout=5)
        if thread.is_alive():
            raise RenderHostError('RENDER_WORKER_DID_NOT_STOP')
        with self._cv:
            self._thread = None
            self._clear_frames()

    def __enter__(self):
        self.start().result(timeout=30)
        return self

    def __exit__(self, *_exc):
        self.stop()
