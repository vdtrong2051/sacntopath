"""R4.1 VTK render host: one isolated process, cached point scene, RGB shared frames.

Only this child owns VTK/OpenGL objects. Parent owns shared-memory lifetime.
R4.3 will decide production IPC, synchronization and frame transport.
"""
from __future__ import annotations
import argparse
import os
import math
from multiprocessing import shared_memory
from pathlib import Path
import sys
from typing import Any

from .protocol import MAX_MESSAGE_BYTES, MIN_SIZE, MAX_SIZE, decode_request, encode_response
from ...application.navigation import CameraView
from ..ply_header import inspect_ply
from ..camera_scene import configure_scene


class PersistentScene:
    """Keep VTK scene and camera resident across all camera commands."""

    def __init__(self, width: int, height: int, buffer: shared_memory.SharedMemory):
        self.width, self.height, self.buffer = width, height, buffer
        self.stride = width * height * 3
        self.window = None
        self.renderer = None
        self.actor = None
        self.axes_actor = None
        self.camera = CameraView()
        self.source: Path | None = None
        self.source_sha256: str | None = None
        self.points = 0
        self.scene_revision = 0
        self.frame_revision = 0
        self.open_count = 0
        self._slot = 0
        self.strict_frame_ack = False
        self.pending_frame: tuple[int, int, int] | None = None
        self._glyph = None
        self._reader = None

    def _ensure_renderer(self) -> None:
        if self.window is not None:
            return
        from vtkmodules.vtkRenderingCore import vtkRenderer, vtkRenderWindow
        import vtkmodules.vtkRenderingOpenGL2  # noqa: F401
        import vtkmodules.vtkInteractionStyle  # noqa: F401
        self.renderer = vtkRenderer()
        self.renderer.SetBackground(.11, .15, .20)
        self.window = vtkRenderWindow()
        self.window.SetOffScreenRendering(1)
        self.window.SetMultiSamples(0)
        self.window.SetSize(self.width, self.height)
        self.window.AddRenderer(self.renderer)

    def close_scene(self) -> None:
        """Detach geometry without terminating the resident VTK process."""
        if self.renderer is not None:
            if self.axes_actor is not None:
                self.renderer.RemoveActor(self.axes_actor)
            if self.actor is not None:
                self.renderer.RemoveActor(self.actor)
        self.axes_actor = self.actor = self._glyph = self._reader = None
        self.source = None
        self.source_sha256 = None
        self.points = 0
        self.camera = CameraView()
        self.pending_frame = None
        self.scene_revision += 1

    def open(self, path: str) -> dict[str, Any]:
        """Validate/hash PLY once, then cache geometry for camera interactions."""
        self.close_scene()
        source = Path(path)
        if source.is_symlink() or not source.is_absolute():
            raise ValueError('SOURCE_PATH_REJECTED')
        hdr = inspect_ply(source)
        from vtkmodules.vtkIOPLY import vtkPLYReader
        from vtkmodules.vtkFiltersGeneral import vtkVertexGlyphFilter
        from vtkmodules.vtkRenderingCore import vtkActor, vtkPolyDataMapper
        reader = vtkPLYReader()
        errors: list[str] = []
        reader.AddObserver('ErrorEvent', lambda *_: errors.append('reader'))
        reader.SetFileName(str(source))
        reader.Update()
        data = reader.GetOutput()
        if errors or data is None or data.GetNumberOfPoints() != hdr.vertex_count:
            raise ValueError('INVALID_PLY_DATA')
        if data.GetNumberOfPolys() or data.GetNumberOfStrips():
            raise ValueError('MESH_DEFERRED_R5_1')
        for i in range(hdr.vertex_count):
            if not all(math.isfinite(float(v)) for v in data.GetPoint(i)):
                raise ValueError('NONFINITE_PLY')
        if not all(math.isfinite(float(v)) for v in data.GetBounds()):
            raise ValueError('INVALID_BOUNDS')
        after = source.stat()
        if after.st_size != hdr.source_bytes or after.st_mtime_ns != hdr.source_mtime_ns:
            raise ValueError('SOURCE_CHANGED_DURING_LOAD')
        self._ensure_renderer()
        glyph = vtkVertexGlyphFilter()
        glyph.SetInputData(data)
        glyph.Update()
        mapper = vtkPolyDataMapper()
        mapper.SetInputConnection(glyph.GetOutputPort())
        colors = data.GetPointData().GetScalars() if data.GetPointData() else None
        has_rgb = bool(hdr.has_rgb and colors is not None and colors.GetNumberOfComponents() >= 3)
        if has_rgb:
            mapper.SetScalarVisibility(True)
            mapper.SetColorModeToDirectScalars()
        else:
            mapper.ScalarVisibilityOff()
        actor = vtkActor()
        actor.SetMapper(mapper)
        actor.GetProperty().SetPointSize(4 if hdr.vertex_count > 100_000 else 6)
        if not has_rgb:
            actor.GetProperty().SetColor(.12, .52, .87)
        self.renderer.AddActor(actor)
        self._reader, self._glyph, self.actor = reader, glyph, actor
        self.source, self.source_sha256, self.points = source, hdr.source_sha256, hdr.vertex_count
        self.open_count += 1
        self.camera = CameraView()
        self._configure_camera()
        frame = self.render()
        return {**frame, 'source_sha256': self.source_sha256, 'point_count': self.points,
                'units': 'unknown', 'coordinate_frame': 'unknown', 'has_rgb': has_rgb,
                'geometry_kind': 'points'}

    def _configure_camera(self) -> None:
        if self.axes_actor is not None:
            self.renderer.RemoveActor(self.axes_actor)
            self.axes_actor = None
        self.axes_actor = configure_scene(self.renderer, self.camera)

    def ack_frame(self, scene_revision: int, frame_revision: int, slot: int) -> dict[str, Any]:
        """Release the producer slot only after the consumer has copied its RGB bytes."""
        if not self.strict_frame_ack or self.pending_frame != (scene_revision, frame_revision, slot):
            raise ValueError('STALE_FRAME_ACK')
        self.pending_frame = None
        return {'acked_frame_revision': frame_revision, 'scene_revision': self.scene_revision}

    def set_camera(self, state: str) -> dict[str, Any]:
        """Render an absolute camera intent; latest-wins scheduling preserves final pose."""
        if self.actor is None:
            raise ValueError('NO_SCENE')
        if self.strict_frame_ack and self.pending_frame is not None:
            raise ValueError('FRAME_NOT_ACKED')
        self.camera = CameraView.from_json(state)
        self._configure_camera()
        return self.render()

    def render(self) -> dict[str, Any]:
        """Render cached scene and publish raw RGB after the entire frame is ready."""
        if self.strict_frame_ack and self.pending_frame is not None:
            raise ValueError('FRAME_NOT_ACKED')
        from vtkmodules.vtkRenderingCore import vtkWindowToImageFilter
        from vtkmodules.util.numpy_support import vtk_to_numpy
        self.window.Render()
        image_filter = vtkWindowToImageFilter()
        image_filter.SetInput(self.window)
        image_filter.SetInputBufferTypeToRGB()
        image_filter.ReadFrontBufferOff()
        image_filter.Update()
        image = image_filter.GetOutput()
        scalars = image.GetPointData().GetScalars()
        rgb = vtk_to_numpy(scalars).tobytes()
        if len(rgb) != self.stride:
            raise RuntimeError('FRAME_SIZE_MISMATCH')
        slot = self._slot
        offset = slot * self.stride
        self.buffer.buf[offset:offset + self.stride] = rgb
        self._slot = 1 - slot
        self.frame_revision += 1
        if self.strict_frame_ack:
            self.pending_frame = (self.scene_revision, self.frame_revision, slot)
        return {'frame_revision': self.frame_revision, 'scene_revision': self.scene_revision,
                'slot': slot, 'width': self.width, 'height': self.height,
                'byte_count': self.stride, 'point_count': self.points,
                'open_count': self.open_count}

    def update_camera(self, action: str, dx: float, dy: float) -> dict[str, Any]:
        if self.actor is None:
            raise ValueError('NO_SCENE')
        if self.strict_frame_ack and self.pending_frame is not None:
            raise ValueError('FRAME_NOT_ACKED')
        self.camera = self.camera.update(action, dx, dy)
        self._configure_camera()
        return self.render()

    def status(self) -> dict[str, Any]:
        return {'scene_revision': self.scene_revision, 'frame_revision': self.frame_revision,
                'point_count': self.points, 'open_count': self.open_count,
                'active_scene': self.source is not None}

    def dispose(self) -> None:
        self.close_scene()
        if self.window is not None:
            self.window.RemoveRenderer(self.renderer)
            self.window.Finalize()
        self.window = self.renderer = None


def run_host(width: int, height: int, shm_name: str) -> int:
    """Serve bounded newline-delimited requests; never import Qt or touch SQLite."""
    if not MIN_SIZE <= width <= MAX_SIZE or not MIN_SIZE <= height <= MAX_SIZE:
        raise ValueError('INVALID_DIMENSIONS')
    options = {'track': False} if sys.version_info >= (3, 13) and os.name != 'nt' else {}
    shm = shared_memory.SharedMemory(name=shm_name, create=False, **options)
    if shm.size < width * height * 3 * 2:
        shm.close()
        raise ValueError('BUFFER_TOO_SMALL')
    scene = PersistentScene(width, height, shm)
    previous_id = 0
    try:
        while True:
            line = sys.stdin.buffer.readline(MAX_MESSAGE_BYTES + 1)
            if not line:
                break
            response: dict[str, Any] = {}
            done = False
            try:
                request = decode_request(line)
                rid = request['id']
                if rid <= previous_id:
                    raise ValueError('NON_MONOTONIC_ID')
                previous_id = rid
                op = request['op']
                if op == 'hello' and request.get('frame_mode') == 'ack':
                    if scene.actor is not None or scene.pending_frame is not None:
                        raise ValueError('ACK_NEGOTIATION_REQUIRES_EMPTY_SCENE')
                    scene.strict_frame_ack = True
                if op == 'open':
                    data = scene.open(request['path'])
                elif op == 'camera':
                    data = scene.update_camera(request['action'], request['dx'], request['dy'])
                elif op == 'set_camera':
                    data = scene.set_camera(request['state'])
                elif op == 'ack_frame':
                    data = scene.ack_frame(request['scene_revision'], request['frame_revision'], request['slot'])
                elif op == 'close_scene':
                    scene.close_scene()
                    data = scene.status()
                elif op == 'status':
                    data = scene.status()
                elif op == 'hello':
                    data = {**scene.status(), 'width': width, 'height': height, 'transport': 'rgb24-shm-2slot',
                            'frame_mode': 'ack' if scene.strict_frame_ack else 'legacy'}
                else:
                    data = scene.status()
                    done = True
                response = {'id': rid, 'ok': True, **data}
            except (ValueError, TypeError, OSError) as exc:
                response = {'id': response.get('id', previous_id), 'ok': False,
                            'error': str(exc)[:160]}
            sys.stdout.buffer.write(encode_response(response))
            sys.stdout.buffer.flush()
            if done:
                break
    finally:
        scene.dispose()
        shm.close()
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description='ScanToPath R4.1 isolated resident VTK PoC')
    parser.add_argument('--width', required=True, type=int)
    parser.add_argument('--height', required=True, type=int)
    parser.add_argument('--shm-name', required=True)
    args = parser.parse_args()
    return run_host(args.width, args.height, args.shm_name)


if __name__ == '__main__':
    raise SystemExit(main())
