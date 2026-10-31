"""VTK-only camera projection of a GUI-owned camera intent (child process only)."""
from __future__ import annotations
import math
import numpy as np
from ..application.navigation import CameraView


def sensor_angular_fit(xyz: np.ndarray, aspect: float) -> tuple[float, float, float]:
    # Fit central 90 percent of camera rays without removing any vertices.
    # Depth optical: X right, Y down, Z forward.
    if (not isinstance(xyz, np.ndarray) or xyz.ndim != 2 or
            xyz.shape[1] != 3 or xyz.shape[0] < 2 or
            not isinstance(aspect, (int, float)) or isinstance(aspect, bool) or
            not math.isfinite(aspect) or aspect <= 0 or
            not np.isfinite(xyz).all() or np.any(xyz[:, 2] <= 0)):
        raise ValueError("INVALID_SENSOR_FIT_INPUT")
    rays = xyz[:, :2].astype(np.float64, copy=False) / xyz[:, 2:3]
    if not np.isfinite(rays).all():
        raise ValueError("NONFINITE_SENSOR_RAYS")
    low, high = np.quantile(rays, [0.05, 0.95], axis=0)
    center_x = float((low[0] + high[0]) * 0.5)
    center_y = float((low[1] + high[1]) * 0.5)
    half_y = float((high[1] - low[1]) * 0.5)
    half_x = float((high[0] - low[0]) * 0.5) / float(aspect)
    # A visible margin prevents the robust envelope from touching the frame.
    half_angle = max(0.06, half_x, half_y) * 1.18
    fov_degrees = max(18.0, min(100.0, math.degrees(2.0 * math.atan(half_angle))))
    if not all(math.isfinite(x) for x in (center_x,center_y,fov_degrees)):
        raise ValueError("INVALID_SENSOR_FIT_RESULT")
    return center_x, center_y, fov_degrees


def configure_scene(renderer, view: CameraView, *, sensor_fit=None):
    """Return a disposable axes actor if requested; never write geometry."""
    if not isinstance(view, CameraView):
        raise TypeError("CameraView required")
    renderer.ResetCamera()
    camera = renderer.GetActiveCamera()
    if view.sensor_view and sensor_fit is not None:
        if (len(sensor_fit) != 3 or
                not all(math.isfinite(float(v)) for v in sensor_fit) or
                not 18 <= float(sensor_fit[2]) <= 100):
            raise ValueError("INVALID_SENSOR_FIT")
        center_x, center_y, view_angle = (float(v) for v in sensor_fit)
        # Camera at the virtual Depth optical origin; +Z forward / -Y up.
        # Only projection is changed, not a single XYZ, color or PLY vertex.
        camera.SetPosition(0.0, 0.0, 0.0)
        camera.SetFocalPoint(center_x, center_y, 1.0)
        camera.SetViewUp(0.0, -1.0, 0.0)
        camera.SetViewAngle(view_angle)
    elif view.sensor_view:
        # Depth optical: +Z forward, +X right, +Y downward. A sensor-facing
        # virtual camera must look along +Z with screen up toward -Y.
        # Preserve full XYZ bounds/fit from VTK ResetCamera (no point transform).
        pos = camera.GetPosition()
        focus = camera.GetFocalPoint()
        distance = math.sqrt(sum((pos[i] - focus[i]) ** 2 for i in range(3)))
        if not math.isfinite(distance) or distance <= 1e-8:
            raise ValueError("Invalid sensor camera distance")
        camera.SetPosition(focus[0], focus[1], focus[2] - distance)
        camera.SetViewUp(0.0, -1.0, 0.0)
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
