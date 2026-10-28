"""VTK-only camera projection of a GUI-owned camera intent (child process only)."""
from __future__ import annotations
import math
from ..application.navigation import CameraView


def configure_scene(renderer, view: CameraView):
    """Return a disposable axes actor if requested; never write geometry."""
    if not isinstance(view, CameraView):
        raise TypeError("CameraView required")
    renderer.ResetCamera()
    camera = renderer.GetActiveCamera()
    camera.Azimuth(view.azimuth)
    camera.Elevation(view.elevation)
    camera.OrthogonalizeViewUp()
    # Pan vector is derived from CURRENT screen basis (not a world pose).
    pos = camera.GetPosition()
    target = camera.GetFocalPoint()
    up = camera.GetViewUp()
    forward = [target[i] - pos[i] for i in range(3)]
    right = [forward[1]*up[2]-forward[2]*up[1],
             forward[2]*up[0]-forward[0]*up[2],
             forward[0]*up[1]-forward[1]*up[0]]
    mag = math.sqrt(sum(x*x for x in right))
    distance = math.sqrt(sum(x*x for x in forward))
    if mag < 1e-14 or not math.isfinite(distance):
        raise ValueError("Invalid camera basis")
    right = [x/mag for x in right]
    height = 2.0*distance*math.tan(math.radians(camera.GetViewAngle())/2.0)
    width = height*1000.0/620.0
    shift = [-view.pan_x*width*right[i] + view.pan_y*height*up[i] for i in range(3)]
    camera.SetPosition(*(pos[i] + shift[i] for i in range(3)))
    camera.SetFocalPoint(*(target[i] + shift[i] for i in range(3)))
    camera.Zoom(view.zoom)
    axes_actor = None
    if view.axes:
        from vtkmodules.vtkRenderingAnnotation import vtkAxesActor
        bounds = renderer.ComputeVisiblePropBounds()
        if not all(math.isfinite(float(x)) for x in bounds):
            raise ValueError("Cannot locate reference axes")
        span = max(bounds[1]-bounds[0],bounds[3]-bounds[2],bounds[5]-bounds[4])
        length = max(span*0.18, 1e-8)
        axes_actor = vtkAxesActor()
        axes_actor.SetTotalLength(length,length,length)
        axes_actor.SetPosition(bounds[0],bounds[2],bounds[4])
        renderer.AddActor(axes_actor)
    renderer.ResetCameraClippingRange()
    return axes_actor
