"""FT-05: non-Qt bridge from FT-03 LiveCloudFrame to FT-04 VTK session.

Only this worker's thread waits on a renderer future or calls stop(). No Qt,
SDK, RAW, SQLite or filesystem I/O. All mailboxes are one-slot latest-wins.
"""
from __future__ import annotations

from threading import Condition, Thread
from time import monotonic
from typing import Any, Callable

from scantopath.modules.viewer3d.infrastructure.resident_poc.async_session import (
    CoalescingRenderSession, FrameSnapshot,
)


class Live3DRenderWorker:
    """One manager thread owns all FT-04 sessions and their VTK child lifecycles."""

    def __init__(self, *, session_factory: Callable[[], Any] | None = None) -> None:
        self._factory = session_factory or (lambda: CoalescingRenderSession(640, 480, timeout=45))
        self._cv = Condition()
        self._thread: Thread | None = None
        self._closing = False
        self._desired_generation = 0
        self._active_generation = 0
        self._scene_epoch = 0
        self._active_scene_epoch = 0
        self._pending_cloud = None
        self._pending_camera: tuple[str, float, float] | None = None
        self._latest: tuple[int, FrameSnapshot] | None = None
        self._last_error: str | None = None
        self._counts = {
            'cloud_received': 0, 'cloud_dropped_input': 0,
            'cloud_rejected_stale': 0, 'render_frames': 0,
            'rgb_dropped_output': 0, 'render_failures': 0,
            'session_starts': 0, 'session_stops': 0,
        }

    def start(self) -> None:
        with self._cv:
            if self._thread is not None:
                raise RuntimeError('FT05_ALREADY_STARTED')
            self._thread = Thread(target=self._run, name='FT05-VTK-bridge', daemon=False)
            self._thread.start()

    def change_generation(self, generation: int) -> None:
        """0 disables live view; positive generations increase monotonically."""
        if type(generation) is not int or generation < 0 or generation > 2**53-1:
            raise ValueError('INVALID_GENERATION')
        with self._cv:
            if self._closing:
                return
            if generation != 0 and generation <= self._desired_generation:
                # Repeated STREAMING signals may be delivered; do not restart.
                if generation == self._desired_generation:
                    return
                raise ValueError('NON_MONOTONIC_GENERATION')
            if self._pending_cloud is not None:
                self._counts['cloud_dropped_input'] += 1
            self._desired_generation = generation
            self._pending_cloud = self._pending_camera = self._latest = None
            self._last_error = None
            self._cv.notify_all()

    def invalidate_scene(self) -> None:
        """Drop old RGB/cloud and restart VTK session on the worker thread."""
        with self._cv:
            if self._closing:
                return
            self._scene_epoch += 1
            self._pending_cloud = self._pending_camera = self._latest = None
            self._cv.notify_all()

    def submit_cloud(self, cloud: object) -> bool:
        from scantopath.modules.geometry.application.live_geometry import LiveCloudFrame
        if not isinstance(cloud, LiveCloudFrame):
            raise TypeError('EXPECTED_LIVE_CLOUD')
        with self._cv:
            if (self._closing or self._desired_generation == 0 or
                    cloud.camera_generation != self._desired_generation):
                self._counts['cloud_rejected_stale'] += 1
                return False
            self._counts['cloud_received'] += 1
            if self._pending_cloud is not None:
                self._counts['cloud_dropped_input'] += 1
            self._pending_cloud = cloud
            self._cv.notify_all()
            return True

    def submit_camera(self, action: str, dx: float = 0.0, dy: float = 0.0) -> bool:
        from scantopath.modules.viewer3d.application.navigation import CameraView
        # Check action/arguments before passing to the renderer thread.
        CameraView().update(action, dx, dy)
        with self._cv:
            if self._closing or self._desired_generation == 0:
                return False
            # Retain only the newest intent; repeated gestures are coalesced.
            if self._pending_camera is not None and self._pending_camera[0] == action and action in ('orbit', 'pan'):
                _, x, y = self._pending_camera
                self._pending_camera = (action, max(-300.0, min(300.0, x + dx)),
                                        max(-300.0, min(300.0, y + dy)))
            else:
                self._pending_camera = (action, float(dx), float(dy))
            self._cv.notify_all()
            return True

    def take_latest_rgb(self) -> tuple[int, FrameSnapshot] | None:
        with self._cv:
            frame = self._latest
            self._latest = None
            if frame is None or frame[0] != self._desired_generation:
                return None
            return frame

    def statistics(self) -> dict[str, int | str | None]:
        with self._cv:
            return {**self._counts, 'desired_generation': self._desired_generation,
                    'active_generation': self._active_generation,
                    'scene_epoch': self._scene_epoch,
                    'pending_cloud': int(self._pending_cloud is not None),
                    'pending_rgb': int(self._latest is not None),
                    'last_error_code': self._last_error,
                    'stopping': int(self._closing),
                    'thread_alive': int(self._thread is not None and self._thread.is_alive())}

    def request_stop(self) -> None:
        with self._cv:
            self._closing = True
            self._desired_generation = 0
            self._pending_cloud = self._pending_camera = self._latest = None
            self._cv.notify_all()

    @property
    def stopped(self) -> bool:
        with self._cv:
            return self._thread is None or not self._thread.is_alive()

    def _run(self) -> None:
        session = None
        active = 0
        try:
            while True:
                with self._cv:
                    desired = self._desired_generation
                    epoch = self._scene_epoch
                    closing = self._closing
                if (closing or desired != active or
                        epoch != self._active_scene_epoch) and session is not None:
                    # Stop a process only in the worker; NEVER block Qt.
                    try:
                        session.stop(timeout=2)
                    except Exception:
                        self._record_error('VTK_STOP_FAILED')
                    session = None
                    active = 0
                    with self._cv:
                        self._active_generation = 0
                        self._counts['session_stops'] += 1
                if closing:
                    return
                if desired == 0:
                    with self._cv:
                        if not self._closing and self._desired_generation == 0:
                            self._cv.wait(timeout=0.1)
                    continue
                if session is None:
                    candidate = None
                    try:
                        candidate = self._factory()
                        candidate.start().result(timeout=50)
                        candidate.begin_live_cloud(live_session_token=desired,
                                                   camera_generation=desired).result(timeout=50)
                    except Exception:
                        self._record_error('VTK_START_FAILED')
                        if candidate is not None:
                            try:
                                candidate.stop(timeout=2)
                            except Exception:
                                pass
                        with self._cv:
                            # Keep RGB/Depth alive. Disable only this generation's 3D.
                            if self._desired_generation == desired:
                                self._desired_generation = 0
                                self._pending_cloud = self._pending_camera = None
                        continue
                    session = candidate
                    active = desired
                    with self._cv:
                        self._active_generation = desired
                        self._active_scene_epoch = epoch
                        self._counts['session_starts'] += 1
                    continue
                with self._cv:
                    if self._desired_generation != active:
                        continue
                    cloud = self._pending_cloud
                    self._pending_cloud = None
                    camera = self._pending_camera
                    self._pending_camera = None
                try:
                    if cloud is not None:
                        session.submit_live_cloud(cloud)
                    if camera is not None:
                        try:
                            session.camera(*camera)
                        except Exception:
                            # Camera commands are best-effort during first cloud.
                            pass
                    try:
                        frame = session.next_frame(timeout=0.035)
                    except TimeoutError:
                        frame = None
                    if frame is not None:
                        with self._cv:
                            if not self._closing and self._desired_generation == active:
                                if self._latest is not None:
                                    self._counts['rgb_dropped_output'] += 1
                                self._latest = (active, frame)
                                self._counts['render_frames'] += 1
                except Exception:
                    self._record_error('VTK_RENDER_FAILED')
                    with self._cv:
                        if self._desired_generation == active:
                            self._desired_generation = 0
                            self._pending_cloud = self._pending_camera = self._latest = None
                # A tiny bounded wait avoids a hot loop when VTK has no new frame.
        finally:
            if session is not None:
                try:
                    session.stop(timeout=2)
                except Exception:
                    self._record_error('VTK_STOP_FAILED')
            with self._cv:
                self._active_generation = 0
                self._pending_cloud = self._pending_camera = self._latest = None
                self._cv.notify_all()

    def _record_error(self, code: str) -> None:
        with self._cv:
            self._last_error = code
            self._counts['render_failures'] += 1
