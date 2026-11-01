"""FT-05.6: conservative, deterministic edge-aware local Depth support filter.

Operate ONLY on live-owned uint16 frames. No temporal 3D averaging, no changes to
RAW/metric reference, no OpenCV/VTK/SDK dependency, no filling missing pixels.
"""
from __future__ import annotations
import numpy as np


def local_depth_support_mask(depth_u16: np.ndarray, scale_m: float, *,
                             min_neighbors: int = 2,
                             tolerance_m: float = 0.035,
                             tolerance_fraction: float = 0.06) -> np.ndarray:
    if (not isinstance(depth_u16,np.ndarray) or depth_u16.dtype != np.uint16 or
            depth_u16.ndim != 2 or depth_u16.size == 0):
        raise ValueError('DENOISE_DEPTH_INVALID')
    if not (type(scale_m) in (int,float) and np.isfinite(scale_m) and scale_m > 0):
        raise ValueError('DENOISE_SCALE_INVALID')
    if (type(min_neighbors) is not int or not 1 <= min_neighbors <= 8 or
            not 0 < tolerance_m <= 1 or not 0 < tolerance_fraction <= 1):
        raise ValueError('DENOISE_CONFIG_INVALID')
    valid = (depth_u16 != 0) & (depth_u16 != 65535)
    h,w = depth_u16.shape
    # Tiny synthetic grids cannot establish spatial support without erasing
    # legitimate edges; still reject invalid sentinel pixels.
    if min(h,w) < 3:
        return valid
    metric = depth_u16.astype(np.float32) * np.float32(scale_m)
    threshold = np.maximum(np.float32(tolerance_m),
                           metric * np.float32(tolerance_fraction))
    neighbors = np.zeros((h,w), dtype=np.uint8)
    for dy,dx in ((-1,-1),(-1,0),(-1,1),(0,-1),(0,1),(1,-1),(1,0),(1,1)):
        ay0,ay1 = max(0,dy), min(h,h+dy)
        ax0,ax1 = max(0,dx), min(w,w+dx)
        by0,by1 = max(0,-dy), min(h,h-dy)
        bx0,bx1 = max(0,-dx), min(w,w-dx)
        close = (valid[ay0:ay1,ax0:ax1] & valid[by0:by1,bx0:bx1] &
                 (np.abs(metric[ay0:ay1,ax0:ax1] - metric[by0:by1,bx0:bx1]) <=
                  threshold[ay0:ay1,ax0:ax1]))
        neighbors[ay0:ay1,ax0:ax1] += close.astype(np.uint8)
    return valid & (neighbors >= min_neighbors)
