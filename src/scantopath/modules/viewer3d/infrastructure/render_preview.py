"""08.02 crash repair: render five synthetic points in an isolated Python process.

This is not a PLY reader or a measured cloud. No Qt import or interaction with
SQLite, RAW, Gemini 2 or ScanToPath UI; GPU/VTK crashes affect this child only.
"""
from __future__ import annotations

import argparse
from pathlib import Path


def render_fixture_png(destination: Path, *, width: int = 1000, height: int = 620) -> None:
    """Render via VTK OpenGL offscreen in the current (child) process."""
    from vtkmodules.vtkRenderingCore import vtkRenderWindow, vtkWindowToImageFilter
    from vtkmodules.vtkIOImage import vtkPNGWriter
    from .fixture_scene import VtkFixtureScene

    if not 64 <= width <= 4096 or not 64 <= height <= 4096:
        raise ValueError('Invalid preview size')
    if destination.suffix.lower() != '.png' or not destination.parent.is_dir():
        raise ValueError('Output must be PNG in an existing directory')
    scene = VtkFixtureScene()
    window = vtkRenderWindow()
    try:
        window.SetOffScreenRendering(1)
        window.SetSize(width, height)
        window.SetMultiSamples(0)
        window.AddRenderer(scene.renderer)
        window.Render()
        capture = vtkWindowToImageFilter()
        capture.SetInput(window)
        capture.ReadFrontBufferOff()
        capture.Update()
        writer = vtkPNGWriter()
        writer.SetInputConnection(capture.GetOutputPort())
        writer.SetFileName(str(destination))
        writer.Write()
        if not destination.is_file() or destination.stat().st_size < 512:
            raise RuntimeError('VTK returned no usable PNG image')
        if destination.open('rb').read(8) != b'\x89PNG\r\n\x1a\n':
            raise RuntimeError('VTK preview output is not PNG')
        print('SCANTOPATH_VTK_PREVIEW_OK points=5 format=PNG', flush=True)
    finally:
        scene.dispose()
        window.RemoveRenderer(scene.renderer)
        # Finalize is contained inside a disposable subprocess. A native driver
        # crash/hang cannot corrupt or terminate the Qt application process.
        window.Finalize()


def main() -> int:
    parser = argparse.ArgumentParser(description='08.02 VTK isolated fixture preview')
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    render_fixture_png(args.output)
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
