"""08.03 isolated, bounded, read-only PLY → PNG + validated metadata.

Invoked only as a disposable child process; never imported by the desktop Qt UI.
"""
from __future__ import annotations
import argparse
import json
import math
from pathlib import Path

from .ply_header import inspect_ply


def render_ply(input_path: Path, output_path: Path, metadata_path: Path, *,
               width: int = 1000, height: int = 620) -> None:
    # Validate destinations; a malicious PLY cannot choose the output location.
    if (input_path.resolve() in (output_path.resolve(), metadata_path.resolve())
            or output_path.resolve() == metadata_path.resolve()
            or output_path.suffix.lower() != '.png' or metadata_path.suffix.lower() != '.json'
            or not output_path.parent.is_dir() or not metadata_path.parent.is_dir()):
        raise ValueError('Invalid output destinations')
    if not 64 <= width <= 2048 or not 64 <= height <= 2048:
        raise ValueError('Invalid render dimensions')
    header = inspect_ply(input_path)
    from vtkmodules.vtkIOPLY import vtkPLYReader
    from vtkmodules.vtkFiltersGeneral import vtkVertexGlyphFilter
    from vtkmodules.vtkRenderingCore import (
        vtkRenderer, vtkActor, vtkPolyDataMapper, vtkRenderWindow, vtkWindowToImageFilter)
    from vtkmodules.vtkIOImage import vtkPNGWriter
    import vtkmodules.vtkRenderingOpenGL2  # noqa: F401
    import vtkmodules.vtkInteractionStyle  # noqa: F401

    reader = vtkPLYReader()
    errors: list[str] = []
    reader.AddObserver('ErrorEvent', lambda *_: errors.append('VTK PLY reader error'))
    reader.SetFileName(str(input_path))
    reader.Update()
    data = reader.GetOutput()
    if errors or data is None:
        raise ValueError('VTK không đọc được PLY')
    count = data.GetNumberOfPoints()
    if count != header.vertex_count or count < 1:
        raise ValueError('Số điểm VTK khác với header PLY')
    # Do not silently accept nonfinite coordinates or claim metric validity.
    # Bounds must be finite; examining each point also detects isolated NaNs.
    for i in range(count):
        if not all(math.isfinite(float(v)) for v in data.GetPoint(i)):
            raise ValueError('PLY chứa tọa độ NaN/Inf')
    bounds = tuple(float(x) for x in data.GetBounds())
    if len(bounds) != 6 or not all(math.isfinite(v) for v in bounds):
        raise ValueError('PLY bounds không hợp lệ')

    glyph = vtkVertexGlyphFilter()
    glyph.SetInputData(data)
    glyph.Update()
    mapper = vtkPolyDataMapper()
    mapper.SetInputConnection(glyph.GetOutputPort())
    colors = data.GetPointData().GetScalars() if data.GetPointData() else None
    rgb = bool(header.has_rgb and colors is not None and colors.GetNumberOfComponents() >= 3)
    if rgb:
        mapper.SetScalarVisibility(True)
        mapper.SetColorModeToDirectScalars()
    else:
        mapper.ScalarVisibilityOff()
    actor = vtkActor()
    actor.SetMapper(mapper)
    actor.GetProperty().SetPointSize(4 if count > 100_000 else 6)
    if not rgb:
        actor.GetProperty().SetColor(.12, .52, .87)
    renderer = vtkRenderer()
    renderer.SetBackground(.11, .15, .20)
    renderer.AddActor(actor)
    renderer.ResetCamera()
    window = vtkRenderWindow()
    try:
        window.SetOffScreenRendering(1)
        window.SetSize(width, height)
        window.SetMultiSamples(0)
        window.AddRenderer(renderer)
        window.Render()
        screenshot = vtkWindowToImageFilter()
        screenshot.SetInput(window)
        screenshot.ReadFrontBufferOff()
        screenshot.Update()
        writer = vtkPNGWriter()
        writer.SetInputConnection(screenshot.GetOutputPort())
        writer.SetFileName(str(output_path))
        writer.Write()
        if (not output_path.is_file() or output_path.stat().st_size < 128
                or output_path.open('rb').read(8) != b'\x89PNG\r\n\x1a\n'):
            raise RuntimeError('VTK không sinh được ảnh xem trước hợp lệ')
        # Reinspect after rendering, so changed input cannot be shown as original.
        end = input_path.stat()
        if end.st_size != header.source_bytes or end.st_mtime_ns != header.source_mtime_ns:
            raise ValueError('PLY đã thay đổi trong khi render')
        result = {
            'name': input_path.name, 'point_count': count, 'bounds': list(bounds),
            'has_rgb': rgb, 'source_sha256': header.source_sha256,
            'source_bytes': header.source_bytes, 'ply_format': header.ply_format,
            'units': 'unknown', 'coordinate_frame': 'unknown',
        }
        metadata_path.write_text(json.dumps(result, ensure_ascii=False, allow_nan=False), encoding='utf-8')
        print('SCANTOPATH_PLY_PREVIEW_OK', flush=True)
    finally:
        renderer.RemoveActor(actor)
        window.RemoveRenderer(renderer)
        window.Finalize()  # native crash stays in isolated subprocess


def main() -> int:
    ap = argparse.ArgumentParser(description='ScanToPath 08.03 isolated PLY preview')
    ap.add_argument('--input', type=Path, required=True)
    ap.add_argument('--output', type=Path, required=True)
    ap.add_argument('--metadata', type=Path, required=True)
    args = ap.parse_args()
    render_ply(args.input, args.output, args.metadata)
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
