"""Visual PLY provenance sidecars and original raw frame safety (no hardware)."""
import json
from types import SimpleNamespace as NS
import numpy as np
from PIL import Image
from scantopath.modules.capture.application.live_snapshot import freeze_geometry,save_snapshot


def test_visual_depth_snapshot_marks_inferred_and_smoothed(tmp_path):
    xyz=np.array([[0.,0.,.850],[.01,0,.850],[.02,0,.850]],dtype='<f4')
    uv=np.array([[1,1],[2,1],[3,1]],np.int32)
    cloud=NS(points_xyz_m=xyz,depth_source_uv=uv,camera_generation=2,
        depth_frame_index=3,color_frame_index=4,depth_timestamp_us=1234,
        calibration_fingerprint='b'*64,coordinate_frame='depth_optical',units='m',
        metric_validated=False,inferred_depth_mask=np.array([True,False,False]),
        smoothed_depth_mask=np.array([False,True,False]))
    src=NS(depth_frame_index=3,color_frame_index=4,depth_timestamp_us=1234,
        depth_height=3,depth_width=5,color_height=4,color_width=6,
        calibration=NS(fingerprint='b'*64),device_name='Fake Gemini')
    orig=np.full((3,5),900,dtype=np.uint16)
    orig[1,1]=0
    frame=NS(source=src,color_rgb=np.zeros((4,6,3),np.uint8),depth_u16=orig)
    frozen=freeze_geometry(cloud,frame,roi=None,scope_mode='object',reference_mode='charuco',
        denoise_mode='standard',depth_enhancement_mode='visual',
        isolation_status='CHARUCO_OBJECT_FOUND')
    result=save_snapshot(frozen,tmp_path)
    assert (result/'cloud.ply').is_file()
    assert sorted(p.name for p in result.iterdir())==[
        'cloud.ply','inferred_points_mask.png','selected_points_mask.png',
        'smoothed_points_mask.png','snapshot.json']
    meta=json.loads((result/'snapshot.json').read_text('utf8'))
    assert meta['depth_enhancement_inferred_points']==1
    assert meta['depth_enhancement_smoothed_points']==1
    assert meta['metric_accuracy_verified'] is False
    assert meta['ply_includes_estimated_or_smoothed_xyz'] is True
    assert int(np.array(Image.open(result/'inferred_points_mask.png')).sum())==255
    assert int(np.array(Image.open(result/'smoothed_points_mask.png')).sum())==255
    assert frozen.depth[1,1]==0   # original depth remains untouched
