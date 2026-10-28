"""VTK-only synthetic scene; must be constructed and used on the GUI thread.

This module does not import Qt, RAW, camera or any project persistence.
Do NOT use this as a PLY loader; real file I/O belongs to 08.03.
"""
from __future__ import annotations

from scantopath.modules.viewer3d.domain.fixture import FIVE_POINT_FIXTURE


class VtkFixtureScene:
    def __init__(self) -> None:
        from vtkmodules.vtkCommonCore import vtkPoints
        from vtkmodules.vtkCommonDataModel import vtkPolyData
        from vtkmodules.vtkFiltersGeneral import vtkVertexGlyphFilter
        from vtkmodules.vtkRenderingCore import vtkActor, vtkPolyDataMapper, vtkRenderer
        import vtkmodules.vtkRenderingOpenGL2  # noqa: F401 - registers rendering backend
        import vtkmodules.vtkInteractionStyle  # noqa: F401 - registers interactions

        self._points = vtkPoints()
        for x, y, z in FIVE_POINT_FIXTURE.points:
            self._points.InsertNextPoint(x, y, z)
        self._polydata = vtkPolyData()
        self._polydata.SetPoints(self._points)
        self._glyph = vtkVertexGlyphFilter()
        self._glyph.SetInputData(self._polydata)
        self._mapper = vtkPolyDataMapper()
        self._mapper.SetInputConnection(self._glyph.GetOutputPort())
        self._actor = vtkActor()
        self._actor.SetMapper(self._mapper)
        self._actor.GetProperty().SetPointSize(12)
        self._actor.GetProperty().SetColor(0.12, 0.52, 0.87)
        self._renderer = vtkRenderer()
        self._renderer.SetBackground(0.11, 0.15, 0.20)
        self._renderer.AddActor(self._actor)
        self._renderer.ResetCamera()
        self._disposed = False

    @property
    def renderer(self) -> object:
        return self._renderer

    @property
    def point_count(self) -> int:
        return int(self._polydata.GetNumberOfPoints())

    def dispose(self) -> None:
        if not self._disposed:
            self._renderer.RemoveActor(self._actor)
            self._disposed = True
