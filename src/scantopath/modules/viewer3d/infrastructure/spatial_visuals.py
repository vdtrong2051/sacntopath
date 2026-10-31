"""UXH-01.2-C01: restrained visual-only reference geometry for the VTK host.

The origin is the source-coordinate (0, 0, 0), never the bbox corner.
No labels or actors here certify a physical origin, world pose, or unit.
No import of VTK at module import time; native VTK remains host-owned.
"""
from __future__ import annotations

import math

# Colors are visual tokens only; they do not encode sensor provenance.
_AXIS_RGB = ((218, 98, 95), (106, 190, 112), (105, 149, 224))
_MAJOR_RGB = (110, 138, 168)
_MINOR_RGB = (68, 85, 106)
GRID_OPACITY = 0.29
GRID_MAJOR_INTERVAL = 5


def _span(bounds) -> float:
    if (not isinstance(bounds, (tuple, list)) or len(bounds) != 6 or
            any(type(x) not in (int, float) or not math.isfinite(x) for x in bounds) or
            any(bounds[k] > bounds[k + 1] for k in (0, 2, 4))):
        raise ValueError('INVALID_VISUAL_BOUNDS')
    span = max(float(bounds[k + 1] - bounds[k]) for k in (0, 2, 4))
    if not math.isfinite(span):
        raise ValueError('INVALID_VISUAL_BOUNDS')
    return max(span, 1e-6)


def origin_axes_length(bounds) -> float:
    """Source-relative length, deliberately smaller than the old 18%-span glyph."""
    return _span(bounds) * 0.065


def grid_line_rgb(segment_index: int) -> tuple[int, int, int]:
    """UXH-01.2 grid emits two lines for every offset -10..10 (42 total).

    Major lines are offset multiples of 5. The mapper colors *cells* rather
    than adding a second actor, preserving the existing native actor contract.
    """
    if type(segment_index) is not int or not 0 <= segment_index < 42:
        raise ValueError('INVALID_GRID_SEGMENT')
    line_offset = segment_index // 2 - 10
    return _MAJOR_RGB if line_offset % GRID_MAJOR_INTERVAL == 0 else _MINOR_RGB


def make_origin_axes(bounds):
    """Six slim unlabelled +/- axis strokes, non-pickable and excluded from fit."""
    length = origin_axes_length(bounds)
    from vtkmodules.vtkCommonCore import vtkPoints, vtkUnsignedCharArray
    from vtkmodules.vtkCommonDataModel import vtkCellArray, vtkPolyData
    from vtkmodules.vtkRenderingCore import vtkActor, vtkPolyDataMapper

    pts, cells = vtkPoints(), vtkCellArray()
    colors = vtkUnsignedCharArray()
    colors.SetName('OriginAxesRGB')
    colors.SetNumberOfComponents(3)
    for axis, rgb in enumerate(_AXIS_RGB):
        for positive in (False, True):
            start = [0., 0., 0.]
            end = [0., 0., 0.]
            # Short negative stroke and longer positive stroke; no oversized
            # arrows or 3D X/Y/Z letters occluding a model.
            end[axis] = length if positive else -0.22 * length
            a, b = pts.InsertNextPoint(*start), pts.InsertNextPoint(*end)
            cells.InsertNextCell(2)
            cells.InsertCellPoint(a)
            cells.InsertCellPoint(b)
            shade = rgb if positive else tuple(round(v * 0.57) for v in rgb)
            colors.InsertNextTuple3(*shade)
    poly = vtkPolyData()
    poly.SetPoints(pts)
    poly.SetLines(cells)
    poly.GetCellData().SetScalars(colors)
    mapper = vtkPolyDataMapper()
    mapper.SetInputData(poly)
    mapper.SetScalarModeToUseCellData()
    mapper.SetColorModeToDirectScalars()
    mapper.ScalarVisibilityOn()
    actor = vtkActor()
    actor.SetMapper(mapper)
    actor.GetProperty().SetLineWidth(2.0)
    actor.GetProperty().SetOpacity(0.88)
    actor.SetPosition(0.0, 0.0, 0.0)
    actor.PickableOff()
    actor.UseBoundsOff()  # This reference must never contribute to camera fit.
    return actor
