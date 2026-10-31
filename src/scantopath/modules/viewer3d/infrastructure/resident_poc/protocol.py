"""Hợp đồng yêu cầu/phản hồi IPC có giới hạn cho Render Host tách tiến trình."""
from __future__ import annotations
import json
from typing import Any

MAX_MESSAGE_BYTES = 4096
MIN_SIZE = 128
MAX_SIZE = 1024


def decode_request(raw: bytes) -> dict[str, Any]:
    """Từ chối lệnh thiếu, quá kích thước hoặc nhập nhằng trước khi giao cho VTK."""
    if not raw.endswith(b'\n') or len(raw) > MAX_MESSAGE_BYTES:
        raise ValueError('INVALID_LINE')
    try:
        value = json.loads(raw)
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise ValueError('INVALID_JSON') from exc
    if not isinstance(value, dict) or set(value) - {'id', 'op', 'path', 'action', 'dx', 'dy', 'frame_mode', 'state', 'scene_revision', 'frame_revision', 'slot', 'expected_sha256', 'u', 'v', 'visible', 'enabled', 'mode'}:
        raise ValueError('INVALID_FIELDS')
    if type(value.get('id')) is not int or not 1 <= value['id'] <= 2**53:
        raise ValueError('INVALID_ID')
    if type(value.get('op')) is not str or value['op'] not in {
        'hello', 'open', 'open_scene', 'camera', 'set_camera', 'ack_frame', 'status', 'close_scene', 'shutdown', 'pick', 'set_visibility', 'set_grid'
    }:
        raise ValueError('INVALID_OP')
    allowed = {
        'hello': {'id', 'op'}, 'open': {'id', 'op', 'path'},
        'open_scene': {'id', 'op', 'path'},
        'set_camera': {'id', 'op', 'state'},
        'ack_frame': {'id', 'op', 'scene_revision', 'frame_revision', 'slot'},
        'camera': {'id', 'op', 'action', 'dx', 'dy'},
        'status': {'id', 'op'}, 'close_scene': {'id', 'op'},
        'shutdown': {'id', 'op'},
        'pick': {'id', 'op', 'u', 'v', 'scene_revision', 'frame_revision'},
        'set_visibility': {'id', 'op', 'visible'},
        'set_grid': {'id', 'op', 'enabled', 'mode'},
    }[value['op']]
    if value['op'] == 'hello' and set(value) == {'id', 'op', 'frame_mode'}:
        if value['frame_mode'] != 'ack':
            raise ValueError('INVALID_FRAME_MODE')
    elif (value['op'] == 'open_scene' and
          set(value) == {'id', 'op', 'path', 'expected_sha256'}):
        from ...application.scene_contracts import SceneSource
        SceneSource(value['path'], value['expected_sha256'])
    elif set(value) != allowed:
        raise ValueError('INVALID_FIELDS')
    if value['op'] == 'ack_frame':
        for field in ('scene_revision', 'frame_revision'):
            if type(value[field]) is not int or not 0 <= value[field] <= 2**53:
                raise ValueError('INVALID_FRAME_ACK')
        if type(value['slot']) is not int or value['slot'] not in (0, 1):
            raise ValueError('INVALID_FRAME_ACK')
    if value['op'] == 'pick':
        for name in ('scene_revision', 'frame_revision'):
            if type(value[name]) is not int or not 0 <= value[name] <= 2**53:
                raise ValueError('INVALID_PICK_REVISION')
        for name in ('u', 'v'):
            x = value[name]
            if type(x) not in (int, float) or not 0.0 <= x <= 1.0:
                raise ValueError('INVALID_PICK_COORDINATE')
    if value['op'] == 'set_grid' and (type(value['enabled']) is not bool or
                                      value['mode'] not in ('xy', 'xz', 'yz', 'base')):
        raise ValueError('INVALID_REFERENCE_GRID')
    if value['op'] == 'set_visibility' and type(value['visible']) is not bool:
        raise ValueError('INVALID_LAYER_VISIBILITY')
    if value['op'] == 'set_camera':
        from ...application.navigation import CameraView
        CameraView.from_json(value['state'])
    if value['op'] in ('open', 'open_scene'):
        path = value['path']
        if type(path) is not str or not path or len(path) > 1024 or '\x00' in path:
            raise ValueError('INVALID_PATH')
    if value['op'] == 'camera':
        from ...application.navigation import CameraView
        CameraView().update(value['action'], value['dx'], value['dy'])
    return value


def encode_response(value: dict[str, Any]) -> bytes:
    return (json.dumps(value, ensure_ascii=True, separators=(',', ':'), allow_nan=False) + '\n').encode('ascii')
