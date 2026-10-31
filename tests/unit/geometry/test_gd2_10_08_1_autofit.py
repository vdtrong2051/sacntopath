"""GD2-10.08.1: robust sensor angular fit / data preserved / Preview-only grid.

No RAW, SQLite, VTK process, or camera required for pure geometry tests.
"""
import math
import numpy as np
import pytest

from scantopath.modules.viewer3d.infrastructure.camera_scene import (
    sensor_angular_fit, configure_scene,
)
from scantopath.modules.viewer3d.application.navigation import CameraView


class Cam:
    def __init__(self):
        self.position=(3.,-2.,11.); self.focus=(3.,-2.,1.)
        self.up=(0.,1.,0.); self.angle=30.; self.zoom=1.
    def GetPosition(self):return self.position
    def GetFocalPoint(self):return self.focus
    def GetViewUp(self):return self.up
    def GetViewAngle(self):return self.angle
    def SetPosition(self,*v):self.position=tuple(v)
    def SetFocalPoint(self,*v):self.focus=tuple(v)
    def SetViewUp(self,*v):self.up=tuple(v)
    def SetViewAngle(self,v):self.angle=float(v)
    def Azimuth(self,v):pass
    def Elevation(self,v):pass
    def OrthogonalizeViewUp(self):pass
    def Zoom(self,z):self.zoom=float(z)

class Renderer:
    def __init__(self):self.cam=Cam()
    def ResetCamera(self):pass
    def GetActiveCamera(self):return self.cam
    def ResetCameraClippingRange(self):pass


def example():
    t=np.linspace(-1,1,1001)
    xyz=np.column_stack((0.3*t,0.12*t,2.+0*t)).astype(np.float64)
    return xyz


def test_angle_fits_distribution_not_extreme_bbox():
    good=example(); before=good.copy()
    a=sensor_angular_fit(good, 4/3)
    out=np.vstack((good,[[150.,60.,2.],[-150.,-60.,2.]]))
    b=sensor_angular_fit(out, 4/3)
    assert b[2] == pytest.approx(a[2],rel=.03)
    assert -0.01 < b[0] < .01 and -0.01 < b[1] < .01
    assert 18 <= a[2] <= 100
    np.testing.assert_array_equal(good,before)


def test_physical_depth_view_and_reset_keep_preset():
    hint=sensor_angular_fit(example(),4/3)
    viewer=Renderer()
    configure_scene(viewer,CameraView().update('sensor_view'),sensor_fit=hint)
    assert viewer.cam.position==(0.,0.,0.)
    assert viewer.cam.focus[2]==1.
    assert viewer.cam.up==(0.,-1.,0.)
    assert viewer.cam.angle==pytest.approx(hint[2])
    assert CameraView(sensor_view=True).update('reset').sensor_view


def test_external_ply_default_unchanged():
    renderer=Renderer()
    configure_scene(renderer,CameraView())
    assert renderer.cam.position==(3.,-2.,11.)
    assert renderer.cam.up==(0.,1.,0.)
    assert renderer.cam.angle==30.


@pytest.mark.parametrize('bad,aspect', [
    (np.array([[0.,0.,0.],[1.,1.,1.]]),1.5),
    (np.array([[0.,0.,-1.],[1.,1.,1.]]),1.5),
    (np.array([[0.,0.,1.]]),1.5),
    (np.array([[0.,0.,1.],[1.,1.,1.]]),0),
    (np.array([[float('nan'),0.,1.],[1.,1.,1.]]),1.5),
])
def test_invalid_rays_fail_closed(bad,aspect):
    with pytest.raises(ValueError):sensor_angular_fit(bad,aspect)


def test_grid_default_is_linked_only_to_explicit_sensor_preset():
    # The callback toggles the existing Qt button, preserving its signal/host sync.
    from pathlib import Path
    import scantopath.ui.shell.geometry_preview as gp
    text=Path(gp.__file__).read_text(encoding='utf-8')
    assert 'if not viewer.navigate("sensor_view")' in text
    assert 'if grid is not None and grid.isChecked()' in text
    assert 'grid.setChecked(False)' in text
    assert 'if token != self._sensor_view_token:' in text


def test_camera_fit_is_finite_and_fov_bounded():
    rng=np.random.default_rng(50)
    xyz=rng.normal(size=(1000,3))
    xyz[:,2]=rng.uniform(.4,5.,size=1000)
    x,y,angle=sensor_angular_fit(xyz,1.3333)
    assert all(math.isfinite(a) for a in (x,y,angle))
    assert 18. <= angle <= 100.
