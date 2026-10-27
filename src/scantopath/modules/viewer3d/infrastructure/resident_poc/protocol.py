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
    if not isinstance(value, dict) or set(value) - {'id', 'op', 'path', 'action', 'dx', 'dy'}:
        raise ValueError('INVALID_FIELDS')
    if type(value.get('id')) is not int or not 1 <= value['id'] <= 2**53:
        raise ValueError('INVALID_ID')
    if type(value.get('op')) is not str or value['op'] not in {
        'hello', 'open', 'camera', 'status', 'close_scene', 'shutdown'
    }:
        raise ValueError('INVALID_OP')
    allowed = {
        'hello': {'id', 'op'}, 'open': {'id', 'op', 'path'},
        'camera': {'id', 'op', 'action', 'dx', 'dy'},
        'status': {'id', 'op'}, 'close_scene': {'id', 'op'},
        'shutdown': {'id', 'op'},
    }[value['op']]
    if set(value) != allowed:
        raise ValueError('INVALID_FIELDS')
    if value['op'] == 'open':
        path = value['path']
        if type(path) is not str or not path or len(path) > 1024 or '\x00' in path:
            raise ValueError('INVALID_PATH')
    if value['op'] == 'camera':
        from ...application.navigation import CameraView
        CameraView().update(value['action'], value['dx'], value['dy'])
    return value


def encode_response(value: dict[str, Any]) -> bytes:
    return (json.dumps(value, ensure_ascii=True, separators=(',', ':'), allow_nan=False) + '\n').encode('ascii')
