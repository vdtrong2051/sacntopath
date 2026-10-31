"""UXH-01.2-C01 native VTK: minimal origin axes and single-actor graded grid."""
from types import SimpleNamespace
import pytest

pytest.importorskip('vtkmodules')
from vtkmodules.vtkRenderingCore import vtkActor, vtkRenderer, vtkPolyDataMapper
from vtkmodules.vtkCommonDataModel import vtkPolyData, vtkCellArray
from vtkmodules.vtkCommonCore import vtkPoints
from scantopath.modules.viewer3d.infrastructure.spatial_visuals import (
    make_origin_axes, grid_line_rgb, origin_axes_length,
)
from scantopath.modules.viewer3d.infrastructure.resident_poc.host import PersistentScene


def test_slim_axes_have_no_text_no_picking_and_no_bounds():
    bounds = (2., 4., 3., 5., 6., 8.)
    actor = make_origin_axes(bounds)
    assert type(actor) is vtkActor  # Not the massive vtkAxesActor with 3D labels.
    assert actor.GetPosition() == (0., 0., 0.)
    assert actor.GetPickable() == 0
    assert actor.GetUseBounds() == 0
    poly = actor.GetMapper().GetInput()
    assert poly.GetNumberOfLines() == 6
    assert poly.GetNumberOfPoints() == 12
    assert poly.GetCellData().GetScalars().GetNumberOfTuples() == 6
    size = origin_axes_length(bounds)
    assert max(abs(poly.GetPoint(i)[0]) for i in range(12)) == pytest.approx(size)


def test_one_actor_42_lines_major_minor_coloring_and_replacement():
    bounds = (2., 4., 3., 5., 6., 8.)
    host = PersistentScene(800, 600, SimpleNamespace())
    host.renderer = vtkRenderer()
    host._loaded = SimpleNamespace(descriptor=SimpleNamespace(bounds=bounds))
    host.grid_enabled = True
    for mode in ('xy', 'xz', 'yz', 'base'):
        host.grid_mode = mode
        host._build_reference_grid()
        actor = host.grid_actor
        assert actor.GetPickable() == 0 and actor.GetUseBounds() == 0
        data = actor.GetMapper().GetInput()
        assert data.GetNumberOfLines() == 42
        colors = data.GetCellData().GetScalars()
        assert colors.GetNumberOfTuples() == 42
        for idx in (0, 5, 10, 20, 41):
            assert tuple(int(v) for v in colors.GetTuple3(idx)) == grid_line_rgb(idx)
        assert host.renderer.GetActors().GetNumberOfItems() == 1
    host.close_scene()
    assert host.renderer.GetActors().GetNumberOfItems() == 0


def test_axes_are_excluded_from_visible_bounds():
    renderer = vtkRenderer()
    points = vtkPoints()
    points.InsertNextPoint(2., 3., 5.)
    points.InsertNextPoint(4., 5., 8.)
    verts = vtkCellArray()
    for index in (0, 1):
        verts.InsertNextCell(1)
        verts.InsertCellPoint(index)
    cloud = vtkPolyData()
    cloud.SetPoints(points)
    cloud.SetVerts(verts)
    mapper = vtkPolyDataMapper()
    mapper.SetInputData(cloud)
    source_actor = vtkActor()
    source_actor.SetMapper(mapper)
    renderer.AddActor(source_actor)
    before = renderer.ComputeVisiblePropBounds()
    renderer.AddActor(make_origin_axes(before))
    after = renderer.ComputeVisiblePropBounds()
    assert after == pytest.approx(before)
