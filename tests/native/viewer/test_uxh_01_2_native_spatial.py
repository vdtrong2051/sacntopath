"""UXH-01.2 native VTK actors (no Qt or device)."""
from types import SimpleNamespace
import math
import pytest

pytest.importorskip('vtkmodules')
from vtkmodules.vtkRenderingCore import vtkRenderer, vtkActor, vtkPolyDataMapper
from vtkmodules.vtkCommonCore import vtkPoints
from vtkmodules.vtkCommonDataModel import vtkPolyData, vtkCellArray
from scantopath.modules.viewer3d.infrastructure.resident_poc.host import PersistentScene
from scantopath.modules.viewer3d.infrastructure.camera_scene import configure_scene
from scantopath.modules.viewer3d.application.navigation import CameraView


def test_reference_planes_actor_non_pickable_and_no_cloud_mutation():
    b = (2., 4., 3., 5., 6., 8.)
    host = PersistentScene(800, 600, SimpleNamespace())
    host.renderer = vtkRenderer()
    host._loaded = SimpleNamespace(descriptor=SimpleNamespace(bounds=b))
    for mode, normal, val in [('xy', 2, 0), ('xz', 1, 0),
                              ('yz', 0, 0), ('base', 2, 6)]:
        host.grid_mode = mode
        host.grid_enabled = True
        host._build_reference_grid()
        actor = host.grid_actor
        assert actor is not None and actor.GetPickable() == 0
        data = actor.GetMapper().GetInput()
        assert data.GetNumberOfLines() == 42
        assert all(abs(data.GetPoint(i)[normal] - val) < 1e-5
                   for i in range(data.GetNumberOfPoints()))
        assert b == (2., 4., 3., 5., 6., 8.)
        assert host.renderer.GetActors().GetNumberOfItems() == 1
    host.close_scene()
    assert host.renderer.GetActors().GetNumberOfItems() == 0


def test_coordinate_axes_at_origin_and_not_pickable():
    renderer = vtkRenderer()
    poly = vtkPolyData()
    pts = vtkPoints()
    for p in ((2.0, 3.0, 5.0), (3.0, 4.0, 6.0)):
        pts.InsertNextPoint(*p)
    cells = vtkCellArray()
    for i in (0, 1):
        cells.InsertNextCell(1)
        cells.InsertCellPoint(i)
    poly.SetPoints(pts)
    poly.SetVerts(cells)
    mapper = vtkPolyDataMapper()
    mapper.SetInputData(poly)
    actor = vtkActor()
    actor.SetMapper(mapper)
    renderer.AddActor(actor)
    axes = configure_scene(renderer, CameraView(axes=True), viewport_aspect=4/3)
    assert axes is not None
    assert axes.GetPickable() == 0
    assert axes.GetPosition() == (0.0, 0.0, 0.0)
    assert poly.GetPoints().GetPoint(0) == pytest.approx((2, 3, 5))
    # Coordinate axes must not itself rewrite the scene geometry.
    assert math.isfinite(renderer.GetActiveCamera().GetPosition()[0])
