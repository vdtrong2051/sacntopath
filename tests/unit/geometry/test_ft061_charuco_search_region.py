from types import SimpleNamespace as NS
import numpy as np
from scantopath.modules.geometry.application.charuco_search_region import (
    projected_board_depth_rect,intersect_depth_rect)


def cal():
    return NS(depth_intrinsics=NS(width=1280,height=800,fx=610.,fy=610.,cx=640.,cy=400.),
        rotation_C_D=(1.,0.,0.,0.,1.,0.,0.,0.,1.),translation_C_D_m=(0.,0.,0.))


def test_projection_is_native_depth_rect_and_bounded():
    r=projected_board_depth_rect(np.eye(3),np.array([-.135,-.18,.90]),cal())
    assert r is not None
    assert 0<=r[0]<1280 and 0<=r[1]<800
    assert r[0]+r[2]<=1280 and r[1]+r[3]<=800
    assert r[0]<640<r[0]+r[2]
    assert r[1]<400<r[1]+r[3]


def test_intersection_preserves_manual_authority():
    assert intersect_depth_rect((10,10,100,100),(20,20,30,30))==(20,20,30,30)
    assert intersect_depth_rect(None,(5,6,7,8))==(5,6,7,8)
    assert intersect_depth_rect((1,1,10,10),(100,100,10,10)) is None


def test_too_near_camera_returns_none_and_not_untrusted_crop():
    r=projected_board_depth_rect(np.eye(3),np.array([0.,0.,.10]),cal())
    assert r is None


def test_grazing_pose_ninety_degree_relative_still_bounded_or_safe_full_fallback():
    theta=np.deg2rad(82.)
    R=np.array([[1,0,0],[0,np.cos(theta),-np.sin(theta)],
                 [0,np.sin(theta),np.cos(theta)]])
    r=projected_board_depth_rect(R,np.array([-.135,-.06,.80]),cal())
    assert r is None or (0<=r[0] and 0<=r[1] and r[0]+r[2]<=1280 and r[1]+r[3]<=800)
