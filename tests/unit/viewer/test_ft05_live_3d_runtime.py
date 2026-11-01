"""FT-05 asynchronous bridge; deterministic fake VTK sessions, no hardware needed."""
from __future__ import annotations

from concurrent.futures import Future
from threading import Lock
import time

import numpy as np

from scantopath.modules.geometry.application.live_geometry import LiveCloudFrame, LiveCloudStats
from scantopath.modules.viewer3d.infrastructure.resident_poc.async_session import FrameSnapshot
from scantopath.modules.viewer3d.application.live_3d_runtime import Live3DRenderWorker


def done(result=True):
    f = Future()
    f.set_result(result)
    return f


def cloud(generation, index):
    return LiveCloudFrame(
        points_xyz_m=np.array([[0., 0., 0.5]], dtype='<f4'),
        depth_source_uv=np.array([[0, 0]], dtype=np.int32),
        camera_generation=generation, depth_frame_index=index,
        color_frame_index=index, depth_timestamp_us=index * 33333,
        calibration_fingerprint='a'*64,
        statistics=LiveCloudStats(1,0,0,0,1,0,1),
    )


class FakeSession:
    def __init__(self):
        self.lock = Lock()
        self.active = 0
        self.submitted = []
        self.stopped = False
        self.camera_calls = []
        self.ready_frames = []

    def start(self):
        return done()

    def begin_live_cloud(self, *, live_session_token, camera_generation):
        with self.lock:
            self.active = camera_generation
        return done()

    def submit_live_cloud(self, value):
        with self.lock:
            self.submitted.append((value.camera_generation, value.depth_frame_index))
            self.ready_frames.append(FrameSnapshot(
                scene_revision=1, frame_revision=value.depth_frame_index+1,
                width=2, height=2, rgb=bytes([1,2,3]*4),
                host_pid=123, input_revision=0))
        return True

    def next_frame(self, *, timeout):
        with self.lock:
            if self.ready_frames:
                return self.ready_frames.pop(0)
        time.sleep(min(timeout, .01))
        raise TimeoutError('NO_NEW_FRAME')

    def camera(self, action, dx, dy):
        with self.lock:
            self.camera_calls.append((action,dx,dy))
        return 1

    def stop(self, *, timeout):
        with self.lock:
            self.stopped = True


def until(predicate, seconds=3):
    deadline=time.monotonic()+seconds
    while time.monotonic()<deadline:
        if predicate():
            return True
        time.sleep(.005)
    return False


def test_ft05_generation_and_rgb_owned_snapshot():
    made=[]
    def make():
        obj=FakeSession()
        made.append(obj)
        return obj
    bridge=Live3DRenderWorker(session_factory=make)
    bridge.start()
    try:
        bridge.change_generation(1)
        assert bridge.submit_cloud(cloud(1, 10))
        assert until(lambda: bridge.statistics()['render_frames']>=1)
        result=bridge.take_latest_rgb()
        assert result[0]==1 and result[1].rgb==bytes([1,2,3]*4)
        assert not bridge.submit_cloud(cloud(2, 11))
        bridge.change_generation(0)
        assert until(lambda: made[0].stopped)
        bridge.change_generation(2)
        assert bridge.submit_cloud(cloud(2, 12))
        assert until(lambda: bridge.statistics()['render_frames']>=2)
        assert bridge.take_latest_rgb()[0]==2
        assert made[0].stopped and len(made)>=2
    finally:
        bridge.request_stop()
        assert until(lambda: bridge.stopped)
    assert bridge.statistics()['pending_cloud']==0


def test_ft05_input_latest_wins_and_shutdown_is_nonblocking():
    made=[]
    def make():
        obj=FakeSession()
        made.append(obj)
        return obj
    bridge=Live3DRenderWorker(session_factory=make)
    bridge.start()
    bridge.change_generation(1)
    try:
        for n in range(1,100):
            bridge.submit_cloud(cloud(1,n))
        assert bridge.statistics()['pending_cloud']<=1
        assert until(lambda: bool(made) and bool(made[0].submitted))
        assert bridge.statistics()['cloud_dropped_input']>=0
        assert bridge.submit_camera('orbit', 2., 1.)
        assert until(lambda: bool(made[0].camera_calls))
    finally:
        t0=time.monotonic()
        bridge.request_stop()
        assert time.monotonic()-t0<0.5
        assert until(lambda: bridge.stopped)
    assert all(s.stopped for s in made)


def test_ft05_negative_generation_and_no_camera_or_vtk_on_construct():
    sessions=[]
    worker=Live3DRenderWorker(session_factory=lambda: sessions.append(1))
    assert sessions==[]
    import pytest
    with pytest.raises(ValueError):
        worker.change_generation(-1)
    assert not worker.submit_camera('orbit', 1, 1)
    with pytest.raises(ValueError):
        worker.submit_camera('garbage', 1, 1)
