"""GD2-10.08.1 sensor-facing camera preset: never transform XYZ/PLY."""
from __future__ import annotations

import math

import pytest

from scantopath.modules.viewer3d.application.navigation import CameraView
from scantopath.modules.viewer3d.infrastructure.camera_scene import configure_scene


class DummyCamera:
    def __init__(self):
        self.position = (3.0, -2.0, 11.0)
        self.focus = (3.0, -2.0, 1.0)
        self.up = (0.0, 1.0, 0.0)
        self.azimuth = self.elevation = 0.0
        self.zoom = 1.0
    def GetPosition(self):return self.position
    def GetFocalPoint(self):return self.focus
    def GetViewUp(self):return self.up
    def SetPosition(self,*v):self.position=tuple(v)
    def SetFocalPoint(self,*v):self.focus=tuple(v)
    def SetViewUp(self,*v):self.up=tuple(v)
    def Azimuth(self,v):self.azimuth=float(v)
    def Elevation(self,v):self.elevation=float(v)
    def OrthogonalizeViewUp(self):pass
    def GetViewAngle(self):return 30.0
    def Zoom(self,v):self.zoom=float(v)


class DummyRenderer:
    def __init__(self):self.camera=DummyCamera();self.reset_count=0;self.clip_count=0
    def ResetCamera(self):self.reset_count+=1
    def GetActiveCamera(self):return self.camera
    def ResetCameraClippingRange(self):self.clip_count+=1


def test_regular_ply_legacy_default_unchanged():
    renderer=DummyRenderer()
    configure_scene(renderer,CameraView())
    assert renderer.camera.position==(3.0,-2.0,11.0)
    assert renderer.camera.up==(0.0,1.0,0.0)
    assert renderer.reset_count == renderer.clip_count == 1


def test_sensor_preview_faces_forward_depth_with_y_up_inverted():
    renderer=DummyRenderer()
    view=CameraView().update('sensor_view')
    assert view.sensor_view is True
    configure_scene(renderer,view)
    cam=renderer.camera
    assert cam.position==(3.0,-2.0,-9.0)
    assert cam.focus==(3.0,-2.0,1.0)
    assert cam.up==(0.0,-1.0,0.0)
    forward=tuple(cam.focus[i]-cam.position[i] for i in range(3))
    right=(forward[1]*cam.up[2]-forward[2]*cam.up[1],
           forward[2]*cam.up[0]-forward[0]*cam.up[2],
           forward[0]*cam.up[1]-forward[1]*cam.up[0])
    assert forward[2]>0 and right[0]>0


def test_orbit_zoom_and_fit_preserve_sensor_preset():
    view=CameraView().update('sensor_view')
    modified=view.update('orbit',40,15).update('pan',30,0).update('zoom',1,0)
    assert modified.sensor_view is True
    assert modified.update('reset')==CameraView(sensor_view=True)
    assert CameraView().update('reset') == CameraView()
    assert CameraView.from_json(modified.to_json()) == modified


def test_sensor_view_explicit_flag_validation():
    with pytest.raises(ValueError,match='sensor_view'):
        CameraView(sensor_view=1)
    with pytest.raises(ValueError,match='sensor_view'):
        CameraView.from_json(CameraView(sensor_view=True).to_json().replace('"sensor_view":true','"sensor_view":1'))


def test_no_xyz_transform_in_camera_configuration():
    renderer=DummyRenderer()
    before=((1.0,2.0,3.0),(-1.0,0.0,5.0))
    configure_scene(renderer, CameraView(sensor_view=True))
    assert before==((1.0,2.0,3.0),(-1.0,0.0,5.0))
    assert math.isfinite(renderer.camera.position[2])
