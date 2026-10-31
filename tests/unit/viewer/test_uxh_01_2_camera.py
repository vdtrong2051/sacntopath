"""UXH-01.2 camera pan must use provided render-frame aspect."""
import math
import pytest
from scantopath.modules.viewer3d.application.navigation import CameraView
from scantopath.modules.viewer3d.infrastructure.camera_scene import configure_scene


class Camera:
    def __init__(self):
        self.p = (0., 0., 10.)
        self.f = (0., 0., 0.)
        self.u = (0., 1., 0.)
    def GetPosition(self): return self.p
    def GetFocalPoint(self): return self.f
    def GetViewUp(self): return self.u
    def SetPosition(self, *v): self.p = tuple(v)
    def SetFocalPoint(self, *v): self.f = tuple(v)
    def SetViewUp(self, *v): self.u = tuple(v)
    def Azimuth(self, v): pass
    def Elevation(self, v): pass
    def OrthogonalizeViewUp(self): pass
    def GetViewAngle(self): return 30.
    def Zoom(self, v): pass


class Renderer:
    def __init__(self): self.camera = Camera()
    def ResetCamera(self): pass
    def GetActiveCamera(self): return self.camera
    def ResetCameraClippingRange(self): pass


@pytest.mark.parametrize('aspect', [4/3, 16/9, 1.0])
def test_pan_scales_with_real_aspect(aspect):
    renderer = Renderer()
    configure_scene(renderer, CameraView(pan_x=0.1, pan_y=0), viewport_aspect=aspect)
    f = renderer.camera.f
    height = 2 * 10 * math.tan(math.radians(30)/2)
    assert abs(f[0]) == pytest.approx(0.1 * height * aspect)
    assert f[1] == 0


@pytest.mark.parametrize('aspect', [0, -1, float('nan'), float('inf'), True])
def test_invalid_aspect_fail_closed(aspect):
    with pytest.raises(ValueError, match='INVALID_VIEWPORT_ASPECT'):
        configure_scene(Renderer(), CameraView(), viewport_aspect=aspect)


def test_no_aspect_in_renderer_fallback_is_defined():
    renderer = Renderer()
    configure_scene(renderer, CameraView(pan_x=0.1))
    assert math.isfinite(renderer.camera.p[0])
