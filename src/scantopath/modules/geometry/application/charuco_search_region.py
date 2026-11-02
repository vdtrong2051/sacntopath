"""FT-06.1 conservative projected ChArUco-board 3D search volume in native Depth.

This is a computation shortcut / explicit search region. The per-pixel 3D
footprint and plane-height classifier remains the actual geometry authority.
Never aligns Depth pixels to RGB pixels and never fabricates a camera pose.
"""
from __future__ import annotations

import numpy as np


def projected_board_depth_rect(R_CB, t_CB, calibration, *, board_wh_m=(.27,.36),
                               max_height_m=.30, padding_px=16):
    """Return native Depth xywh conservative projection of board+height volume.

    Return None (search all Depth, with normal 3D classifier) if the projection
    is singular, out of view, or otherwise not reliable.  This is NEVER a mask.
    """
    k=calibration.depth_intrinsics
    R_CD=np.asarray(calibration.rotation_C_D,dtype=np.float64).reshape(3,3)
    t_CD=np.asarray(calibration.translation_C_D_m,dtype=np.float64)
    R=np.asarray(R_CB,dtype=np.float64).reshape(3,3)
    t=np.asarray(t_CB,dtype=np.float64).reshape(3)
    board_normal=R[:,2]
    if float(board_normal @ (-t)) < 0:
        board_normal=-board_normal
    points=[]
    for x in (0.,float(board_wh_m[0])):
        for y in (0.,float(board_wh_m[1])):
            base=R @ np.array([x,y,0.],dtype=np.float64)+t
            for height in (0.,float(max_height_m)):
                pc=base+board_normal*height
                pd=(pc-t_CD) @ R_CD
                points.append(pd)
    points=np.asarray(points,dtype=np.float64)
    if not np.isfinite(points).all() or np.any(points[:,2]<.14):
        return None
    uv=np.column_stack((points[:,0]/points[:,2]*k.fx+k.cx,
                        points[:,1]/points[:,2]*k.fy+k.cy))
    if not np.isfinite(uv).all():
        return None
    vmin=uv.min(axis=0)
    vmax=uv.max(axis=0)
    if np.any(vmax-vmin<1.):
        return None
    margin=max(int(padding_px),int(.04*max(vmax-vmin)))
    x0=max(0,int(np.floor(vmin[0]))-margin)
    y0=max(0,int(np.floor(vmin[1]))-margin)
    x1=min(k.width,int(np.ceil(vmax[0]))+margin+1)
    y1=min(k.height,int(np.ceil(vmax[1]))+margin+1)
    if x1-x0<4 or y1-y0<4:
        return None
    return x0,y0,x1-x0,y1-y0


def intersect_depth_rect(a,b):
    if a is None:
        return b
    if b is None:
        return a
    x0=max(a[0],b[0]);y0=max(a[1],b[1])
    x1=min(a[0]+a[2],b[0]+b[2]);y1=min(a[1]+a[3],b[1]+b[3])
    if x1-x0<4 or y1-y0<4:
        return None
    return x0,y0,x1-x0,y1-y0
