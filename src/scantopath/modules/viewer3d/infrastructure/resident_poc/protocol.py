"""Bounded request/response contracts for the R4.1 standalone renderer."""
from __future__ import annotations
import json
from typing import Any

MAX_MESSAGE_BYTES = 4096
MIN_SIZE = 128
MAX_SIZE = 1024


def decode_request(raw: bytes) -> dict[str, Any]:
    """Reject incomplete/oversized/ambiguous commands before dispatching to VTK."""
    if not raw.endswith(b'\n') or len(raw) > MAX_MESSAGE_BYTES:
        raise ValueError('INVALID_LINE')
    try:
        value = json.loads(raw)
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise ValueError('INVALID_JSON') from exc
    if not isinstance(value, dict) or set(value) - {'id', 'op', 'path', 'action', 'dx', 'dy', 'frame_mode', 'state', 'scene_revision', 'frame_revision', 'slot', 'expected_sha256'}:
        raise ValueError('INVALID_FIELDS')
    if type(value.get('id')) is not int or not 1 <= value['id'] <= 2**53:
        raise ValueError('INVALID_ID')
    if type(value.get('op')) is not str or value['op'] not in {
        'hello', 'open', 'open_scene', 'camera', 'set_camera', 'ack_frame', 'status', 'close_scene', 'shutdown'
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
