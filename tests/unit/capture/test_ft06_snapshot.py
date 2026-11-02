"""FT-06 atomic snapshot, geometry lineage and fail-closed contract."""
from pathlib import Path
from types import SimpleNamespace
import json
import numpy as np
import pytest

from scantopath.modules.capture.application.live_snapshot import (
    SnapshotError, freeze_geometry, bounds_xyz_mm, save_snapshot,
)


def _fixture():
    rgb = np.zeros((4, 6, 3), dtype=np.uint8)
    depth = np.full((3, 5), 900, dtype=np.uint16)
    src = SimpleNamespace(depth_frame_index=7, color_frame_index=8,
                          depth_timestamp_us=99123, depth_height=3,
                          depth_width=5, color_height=4, color_width=6,
                          calibration=SimpleNamespace(fingerprint='a'*64),
                          device_name='Fake Gemini')
    frame = SimpleNamespace(source=src, color_rgb=rgb, depth_u16=depth)
    xyz = np.array([[0.0,0.0,0.9],[0.01,0.02,0.9],[-0.01,0.01,1.0]], dtype='<f4')
    uv = np.array([[1,1],[2,1],[3,2]], dtype=np.int32)
    cloud = SimpleNamespace(points_xyz_m=xyz, depth_source_uv=uv,
                            camera_generation=3, depth_frame_index=7,
                            color_frame_index=8, depth_timestamp_us=99123,
                            calibration_fingerprint='a'*64,
                            coordinate_frame='depth_optical', units='m',
                            metric_validated=False)
    return cloud, frame


def _freeze():
    cloud, frame = _fixture()
    return freeze_geometry(cloud, frame, roi=(0,0,5,3), scope_mode='object',
                           reference_mode='charuco', denoise_mode='standard',
                           isolation_status='CHARUCO_OBJECT_FOUND', board_corners=23,
                           board_reprojection_px=0.4, board_support_fraction=0.92)


def test_ft06_freeze_owns_arrays_and_sampled_mask():
    cloud, frame = _fixture()
    frozen = freeze_geometry(cloud, frame, roi=None, scope_mode='scene',
                             reference_mode='depth', denoise_mode='off',
                             isolation_status='SCENE')
    assert frozen.depth_mask.shape == (3,5)
    assert np.count_nonzero(frozen.depth_mask) == 3
    assert not frozen.depth_mask.flags.writeable
    frame.depth_u16[1,1] = 0
    assert frozen.depth[1,1] == 900
    assert bounds_xyz_mm(frozen)[0] == [-10.0,0.0,900.0]


def test_ft06_rejects_mismatched_frame_identity():
    cloud, frame = _fixture()
    cloud.depth_frame_index=6
    with pytest.raises(SnapshotError, match='SNAPSHOT_FRAME_MISMATCH'):
        freeze_geometry(cloud, frame, roi=None, scope_mode='scene',
                        reference_mode='depth', denoise_mode='off',isolation_status='SCENE')


def test_ft06_rejects_uv_outside_depth_grid():
    cloud, frame = _fixture()
    cloud.depth_source_uv[0,0]=99
    with pytest.raises(SnapshotError, match='SNAPSHOT_POINTS_INVALID'):
        freeze_geometry(cloud, frame, roi=None, scope_mode='object',
                        reference_mode='charuco', denoise_mode='off',isolation_status='CHARUCO_OBJECT_FOUND')


def test_ft06_atomic_export_and_ply_readback(tmp_path):
    frozen = _freeze()
    output = save_snapshot(frozen, tmp_path)
    assert output.is_dir()
    assert sorted(p.name for p in output.iterdir()) == [
        'cloud.ply', 'selected_points_mask.png', 'snapshot.json']
    assert not list(tmp_path.glob('*.partial'))
    payload = (output/'cloud.ply').read_bytes()
    header, body = payload.split(b'end_header\n', 1)
    assert b'format binary_little_endian 1.0' in header
    assert b'element vertex 3' in header
    assert np.allclose(np.frombuffer(body, dtype='<f4').reshape(-1,3), frozen.cloud.points_xyz_m)
    meta = json.loads((output/'snapshot.json').read_text(encoding='utf8'))
    assert meta['point_count']==3 and meta['coordinate_frame']=='depth_optical'
    assert meta['board_corners']==23
    assert meta['metric_accuracy_verified'] is False
    assert meta['mask_semantics']=='selected_post_filter_post_sampling_depth_pixels'
    from PIL import Image
    mask = np.array(Image.open(output/'selected_points_mask.png'))
    assert np.array_equal(mask, frozen.depth_mask)


def test_ft06_rejects_nonexisting_parent(tmp_path):
    with pytest.raises(SnapshotError, match='SNAPSHOT_PARENT_INVALID'):
        save_snapshot(_freeze(), tmp_path/'missing')
