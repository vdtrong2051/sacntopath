"""08.05 isolated VTK picker. Input PLY is read-only; GUI never imports VTK.

Pick works in the same 1000x620 camera projection as the preview renderer.
The actor is restricted to point-cloud vertices; reference XYZ axes cannot be picked.
"""
from __future__ import annotations
import argparse
import json
import math
from pathlib import Path
from ..application.navigation import CameraView
from ..application.picking import PickResult
from .camera_scene import configure_scene
from .ply_header import inspect_ply

WIDTH,HEIGHT=1000,620


def pick_point(kind: str, state: CameraView, u: float, v: float,
               result_path: Path, source: Path | None=None,
               expected_sha256: str | None=None) -> PickResult:
    if kind not in ('fixture','ply') or not isinstance(state,CameraView):
        raise ValueError('Invalid pick scene')
    if any(type(n) not in (float,int) or not math.isfinite(n) or not 0<=n<=1 for n in (u,v)):
        raise ValueError('Invalid pick coordinate')
    if result_path.suffix.lower() != '.json' or not result_path.parent.is_dir():
        raise ValueError('Invalid pick destination')
    if kind=='fixture' and (source is not None or expected_sha256 is not None):
        raise ValueError('Fixture pick must not use file source')
    if kind=='ply' and (source is None or not isinstance(expected_sha256,str)
                        or len(expected_sha256)!=64):
        raise ValueError('Missing PLY fingerprint')
    # Native modules are imported ONLY inside the child process.
    from vtkmodules.vtkRenderingCore import vtkPointPicker, vtkRenderWindow
    import vtkmodules.vtkRenderingOpenGL2  # noqa: F401
    import vtkmodules.vtkInteractionStyle  # noqa: F401
    from vtkmodules.vtkFiltersGeneral import vtkVertexGlyphFilter
    from vtkmodules.vtkIOPLY import vtkPLYReader
    from vtkmodules.vtkRenderingCore import vtkActor, vtkPolyDataMapper, vtkRenderer

    header=None; scene=None; actor=None; data=None
    if kind=='fixture':
        from .fixture_scene import VtkFixtureScene
        scene=VtkFixtureScene()
        renderer=scene.renderer
        actor=scene._actor
        data=scene._polydata
        source_id='fixture:08.02'
    else:
        header=inspect_ply(source)
        if header.source_sha256 != expected_sha256:
            raise ValueError('PLY changed since it was displayed')
        reader=vtkPLYReader();errors=[]
        reader.AddObserver('ErrorEvent',lambda *_: errors.append(True))
        reader.SetFileName(str(source));reader.Update()
        data=reader.GetOutput()
        if errors or data is None or data.GetNumberOfPoints()!=header.vertex_count:
            raise ValueError('PLY failed to load for picking')
        glyph=vtkVertexGlyphFilter();glyph.SetInputData(data);glyph.Update()
        mapper=vtkPolyDataMapper();mapper.SetInputConnection(glyph.GetOutputPort())
        actor=vtkActor();actor.SetMapper(mapper)
        actor.GetProperty().SetPointSize(4 if header.vertex_count>100000 else 6)
        renderer=vtkRenderer();renderer.AddActor(actor);renderer.ResetCamera()
        source_id=expected_sha256

    axes_actor=configure_scene(renderer,state)
    window=vtkRenderWindow()
    try:
        window.SetOffScreenRendering(1)
        window.SetSize(WIDTH,HEIGHT)
        window.SetMultiSamples(0)
        window.AddRenderer(renderer)
        window.Render()
        picker=vtkPointPicker()
        picker.SetTolerance(.015)
        picker.PickFromListOn()
        picker.AddPickList(actor)
        x=float(u)*(WIDTH-1);y=float(v)*(HEIGHT-1)
        picker.Pick(x,y,0,renderer)
        idx=int(picker.GetPointId())
        if idx<0 or idx>=data.GetNumberOfPoints():
            picked=PickResult(False,None,None,None,None,source_id)
        else:
            xyz=tuple(float(c) for c in data.GetPoint(idx))
            if not all(math.isfinite(c) for c in xyz):
                raise ValueError('PLY point is not finite')
            renderer.SetWorldPoint(*xyz,1.0)
            renderer.WorldToDisplay()
            display=renderer.GetDisplayPoint()
            # vtkPointPicker tolerance can cover a huge region in dense data;
            # bound the pick to 12 PNG pixels around the actual chosen point.
            if (not all(math.isfinite(c) for c in display[:2])
                    or math.hypot(display[0]-x,display[1]-y)>12):
                picked=PickResult(False,None,None,None,None,source_id)
            else:
                rgb=None
                if kind=='ply' and header.has_rgb:
                    scalars=data.GetPointData().GetScalars() if data.GetPointData() else None
                    if scalars is not None and scalars.GetNumberOfComponents()>=3:
                        values=scalars.GetTuple(idx)[:3]
                        if all(math.isfinite(c) and 0<=c<=255 for c in values):
                            rgb=tuple(int(round(c)) for c in values)
                dx=max(0.,min(1.,float(display[0])/(WIDTH-1)))
                dy=max(0.,min(1.,float(display[1])/(HEIGHT-1)))
                picked=PickResult(True,idx,xyz,rgb,(dx,dy),source_id)
        if kind=='ply' and inspect_ply(source).source_sha256!=expected_sha256:
            raise ValueError('PLY changed during point picking')
        # Serialize only checked DTO fields; neither 3D data nor absolute paths leak to GUI.
        from dataclasses import asdict
        result_path.write_text(json.dumps(asdict(picked),allow_nan=False,separators=(',',':')),
                               encoding='utf-8')
        return picked
    finally:
        if axes_actor is not None:
            renderer.RemoveActor(axes_actor)
        if scene is not None:
            scene.dispose()
        else:
            renderer.RemoveActor(actor)
        window.RemoveRenderer(renderer)
        window.Finalize()


def main() -> int:
    ap=argparse.ArgumentParser()
    ap.add_argument('--kind',required=True,choices=('fixture','ply'))
    ap.add_argument('--state',required=True)
    ap.add_argument('--u',required=True,type=float)
    ap.add_argument('--v',required=True,type=float)
    ap.add_argument('--output',required=True,type=Path)
    ap.add_argument('--input',type=Path)
    ap.add_argument('--expected-sha256')
    a=ap.parse_args()
    try:
        pick_point(a.kind,CameraView.from_json(a.state),a.u,a.v,a.output,
                   a.input,a.expected_sha256)
    except (OSError,ValueError,TypeError) as e:
        code='SOURCE_CHANGED' if 'changed' in str(e) else 'INVALID'
        print('SCANTOPATH_POINT_PICK_REJECTED:'+code,flush=True)
        return 2
    print('SCANTOPATH_POINT_PICK_OK',flush=True)
    return 0

if __name__=='__main__':
    raise SystemExit(main())
