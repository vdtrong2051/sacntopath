"""08.05 point selection contracts: no Qt, VTK, file I/O or metric claims."""
from __future__ import annotations
from dataclasses import dataclass
import math


def image_click_uv(x: float, y: float, label_w: int, label_h: int,
                   shown_w: int, shown_h: int) -> tuple[float, float] | None:
    """Map a Qt KeepAspectRatio centered pixmap click to bottom-left VTK UV.

    The displayed pixmap already has its final logical size (high-DPI safe).
    Empty letterboxing is NOT a selectable surface.
    """
    if (any(type(n) not in (float, int) or not math.isfinite(n) for n in (x,y))
            or any(type(n) is not int or n <= 1 for n in (label_w,label_h,shown_w,shown_h))
            or shown_w > label_w or shown_h > label_h):
        raise ValueError('Invalid displayed image geometry')
    left = (label_w - shown_w) / 2.0
    top = (label_h - shown_h) / 2.0
    px = x - left
    py = y - top
    if px < 0 or py < 0 or px > shown_w - 1 or py > shown_h - 1:
        return None
    return (px / (shown_w - 1), 1.0 - py / (shown_h - 1))


@dataclass(frozen=True, slots=True)
class PickResult:
    hit: bool
    point_id: int | None
    xyz: tuple[float, float, float] | None
    rgb: tuple[int, int, int] | None
    display_uv: tuple[float, float] | None
    source_id: str
    units: str = 'unknown'
    coordinate_frame: str = 'unknown'

    @classmethod
    def from_result(cls, data: dict) -> 'PickResult':
        if not isinstance(data, dict) or set(data) != {
            'hit','point_id','xyz','rgb','display_uv','source_id','units','coordinate_frame'
        }:
            raise ValueError('Invalid pick payload fields')
        hit=data['hit']
        source=data['source_id']
        if type(hit) is not bool or not isinstance(source,str) or not 1<=len(source)<=120:
            raise ValueError('Invalid pick identity')
        if data['units'] != 'unknown' or data['coordinate_frame'] != 'unknown':
            raise ValueError('Unverified point coordinates must not declare metric validity')
        if not hit:
            if any(data[x] is not None for x in ('point_id','xyz','rgb','display_uv')):
                raise ValueError('No-hit result cannot carry stale point data')
            return cls(False,None,None,None,None,source)
        pid=data['point_id'];xyz=data['xyz'];rgb=data['rgb'];uv=data['display_uv']
        if type(pid) is not int or pid<0:
            raise ValueError('Invalid point ID')
        if not isinstance(xyz,(list,tuple)) or len(xyz)!=3 or any(
            type(v) not in (float,int) or not math.isfinite(v) for v in xyz):
            raise ValueError('Invalid XYZ coordinates')
        if rgb is not None and (not isinstance(rgb,(list,tuple)) or len(rgb)!=3
            or any(type(v) is not int or not 0<=v<=255 for v in rgb)):
            raise ValueError('Invalid RGB')
        if not isinstance(uv,(list,tuple)) or len(uv)!=2 or any(
            type(v) not in (int,float) or not math.isfinite(v) or not 0<=v<=1 for v in uv):
            raise ValueError('Invalid picked pixel')
        return cls(True,pid,tuple(float(v) for v in xyz),
                   None if rgb is None else tuple(rgb),tuple(float(v) for v in uv),source)
