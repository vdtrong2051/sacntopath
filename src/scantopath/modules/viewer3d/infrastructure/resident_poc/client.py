"""Stdlib-only supervised client for the R4.1 isolated renderer prototype."""
from __future__ import annotations
from multiprocessing import shared_memory
import json
import os
from collections import deque
import queue
import subprocess
import sys
import threading
from typing import Any

from .protocol import MIN_SIZE, MAX_SIZE, MAX_MESSAGE_BYTES, encode_response

HOST = 'scantopath.modules.viewer3d.infrastructure.resident_poc.host'


class RenderHostError(RuntimeError):
    """Isolated render-host rejected a request or exited unexpectedly."""


class ResidentRenderClient:
    """Supervise one host process and own its two RGB24 shared-memory slots.

    This synchronous PoC client is NOT called from the Qt GUI thread. R4.3
    will add asynchronous scheduling, coalescing, and frame acknowledgement.
    """

    def __init__(self, width: int = 320, height: int = 240, *, timeout: float = 20.0):
        if any(type(x) is not int or not MIN_SIZE <= x <= MAX_SIZE for x in (width, height)):
            raise ValueError('Invalid dimensions')
        if not 0.1 <= timeout <= 120:
            raise ValueError('Invalid timeout')
        self.width, self.height, self.timeout = width, height, timeout
        self._stride = width * height * 3
        self._shm: shared_memory.SharedMemory | None = None
        self._proc: subprocess.Popen | None = None
        self._responses: queue.Queue[bytes | None] = queue.Queue(maxsize=8)
        self._reader: threading.Thread | None = None
        self._error_reader: threading.Thread | None = None
        self._errors: deque[str] = deque(maxlen=30)
        self._sequence = 0
        self._last_frame: dict[str, Any] | None = None
        self._lock = threading.Lock()
        self._ack_mode = False
        self._seen_frame_revision = -1
        self._seen_scene_revision = -1

    @property
    def pid(self) -> int | None:
        return self._proc.pid if self._proc else None

    def start(self) -> None:
        """Create buffers once and launch one VTK process for all interactions."""
        if self._proc is not None:
            raise RuntimeError('Client already running')
        self._responses = queue.Queue(maxsize=8)
        self._sequence = 0
        self._ack_mode = False
        self._seen_frame_revision = -1
        self._seen_scene_revision = -1
        self._last_frame = None
        self._errors.clear()
        self._shm = shared_memory.SharedMemory(create=True, size=self._stride * 2)
        try:
            self._proc = subprocess.Popen(
                [sys.executable, '-X', 'faulthandler', '-m', HOST,
                 '--width', str(self.width), '--height', str(self.height),
                 '--shm-name', self._shm.name],
                stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                bufsize=0,
            )
            self._reader = threading.Thread(target=self._read_responses, daemon=True)
            self._reader.start()
            self._error_reader = threading.Thread(target=self._read_errors, daemon=True)
            self._error_reader.start()
            self.request('hello')
        except BaseException:
            self.close()
            raise

    def _read_responses(self) -> None:
        assert self._proc is not None and self._proc.stdout is not None
        try:
            while True:
                line = self._proc.stdout.readline(MAX_MESSAGE_BYTES + 1)
                if not line:
                    break
                try:
                    self._responses.put(line, timeout=1)
                except queue.Full:
                    break
        finally:
            try:
                self._responses.put(None, timeout=1)
            except queue.Full:
                pass

    def _read_errors(self) -> None:
        assert self._proc is not None and self._proc.stderr is not None
        for line in iter(self._proc.stderr.readline, b''):
            self._errors.append(line.decode('utf-8', 'replace')[:400])

    @property
    def recent_errors(self) -> tuple[str, ...]:
        return tuple(self._errors)

    def request(self, op: str, **kwargs) -> dict[str, Any]:
        """One in-flight command; fail closed on timeout or broken child pipe."""
        with self._lock:
            if self._proc is None or self._proc.poll() is not None or self._proc.stdin is None:
                raise RenderHostError('HOST_NOT_RUNNING')
            self._sequence += 1
            message = {'id': self._sequence, 'op': op, **kwargs}
            raw = encode_response(message)
            if len(raw) > MAX_MESSAGE_BYTES:
                raise ValueError('REQUEST_TOO_LARGE')
            try:
                self._proc.stdin.write(raw)
                self._proc.stdin.flush()
            except (BrokenPipeError, OSError) as exc:
                raise RenderHostError('HOST_PIPE_CLOSED') from exc
            try:
                line = self._responses.get(timeout=self.timeout)
            except queue.Empty as exc:
                self._terminate()
                raise RenderHostError('HOST_TIMEOUT') from exc
            if line is None:
                raise RenderHostError('HOST_EXITED')
            try:
                answer = json.loads(line)
            except (ValueError, UnicodeDecodeError) as exc:
                raise RenderHostError('INVALID_HOST_RESPONSE') from exc
            if (not isinstance(answer, dict) or type(answer.get('id')) is not int
                    or answer['id'] != self._sequence or type(answer.get('ok')) is not bool):
                raise RenderHostError('INVALID_HOST_RESPONSE')
            if not answer['ok']:
                raise RenderHostError(str(answer.get('error', 'HOST_REJECTED')))
            if 'slot' in answer:
                if (type(answer['slot']) is not int or answer['slot'] not in (0, 1) or
                        answer.get('byte_count') != self._stride or
                        answer.get('width') != self.width or answer.get('height') != self.height):
                    raise RenderHostError('INVALID_FRAME_DESCRIPTOR')
                if self._ack_mode:
                    scene_rev = answer.get('scene_revision')
                    frame_rev = answer.get('frame_revision')
                    if (type(scene_rev) is not int or type(frame_rev) is not int
                            or scene_rev < self._seen_scene_revision
                            or frame_rev <= self._seen_frame_revision):
                        raise RenderHostError('STALE_FRAME_DESCRIPTOR')
                    self._seen_scene_revision = scene_rev
                    self._seen_frame_revision = frame_rev
                self._last_frame = answer
            elif op in ('close_scene', 'shutdown'):
                self._last_frame = None
            return answer

    def enable_frame_ack(self) -> None:
        """Opt into strict consumer acknowledgement without changing R4.1 semantics."""
        result = self.request('hello', frame_mode='ack')
        if result.get('frame_mode') != 'ack':
            raise RenderHostError('ACK_NEGOTIATION_FAILED')
        self._ack_mode = True

    def copy_ack_frame(self) -> tuple[dict[str, Any], bytes]:
        """Copy immutable RGB bytes before releasing the host's shared slot."""
        if not self._ack_mode or self._last_frame is None:
            raise RenderHostError('NO_PENDING_FRAME')
        descriptor = dict(self._last_frame)
        rgb = self.latest_rgb()
        ack = self.request('ack_frame', scene_revision=descriptor['scene_revision'],
                           frame_revision=descriptor['frame_revision'], slot=descriptor['slot'])
        if ack.get('acked_frame_revision') != descriptor['frame_revision']:
            raise RenderHostError('INVALID_ACK_RESPONSE')
        self._last_frame = None
        return descriptor, rgb

    def set_camera(self, state: str) -> dict[str, Any]:
        return self.request('set_camera', state=state)

    def abort(self) -> None:
        """Interrupt native work without waiting on the synchronous request lock."""
        self._terminate()

    def open_ply(self, path: os.PathLike | str) -> dict[str, Any]:
        """Load and verify geometry exactly once in the isolated process."""
        self._last_frame = None
        return self.request('open', path=os.fspath(path))

    def open_source(self, path: os.PathLike | str,
                    expected_sha256: str | None = None) -> dict[str, Any]:
        # R5.1 scene loader; legacy open_ply remains vertex-only.
        from ...application.scene_contracts import SceneSource
        source = SceneSource(os.fspath(path), expected_sha256)
        self._last_frame = None
        return self.request('open_scene', path=source.path,
                            expected_sha256=source.expected_sha256)

    def camera(self, action: str, dx: float = 0, dy: float = 0) -> dict[str, Any]:
        return self.request('camera', action=action, dx=dx, dy=dy)

    def latest_rgb(self) -> bytes:
        """Copy the most recently ACKed frame; rows are bottom-up (VTK origin)."""
        if self._shm is None or self._last_frame is None:
            raise RenderHostError('NO_FRAME')
        offset = self._last_frame['slot'] * self._stride
        return bytes(self._shm.buf[offset:offset + self._stride])

    def _terminate(self) -> None:
        if self._proc is not None and self._proc.poll() is None:
            self._proc.kill()
            try:
                self._proc.wait(timeout=5)
            except subprocess.TimeoutExpired:
                pass

    def close(self) -> None:
        """Attempt protocol shutdown, then bound process teardown and unlink SHM."""
        if self._proc is not None:
            if self._proc.poll() is None:
                try:
                    self.request('shutdown')
                except (RenderHostError, OSError):
                    pass
            if self._proc.poll() is None:
                self._terminate()
            try:
                self._proc.wait(timeout=5)
            except subprocess.TimeoutExpired:
                self._terminate()
            for stream in (self._proc.stdin, self._proc.stdout, self._proc.stderr):
                if stream is not None:
                    stream.close()
            self._proc = None
        if self._reader is not None:
            self._reader.join(timeout=1)
            self._reader = None
        if self._error_reader is not None:
            self._error_reader.join(timeout=1)
            self._error_reader = None
        if self._shm is not None:
            self._shm.close()
            try:
                self._shm.unlink()
            except FileNotFoundError:
                pass
            self._shm = None
        self._last_frame = None
        self._ack_mode = False

    def __enter__(self):
        self.start()
        return self

    def __exit__(self, *_exc):
        self.close()
