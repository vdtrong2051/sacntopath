"""One disposable native process for an R4.4 A/B interaction measurement.

A: standalone Qt QVTK widget. B: isolated resident VTK host and async client.
No production Viewer is modified or imported.
"""
from __future__ import annotations

import argparse
import os
from pathlib import Path
import sys
import time

from r4_4_common import (SCHEMA, environment, rss_bytes, process_cpu_seconds, sha256_file,
                         summarise_timings, write_json)

WIDTH, HEIGHT = 640, 480


def _resident(path: Path, samples: int):
    from scantopath.modules.viewer3d.infrastructure.resident_poc.async_session import CoalescingRenderSession
    started = time.perf_counter()
    s = CoalescingRenderSession(WIDTH, HEIGHT, timeout=90)
    peaks = []
    timings = []
    fresh = 0
    try:
        s.start().result(timeout=30)
        s.open_ply(path).result(timeout=150)
        first = s.next_frame(timeout=30)
        last_rev = first.frame_revision
        pid = s.pid
        if pid is None:
            raise RuntimeError('NO_RESIDENT_PID')
        cold = time.perf_counter() - started
        start_cpu = process_cpu_seconds(pid)
        peaks.append(rss_bytes(pid))
        warm_start = time.perf_counter()
        for i in range(samples):
            t0 = time.perf_counter_ns()
            wanted = s.camera('orbit', 2.0, 0.75 if i % 2 else -0.75)
            frame = s.next_frame(timeout=90)
            elapsed = (time.perf_counter_ns() - t0) / 1_000_000.0
            if (frame.frame_revision <= last_rev or frame.input_revision != wanted
                    or frame.host_pid != pid):
                raise RuntimeError('STALE_OR_MISMATCHED_FRAME')
            if len(frame.rgb) != WIDTH * HEIGHT * 3:
                raise RuntimeError('INVALID_RGB_BYTES')
            last_rev = frame.frame_revision
            timings.append(max(elapsed, 0.000001))
            fresh += 1
            peaks.append(rss_bytes(pid))
        elapsed_seconds = max(time.perf_counter() - warm_start, 0.000001)
        stats = s.statistics
        end_cpu = process_cpu_seconds(pid)
        if stats['frames_dropped'] != 0:
            raise RuntimeError('DROPPED_FRAMES_IN_SEQUENTIAL_WORKLOAD')
        # Because camera commands are synchronous in this workload, one frame per input.
        return dict(host_pid=pid, cold_seconds=cold, latency_ms=timings,
                    fresh_frames=fresh, elapsed_seconds=elapsed_seconds,
                    peak_renderer_rss_bytes=max((p for p in peaks if p is not None), default=None),
                    renderer_cpu_seconds=(round(end_cpu - start_cpu, 4) if end_cpu is not None and start_cpu is not None else None),
                    open_count=1, frame_revision=last_rev,
                    input_revision=stats['input_revision'],
                    frames_dropped=stats['frames_dropped'],
                    notes='B input-to-immutable-ACKed-frame. Worker/host IPC and RGB copy included.')
    finally:
        s.stop(timeout=5)


def _embedded(path: Path, samples: int):
    import vtkmodules.qt
    vtkmodules.qt.PyQtImpl = 'PySide6'
    vtkmodules.qt.QVTKRWIBase = 'QWidget'
    from PySide6.QtWidgets import QApplication, QWidget, QVBoxLayout
    from PySide6.QtCore import Qt, QEvent, QPointF, QCoreApplication
    from PySide6.QtGui import QMouseEvent
    from vtkmodules.qt.QVTKRenderWindowInteractor import QVTKRenderWindowInteractor
    from vtkmodules.vtkRenderingCore import vtkRenderer, vtkActor, vtkPolyDataMapper
    from vtkmodules.vtkIOPLY import vtkPLYReader
    from vtkmodules.vtkFiltersGeneral import vtkVertexGlyphFilter
    from vtkmodules.vtkInteractionStyle import vtkInteractorStyleTrackballCamera
    import vtkmodules.vtkRenderingOpenGL2  # noqa: F401
    import vtkmodules.vtkInteractionStyle  # noqa: F401
    from scantopath.modules.viewer3d.infrastructure.ply_header import inspect_ply

    started = time.perf_counter()
    app = QApplication.instance() or QApplication([])
    if app.platformName().lower() in ('offscreen', 'minimal'):
        raise RuntimeError('NATIVE_QT_PLATFORM_REQUIRED')
    hdr = inspect_ply(path)
    panel = QWidget()
    panel.setWindowTitle('ScanToPath R4.4 A/B benchmark - experimental only')
    panel.resize(660, 525)
    layout = QVBoxLayout(panel)
    widget = QVTKRenderWindowInteractor(panel)
    widget.setMinimumSize(WIDTH, HEIGHT)
    layout.setContentsMargins(0, 0, 0, 0)
    layout.addWidget(widget)
    renderer = vtkRenderer()
    renderer.SetBackground(.11, .15, .20)
    rw = widget.GetRenderWindow()
    rw.AddRenderer(renderer)
    interactor = rw.GetInteractor()
    interactor.SetInteractorStyle(vtkInteractorStyleTrackballCamera())
    reader = vtkPLYReader()
    errors = []
    reader.AddObserver('ErrorEvent', lambda *_: errors.append('VTK_READER_FAILED'))
    reader.SetFileName(str(path))
    reader.Update()
    data = reader.GetOutput()
    if errors or data is None or data.GetNumberOfPoints() != hdr.vertex_count:
        raise RuntimeError('VTK_PLY_MISMATCH')
    if data.GetNumberOfPolys():
        raise RuntimeError('POINT_BENCHMARK_REQUIRES_NO_FACES')
    glyph = vtkVertexGlyphFilter()
    glyph.SetInputData(data)
    glyph.Update()
    mapper = vtkPolyDataMapper()
    mapper.SetInputConnection(glyph.GetOutputPort())
    actor = vtkActor()
    actor.SetMapper(mapper)
    actor.GetProperty().SetPointSize(4 if hdr.vertex_count > 100000 else 6)
    renderer.AddActor(actor)
    renderer.ResetCamera()
    timings = []
    fresh = 0
    peaks = []
    try:
        panel.show()
        app.processEvents()
        interactor.Initialize()
        rw.Render()
        cold = time.perf_counter() - started
        start_cpu = time.process_time()
        peaks.append(rss_bytes(os.getpid()))
        before = tuple(renderer.GetActiveCamera().GetPosition())
        pos_x, pos_y = 150, 160
        def send(t, x, y, button, buttons):
            point = QPointF(float(x), float(y))
            event = QMouseEvent(t, point, button, buttons, Qt.NoModifier)
            QCoreApplication.sendEvent(widget, event)
            app.processEvents()
        send(QEvent.MouseButtonPress, pos_x, pos_y, Qt.LeftButton, Qt.LeftButton)
        warm_start = time.perf_counter()
        for i in range(samples):
            t0 = time.perf_counter_ns()
            pos_x += 2
            pos_y += 1 if i % 2 else -1
            send(QEvent.MouseMove, pos_x, pos_y, Qt.NoButton, Qt.LeftButton)
            # Completion of Render() is observable, display presentation is NOT.
            rw.Render()
            elapsed = (time.perf_counter_ns() - t0) / 1_000_000.0
            timings.append(max(elapsed, 0.000001))
            fresh += 1
            peaks.append(rss_bytes(os.getpid()))
        elapsed_seconds = max(time.perf_counter() - warm_start, 0.000001)
        cpu_seconds = time.process_time() - start_cpu
        send(QEvent.MouseButtonRelease, pos_x, pos_y, Qt.LeftButton, Qt.NoButton)
        after = tuple(renderer.GetActiveCamera().GetPosition())
        if not any(abs(x - y) > 1e-8 for x, y in zip(before, after)):
            raise RuntimeError('NATIVE_CAMERA_DID_NOT_MOVE')
        return dict(host_pid=os.getpid(), cold_seconds=cold, latency_ms=timings,
                    fresh_frames=fresh, elapsed_seconds=elapsed_seconds,
                    peak_renderer_rss_bytes=max((p for p in peaks if p is not None), default=None),
                    renderer_cpu_seconds=round(cpu_seconds, 4),
                    open_count=1, frame_revision=fresh,
                    input_revision=samples, frames_dropped=0,
                    qt_platform=app.platformName(),
                    notes='A Qt mouseMoveEvent -> VTK Render() completion. No display vsync/presentation guarantee.')
    finally:
        try:
            renderer.RemoveActor(actor)
            rw.RemoveRenderer(renderer)
            widget.close()
            panel.close()
            widget.deleteLater()
            panel.deleteLater()
            app.processEvents()
        except Exception:
            raise


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument('--mode', choices=('resident', 'embedded'), required=True)
    parser.add_argument('--input', type=Path, required=True)
    parser.add_argument('--samples', type=int, required=True)
    parser.add_argument('--report', type=Path, required=True)
    args = parser.parse_args()
    if not 10 <= args.samples <= 300 or not args.input.is_absolute() or args.input.is_symlink():
        raise ValueError('UNSAFE_WORKLOAD')
    if args.report.is_symlink() or args.report.resolve() == args.input.resolve():
        raise ValueError('UNSAFE_REPORT')
    from scantopath.modules.viewer3d.infrastructure.ply_header import inspect_ply
    header = inspect_ply(args.input)
    before = header.source_sha256
    if args.mode == 'resident':
        measure = _resident(args.input, args.samples)
    else:
        measure = _embedded(args.input, args.samples)
    after = sha256_file(args.input)
    if before != after:
        raise RuntimeError('SOURCE_CHANGED')
    stats = summarise_timings(measure['latency_ms'], measure['elapsed_seconds'])
    report = {**environment(), **measure, **stats,
              'schema': SCHEMA, 'mode': args.mode, 'point_count': header.vertex_count,
              'sample_count': args.samples, 'source_sha256': before,
              'source_sha256_after': after, 'viewport': [WIDTH, HEIGHT],
              'measurement_type': 'input_to_render_completed_not_presented',
              'worker_rss_at_report_bytes': rss_bytes(os.getpid()),
              'measured_at_utc': __import__('datetime').datetime.now(__import__('datetime').timezone.utc).isoformat(),
              'vtk_version': __import__('vtkmodules.vtkCommonCore', fromlist=['vtkVersion']).vtkVersion.GetVTKVersion()}
    if args.mode == 'embedded':
        import PySide6
        report['qt_version'] = PySide6.__version__
    write_json(args.report, report)
    print(f'R4.4 {args.mode} measured: points={header.vertex_count} '
          f'p95_ms={stats["p95_ms"]} rate_hz={stats["fresh_frame_rate_hz"]}', flush=True)
    return 0


if __name__ == '__main__':
    try:
        sys.exit(main())
    except Exception as exc:
        print('R4.4 worker failed: ' + repr(exc), file=sys.stderr, flush=True)
        sys.exit(2)
