"""UXH-01.5: strict, renderer-independent validation of native pick replies.

An IPC reply is untrusted until it matches the active scene *and* frame.
This module does not perform a measurement and establishes no metric provenance.
"""
from __future__ import annotations

import math
from typing import Any

from .scene_contracts import SceneDescriptor, SceneSelectionRef


class StalePickResult(ValueError):
    """A valid identity envelope points to a different displayed scene/frame."""


def _integer(value: Any, *, minimum: int = 0) -> bool:
    return type(value) is int and minimum <= value <= 2**53


def validate_native_pick(
    payload: object,
    descriptor: SceneDescriptor,
    scene_revision: int,
    frame_revision: int,
) -> SceneSelectionRef | None:
    """Decode one Render Host reply into a typed source-backed selection.

    Returns None for a genuine miss; raises StalePickResult for an obsolete
    reply; raises ValueError/TypeError for any malformed/unsupported payload.
    Neither a miss nor a bad reply can introduce a fabricated metric claim.
    """
    if not isinstance(descriptor, SceneDescriptor):
        raise TypeError('PICK_DESCRIPTOR_INVALID')
    if not _integer(scene_revision, minimum=1) or not _integer(frame_revision):
        raise ValueError('PICK_CURRENT_REVISION_INVALID')
    if type(payload) is not dict:
        raise TypeError('PICK_RESULT_NOT_DICT')
    base = {'scene_revision', 'frame_revision', 'source_sha256',
            'geometry_kind', 'units', 'coordinate_frame', 'hit'}
    hit_fields = {'kind', 'element_id', 'xyz'} if payload.get('hit') is True else set()
    expected = base | hit_fields
    envelope = {'id', 'ok'}
    if envelope & payload.keys():
        if not envelope <= payload.keys():
            raise ValueError('PICK_IPC_ENVELOPE_INCOMPLETE')
        if not _integer(payload['id'], minimum=1) or payload['ok'] is not True:
            raise ValueError('PICK_IPC_ENVELOPE_INVALID')
        expected |= envelope
    if set(payload) != expected or type(payload.get('hit')) is not bool:
        raise ValueError('PICK_RESULT_FIELDS_INVALID')
    if not _integer(payload['scene_revision'], minimum=1) or not _integer(payload['frame_revision']):
        raise ValueError('PICK_RESULT_REVISION_INVALID')
    if type(payload['source_sha256']) is not str or type(payload['geometry_kind']) is not str:
        raise ValueError('PICK_RESULT_SOURCE_INVALID')
    if payload['units'] != 'unknown' or payload['coordinate_frame'] != 'unknown':
        raise ValueError('PICK_PROVENANCE_UNVERIFIED')
    if (payload['scene_revision'] != scene_revision or
            payload['frame_revision'] != frame_revision or
            payload['source_sha256'] != descriptor.source_sha256 or
            payload['geometry_kind'] != descriptor.geometry_kind):
        raise StalePickResult('PICK_RESULT_STALE')
    if not payload['hit']:
        return None
    kind = payload['kind']
    expected_kind = 'face' if descriptor.geometry_kind == 'mesh' else 'point'
    if type(kind) is not str or kind != expected_kind:
        raise ValueError('PICK_KIND_MISMATCH')
    idx = payload['element_id']
    limit = descriptor.face_count if kind == 'face' else descriptor.point_count
    if not _integer(idx) or idx >= limit:
        raise ValueError('PICK_ELEMENT_OUT_OF_BOUNDS')
    xyz = payload['xyz']
    if (type(xyz) not in (list, tuple) or len(xyz) != 3 or
            any(type(v) not in (int, float) or not math.isfinite(v) for v in xyz)):
        raise ValueError('PICK_XYZ_INVALID')
    return SceneSelectionRef(descriptor.source_sha256, scene_revision,
                             kind, idx, tuple(float(v) for v in xyz))
