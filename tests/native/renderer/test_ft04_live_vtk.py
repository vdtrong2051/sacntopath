"""FT-04 live VTK end-to-end. Host process is real; no RGB-D hardware needed."""
from __future__ import annotations

import os
import numpy as np
import pytest

from scantopath.modules.viewer3d.infrastructure.resident_poc.client import (
    ResidentRenderClient, RenderHostError,
)
from scantopath.modules.geometry.application.live_geometry import LiveCloudFrame, LiveCloudStats


def cloud(index: int, generation: int = 1, points: int = 64):
    xyz = np.zeros((points, 3), dtype='<f4')
    xyz[:,0] = np.linspace(-.15,.15,points,dtype='<f4')
    xyz[:,1] = np.linspace(-.08,.08,points,dtype='<f4')
    xyz[:,2] = 1.0 + .002 * index
    uv = np.column_stack((np.arange(points,dtype=np.int32),
                          np.zeros(points,dtype=np.int32)))
    return LiveCloudFrame(
        points_xyz_m=xyz, depth_source_uv=uv, camera_generation=generation,
        depth_frame_index=index, color_frame_index=index,
        depth_timestamp_us=index*33333, calibration_fingerprint='a'*64,
        statistics=LiveCloudStats(points,0,0,0,points,0,points),
    )


def client():
    from vtkmodules.vtkRenderingCore import vtkRenderWindow  # noqa: F401
    return ResidentRenderClient(320,240,timeout=20)


def test_ipc_life_03_real_host_begin_update_ack_end():
    c = client()
    try:
        c.start()
        c.enable_frame_ack()
        begin=c.begin_live_cloud(live_session_token=461,camera_generation=1)
        assert begin['live_mode'] is True
        first=c.update_live_cloud(cloud(1))
        assert first['cloud_acked_sequence']==1
        assert first['cloud_acked_slot']==0
        d,rgb=c.copy_ack_frame()
        assert len(rgb)==320*240*3
        assert d['point_count']==64
        second=c.update_live_cloud(cloud(2))
        assert second['cloud_acked_slot']==1
        c.copy_ack_frame()
        with pytest.raises(RenderHostError,match='CLOUD_FRAME_STALE'):
            c.update_live_cloud(cloud(2))
        # A rejected packet has uncertain ACK state, so client quarantines host.
        assert c._cloud_failed
    finally:
        c.close()


def test_ipc_life_04_clean_end_and_file_mode_status():
    c=client()
    try:
        c.start(); c.enable_frame_ack()
        c.begin_live_cloud(live_session_token=100,camera_generation=2)
        c.update_live_cloud(cloud(1,generation=2))
        c.copy_ack_frame()
        status=c.request('status')
        assert status['active_scene'] and status['live_mode']
        ended=c.end_live_cloud()
        assert not ended['live_mode']
        assert not c.request('status')['active_scene']
        c.begin_live_cloud(live_session_token=101,camera_generation=3)
        c.update_live_cloud(cloud(1,generation=3))
        c.copy_ack_frame()
        c.end_live_cloud()
    finally:
        c.close()


def test_ipc_life_05_rgb_ack_required_before_update():
    c=client()
    try:
        c.start(); c.enable_frame_ack()
        c.begin_live_cloud(live_session_token=100,camera_generation=1)
        c.update_live_cloud(cloud(1))
        with pytest.raises(RenderHostError,match='FRAME_NOT_ACKED'):
            c.update_live_cloud(cloud(2))
        c.copy_ack_frame()
        c.update_live_cloud(cloud(2))
        c.copy_ack_frame()
        c.end_live_cloud()
    finally:
        c.close()


def test_ipc_flow_06_session_latest_cloud_and_close():
    from scantopath.modules.viewer3d.infrastructure.resident_poc.async_session import CoalescingRenderSession
    s=CoalescingRenderSession(320,240,timeout=20)
    try:
        s.start().result(timeout=30)
        s.begin_live_cloud(live_session_token=200,camera_generation=3).result(timeout=30)
        for index in range(1,8):
            assert s.submit_live_cloud(cloud(index,generation=3))
        snap=s.next_frame(timeout=30)
        assert snap.scene_revision>0
        assert len(snap.rgb)==320*240*3
        assert s.statistics['cloud_acked']>=1
        assert s.statistics['cloud_dropped']>=1
        s.end_live_cloud().result(timeout=30)
        assert not s.statistics['cloud_pending']
    finally:
        s.stop(timeout=5)
