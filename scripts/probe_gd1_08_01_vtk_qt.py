"""Isolated 08.01 VTK+PySide6 compatibility probe; NO project/RAW/camera imports.

Run with --mode import before --mode window. For a Windows hardware desktop the
window mode exercises a real Qt event loop and OpenGL render, not QT offscreen.
"""
from __future__ import annotations
import argparse
import json
import platform
import sys
from pathlib import Path


def probe(mode: str) -> dict[str, object]:
    # Qt must be loaded FIRST so VTK resolves the PySide6 backend rather than
    # selecting a different installed Qt binding on the machine.
    import PySide6
    from PySide6.QtCore import QTimer
    from PySide6.QtWidgets import QApplication
    import vtkmodules.qt
    vtkmodules.qt.PyQtImpl = 'PySide6'
    from vtkmodules.qt.QVTKRenderWindowInteractor import QVTKRenderWindowInteractor
    from vtkmodules.vtkCommonCore import vtkPoints, vtkVersion
    from vtkmodules.vtkCommonDataModel import vtkPolyData
    from vtkmodules.vtkFiltersGeneral import vtkVertexGlyphFilter
    from vtkmodules.vtkRenderingCore import vtkActor, vtkPolyDataMapper, vtkRenderer
    import vtkmodules.vtkRenderingOpenGL2  # noqa: F401: register OpenGL renderer
    import vtkmodules.vtkInteractionStyle  # noqa: F401: register interaction styles

    if vtkmodules.qt.PyQtImpl != 'PySide6':
        raise RuntimeError('VTK selected a Qt binding other than PySide6')

    data: dict[str, object] = {
        'stage': 'GD1-08.01', 'mode': mode, 'python': platform.python_version(),
        'platform': platform.platform(), 'pyside6': PySide6.__version__,
        'vtk': vtkVersion.GetVTKVersion(), 'qt_binding': vtkmodules.qt.PyQtImpl,
        'import_pass': True, 'render_pass': False,
        'source': 'isolated probe; no PLY, camera or persisted project data',
    }
    if mode == 'import':
        return data

    # Interactive real-window smoke: intentionally NOT a headless acceptance
    # proof. A human still needs to confirm points and mouse interaction.
    if QApplication.instance() is not None:
        raise RuntimeError('The VTK probe must own its isolated QApplication')
    app = QApplication(['scantopath-vtk-08-01-probe'])
    window = QVTKRenderWindowInteractor()
    window.resize(720, 510)
    window.setWindowTitle('ScanToPath 08.01 — VTK/PySide6 Visual Probe (fixture)')
    renderer = vtkRenderer()
    window.GetRenderWindow().AddRenderer(renderer)
    points = vtkPoints()
    for xyz in ((0.0, 0.0, 0.0), (0.25, 0.0, 0.0),
                (0.0, 0.25, 0.0), (0.0, 0.0, 0.25), (0.25, 0.25, 0.25)):
        points.InsertNextPoint(*xyz)
    cloud = vtkPolyData()
    cloud.SetPoints(points)
    glyph = vtkVertexGlyphFilter()
    glyph.SetInputData(cloud)
    mapper = vtkPolyDataMapper()
    mapper.SetInputConnection(glyph.GetOutputPort())
    actor = vtkActor()
    actor.SetMapper(mapper)
    actor.GetProperty().SetPointSize(12)
    renderer.AddActor(actor)
    renderer.ResetCamera()
    rendered = {'ok': False}

    def render_once() -> None:
        window.GetRenderWindow().Render()
        rendered['ok'] = True

    try:
        window.show()
        window.Initialize()
        QTimer.singleShot(120, render_once)
        QTimer.singleShot(8000, app.quit)
        app.exec()
        if not rendered['ok']:
            raise RuntimeError('Render callback was not reached')
        data['render_pass'] = True
        data['fixture_points'] = int(cloud.GetNumberOfPoints())
        return data
    finally:
        try:
            window.Finalize()
        finally:
            window.close()


def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument('--mode', choices=('import', 'window'), default='import')
    p.add_argument('--out', type=Path)
    opts = p.parse_args()
    result = probe(opts.mode)
    print(json.dumps(result, ensure_ascii=False, indent=2))
    if opts.out:
        opts.out.parent.mkdir(parents=True, exist_ok=True)
        opts.out.write_text(json.dumps(result, indent=2) + '\n', encoding='utf-8')
    return 0


if __name__ == '__main__':
    try:
        raise SystemExit(main())
    except Exception as exc:
        print(f'VTK / PySide6 compatibility probe FAILED: {type(exc).__name__}: {exc}', file=sys.stderr)
        raise SystemExit(1)
