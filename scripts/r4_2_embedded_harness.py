"""R4.2 standalone Qt/VTK script outside production feature layers.

Running this may terminate the entire child due to native GL/Qt/VTK faults.
The parent comparator launches it as a disposable subprocess by design.
"""
from __future__ import annotations
import argparse
import os
from pathlib import Path
import platform
import sys
import time

from scantopath.modules.viewer3d.infrastructure.embedded_poc.contracts import ComparatorRequest, write_report


def _build_scene(renderer, source: Path | None):
    """Create a drawable VTK actor without changing user-owned geometry."""
    from vtkmodules.vtkRenderingCore import vtkActor, vtkPolyDataMapper
    if source is None:
        from vtkmodules.vtkFiltersSources import vtkSphereSource
        sphere = vtkSphereSource()
        sphere.SetThetaResolution(30)
        sphere.SetPhiResolution(24)
        sphere.Update()
        poly = sphere.GetOutput()
    else:
        from scantopath.modules.viewer3d.infrastructure.ply_header import inspect_ply
        from vtkmodules.vtkIOPLY import vtkPLYReader
        from vtkmodules.vtkFiltersGeneral import vtkVertexGlyphFilter
        preflight = inspect_ply(source)
        reader = vtkPLYReader()
        errors = []
        reader.AddObserver('ErrorEvent', lambda *_: errors.append('VTK reader error'))
        reader.SetFileName(str(source))
        reader.Update()
        poly = reader.GetOutput()
        if errors or poly is None or poly.GetNumberOfPoints() != preflight.vertex_count:
            raise ValueError('VTK PLY reader data mismatch')
        # R4.2 compares Qt/VTK lifecycle, not R5 geometry/mesh completeness.
        if poly.GetNumberOfPolys() == 0:
            glyph = vtkVertexGlyphFilter()
            glyph.SetInputData(poly)
            glyph.Update()
            poly = glyph.GetOutput()
    mapper = vtkPolyDataMapper()
    mapper.SetInputData(poly)
    actor = vtkActor()
    actor.SetMapper(mapper)
    if poly.GetNumberOfPolys() == 0:
        actor.GetProperty().SetPointSize(5)
    renderer.AddActor(actor)
    renderer.ResetCamera()
    return actor, mapper, poly


def _drag(qapp, widget, steps: int) -> bool:
    """Feed real Qt mouse events into QVTK, compare the native camera pose."""
    from PySide6.QtCore import QPointF, QEvent, Qt, QCoreApplication
    from PySide6.QtGui import QMouseEvent
    from vtkmodules.vtkRenderingCore import vtkRenderer
    camera = widget.GetRenderWindow().GetRenderers().GetFirstRenderer().GetActiveCamera()
    before = tuple(camera.GetPosition())
    def send(kind, pos, button, buttons):
        point = QPointF(float(pos[0]), float(pos[1]))
        event = QMouseEvent(kind, point, button, buttons, Qt.NoModifier)
        QCoreApplication.sendEvent(widget, event)
        qapp.processEvents()
    start = (max(40, widget.width() // 3), max(40, widget.height() // 3))
    send(QEvent.MouseButtonPress, start, Qt.LeftButton, Qt.LeftButton)
    for i in range(steps):
        send(QEvent.MouseMove, (start[0] + 3 * (i + 1), start[1] + 2 * (i + 1)), Qt.NoButton, Qt.LeftButton)
    send(QEvent.MouseButtonRelease, (start[0] + 3 * steps, start[1] + 2 * steps), Qt.LeftButton, Qt.NoButton)
    after = tuple(camera.GetPosition())
    return any(abs(a - b) > 1e-8 for a, b in zip(before, after))


def run(request: ComparatorRequest, report_path: Path, *, require_native: bool = True) -> int:
    """Own QApplication and the VTK render window in this child process only."""
    from PySide6.QtCore import Qt, QTimer
    from PySide6.QtWidgets import QApplication, QVBoxLayout, QWidget, QLabel
    import PySide6
    import vtkmodules.qt
    vtkmodules.qt.PyQtImpl = 'PySide6'
    vtkmodules.qt.QVTKRWIBase = 'QWidget'
    from vtkmodules.qt.QVTKRenderWindowInteractor import QVTKRenderWindowInteractor
    from vtkmodules.vtkRenderingCore import vtkRenderer
    from vtkmodules.vtkInteractionStyle import vtkInteractorStyleTrackballCamera
    import vtkmodules.vtkRenderingOpenGL2  # noqa: F401
    import vtkmodules.vtkInteractionStyle  # noqa: F401
    from vtkmodules.vtkCommonCore import vtkVersion
    from scantopath.modules.viewer3d.infrastructure.ply_header import inspect_ply

    if request.source is not None:
        preflight = inspect_ply(request.source)
        source_sha = preflight.source_sha256
        source_stat = (preflight.source_bytes, preflight.source_mtime_ns)
    else:
        source_sha, source_stat = None, None
    app = QApplication.instance() or QApplication([])
    qt_platform = app.platformName().lower()
    if require_native and qt_platform in ('offscreen', 'minimal'):
        raise RuntimeError('R4.2 Windows native HMI requires a real Qt display platform')
    started = time.perf_counter()
    confirmed = True
    records = []
    total_renders = 0
    loop_count = request.cycles if request.scenario != 'manual' else 1

    for idx in range(loop_count):
        panel = QWidget()
        panel.setWindowTitle('R4.2 Qt-VTK isolated comparator - NOT ScanToPath production')
        panel.resize(740, 500)
        layout = QVBoxLayout(panel)
        status = QLabel('R4.2 standalone Qt/VTK comparator')
        layout.addWidget(status)
        vtk_widget = QVTKRenderWindowInteractor(panel)
        vtk_widget.setMinimumSize(550, 360)
        layout.addWidget(vtk_widget, 1)
        renderer = vtkRenderer()
        renderer.SetBackground(.11, .15, .20)
        rw = vtk_widget.GetRenderWindow()
        rw.AddRenderer(renderer)
        iren = rw.GetInteractor()
        iren.SetInteractorStyle(vtkInteractorStyleTrackballCamera())
        actor = mapper = poly = None
        try:
            actor, mapper, poly = _build_scene(renderer, request.source)
            panel.show()
            app.processEvents()
            iren.Initialize()
            rw.Render()
            total_renders += 1
            if request.scenario == 'manual':
                status.setText('Drag left to orbit, middle/right to pan, scroll to zoom. Close this window to finish.')
                before_manual = tuple(renderer.GetActiveCamera().GetPosition())
                app.exec()
                after_manual = tuple(renderer.GetActiveCamera().GetPosition())
                confirmed = any(abs(a - b) > 1e-8 for a, b in zip(before_manual, after_manual))
            else:
                moved = _drag(app, vtk_widget, request.events_per_cycle)
                confirmed = confirmed and moved
                rw.Render()
                total_renders += 1
                if idx in (0, loop_count - 1):
                    records.append({'cycle': idx + 1, 'native_drag_changed_camera': moved,
                                    'position': [float(x) for x in renderer.GetActiveCamera().GetPosition()]})
            if source_stat is not None:
                stat = request.source.stat()
                if (stat.st_size, stat.st_mtime_ns) != source_stat:
                    raise ValueError('source changed while Qt/VTK comparator was running')
        finally:
            try:
                if actor is not None:
                    renderer.RemoveActor(actor)
                rw.RemoveRenderer(renderer)
                vtk_widget.close()  # QVTK.closeEvent finalizes its own native window
                panel.close()
                vtk_widget.deleteLater()
                panel.deleteLater()
                app.processEvents()
            except Exception:
                # A C++ crash here is precisely why R4.2 is a separate process.
                raise
    if source_sha is not None:
        from scantopath.modules.viewer3d.infrastructure.embedded_poc.contracts import file_sha256
        if file_sha256(request.source) != source_sha:
            raise ValueError('PLY SHA-256 changed during comparator')
    write_report(report_path, {
        'schema': 'r4.2-comparator-v1', 'scenario': request.scenario,
        'widget': 'QVTKRenderWindowInteractor',
        'pid': os.getpid(), 'cycles_completed': loop_count, 'renders': total_renders,
        'events_per_cycle': request.events_per_cycle,
        'drag_confirmed': bool(confirmed), 'qt_platform': qt_platform,
        'qt_version': PySide6.__version__, 'vtk_version': vtkVersion.GetVTKVersion(),
        'python': sys.version.split()[0], 'os': platform.platform(),
        'source_sha256': source_sha, 'source_kind': 'synthetic_sphere' if request.source is None else 'ply',
        'elapsed_seconds': round(max(1e-9, time.perf_counter() - started), 6),
        'samples': records,
        'note': 'Standalone child only. Does not certify an embedded production application or native crash recovery.'
    })
    return 0 if confirmed else 4


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument('--scenario', choices=sorted({'smoke', 'stress', 'manual', 'process_exit_probe'}), default='smoke')
    parser.add_argument('--cycles', type=int, default=1)
    parser.add_argument('--events', type=int, default=12)
    parser.add_argument('--source', type=Path)
    parser.add_argument('--report', type=Path, required=True)
    parser.add_argument('--allow-offscreen', action='store_true', help='development only; cannot certify Windows HMI')
    args = parser.parse_args(argv)
    request = ComparatorRequest(args.scenario, args.cycles, args.events, args.source)
    if args.scenario == 'process_exit_probe':
        # Controlled process exit, NOT a simulated native VTK segmentation fault.
        os._exit(86)
    return run(request, args.report, require_native=not args.allow_offscreen)


if __name__ == '__main__':
    try:
        sys.exit(main())
    except Exception as error:
        print('R4.2 comparator failed: ' + repr(error), file=sys.stderr, flush=True)
        sys.exit(3)
