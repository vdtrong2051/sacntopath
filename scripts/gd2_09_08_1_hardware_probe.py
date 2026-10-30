"""Capture Gemini 2 keyframes over existing crash-isolated process IPC.

GD2-09.08.1 MEMORY-ONLY probe: no SQLite, no RAW files, no UI.
Close OrbbecViewer before executing. This is NOT a full G2-09 acceptance.
"""
from __future__ import annotations
import argparse
import hashlib
import json
import sys

from scantopath.modules.capture.infrastructure.process_camera import ProcessIsolatedCameraAdapter


def main():
    p = argparse.ArgumentParser()
    p.add_argument('--captures', type=int, default=2, choices=range(1,6),metavar='{1..5}')
    a = p.parse_args()
    camera=ProcessIsolatedCameraAdapter()
    report=[]
    try:
        camera.open()
        last_preview=camera.read_next(per_attempt_timeout_ms=300,max_attempts=1)
        for _ in range(a.captures):
            raw=camera.capture_next_raw(session_id='probe_session',specimen_id='probe_specimen')
            m=raw.metadata
            assert m.schema_version==2 and m.measured and m.camera_pose is None
            assert m.color.width==last_preview.color_width
            assert m.depth.width==last_preview.depth_width
            assert m.color.frame_index!=last_preview.color_frame_index or m.depth.frame_index!=last_preview.depth_frame_index
            assert m.depth_scale_m_per_unit>0
            assert len(raw.depth_y16_le)==m.depth.width*m.depth.height*2
            assert m.depth_intrinsics.fx>0 and m.color_intrinsics.fx>0
            report.append({
                'capture_id':m.capture_id,
                'color_frame_index':m.color.frame_index,
                'depth_frame_index':m.depth.frame_index,
                'color_dimensions':[m.color.width,m.color.height],
                'depth_dimensions':[m.depth.width,m.depth.height],
                'depth_scale_m_per_unit':m.depth_scale_m_per_unit,
                'color_sha256':hashlib.sha256(raw.color_mjpeg).hexdigest(),
                'depth_sha256':hashlib.sha256(raw.depth_y16_le).hexdigest(),
                'depth_to_color_translation_mm':list(m.depth_to_color.translation_mm),
            })
            last_preview=camera.read_next(per_attempt_timeout_ms=300,max_attempts=1)
    except Exception as exc:
        print('GD2_09_08_1_HARDWARE=FAIL',type(exc).__name__,str(exc),file=sys.stderr)
        return 1
    finally:
        try:
            camera.close()
        except Exception as exc:
            print('GD2_09_08_1_CLOSE=FAIL',type(exc).__name__,str(exc),file=sys.stderr)
            raise
    if len(set(x['capture_id'] for x in report))!=len(report):
        print('GD2_09_08_1_CAPTURE_IDS=FAIL',file=sys.stderr)
        return 1
    print(json.dumps({'result':'GD2_09_08_1_HARDWARE=PASS','captures':report},indent=2))
    print('NO_RAW_PERSISTED; NO_SQLITE_MODIFIED; NO_GIT_OPERATIONS')
    return 0

if __name__=='__main__':sys.exit(main())
