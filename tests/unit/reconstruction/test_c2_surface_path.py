"""C2 focused geometric and artifact integrity tests, no camera or Qt required."""
from __future__ import annotations
from hashlib import sha256
import json
import sys
from types import ModuleType
import numpy as np
import pytest

from scantopath.modules.reconstruction.application import c2_surface_path as core
import c2_surface_to_path as cli


def sample_plane(n=29):
    x,y=np.meshgrid(np.linspace(-.065,.065,n), np.linspace(-.055,.055,n))
    z=.64+.011*np.sin(x*18)+.003*np.cos(y*20)
    xyz=np.column_stack((x.ravel(),y.ravel(),z.ravel()))
    nrm=np.column_stack((-.011*18*np.cos(x.ravel()*18), .003*20*np.sin(y.ravel()*20),
                          np.ones(len(x.ravel()))))
    nrm /= np.linalg.norm(nrm,axis=1)[:,None]
    return xyz,nrm


def test_reconstruction_and_both_paths():
    xyz,nrm=sample_plane()
    vertices,faces,quality=core.reconstruct_surface(xyz,nrm)
    assert len(faces)>=100
    assert len(vertices)>100
    assert quality['underside_coverage_verified'] is False
    assert quality['interpolated_unsupported_faces_exported']==0
    assert np.isfinite(vertices).all()
    for kind in ('zigzag','contour'):
        lines,report=core.generate_paths(vertices,faces,xyz,nrm,kind=kind)
        assert report['path_points']>=12
        assert report['robot_executable'] is False
        assert all(np.allclose(np.linalg.norm(p['normals'],axis=1),1.,atol=.02) for p in lines)
        # Points must remain near measured sensor cloud: no floating lines.
        ds,_=core.Nearest(xyz).query(np.concatenate([l['points'] for l in lines]))
        assert ds.max()<=.014+1e-10


def test_flat_surface_has_boundary_contour():
    x,y=np.meshgrid(np.linspace(-.04,.04,21), np.linspace(-.04,.04,21))
    xyz=np.column_stack((x.ravel(),y.ravel(),np.full(x.size,.5)))
    nrm=np.tile([0,0,1.],(len(xyz),1))
    vertices,faces,_=core.reconstruct_surface(xyz,nrm)
    lines,q=core.generate_paths(vertices,faces,xyz,nrm,kind='contour')
    assert len(lines)>0 and q['path_points']>2


def test_config_and_invalid_source():
    xyz,nrm=sample_plane()
    with pytest.raises(core.C2Error, match='C2_CONFIG_INVALID'):
        core.C2Config(mesh_spacing_m=0)
    with pytest.raises(core.C2Error, match='C2_NORMALS_OR_EXTENT_INVALID'):
        core.reconstruct_surface(xyz,nrm*100)
    with pytest.raises(core.C2Error, match='C2_C1_POINTS_INVALID'):
        core.reconstruct_surface(np.full_like(xyz,float('nan')),nrm)


def test_numpy_nearest_self_zero(monkeypatch):
    xyz,_=sample_plane(11)
    monkeypatch.setattr(core,'cKDTree',None)
    distances,ix=core.Nearest(xyz).query(xyz)
    assert distances.max()==0.
    assert np.array_equal(ix,np.arange(len(xyz)))


def test_ply_mesh_and_path_preview_vtk():
    import vtk
    xyz,nrm=sample_plane()
    vertices,faces,_=core.reconstruct_surface(xyz,nrm)
    data=cli._ply_mesh(vertices,faces)
    assert f'element face {len(faces)}'.encode() in data
    import tempfile
    from pathlib import Path
    with tempfile.TemporaryDirectory() as d:
        f=Path(d)/'mesh.ply';f.write_bytes(data)
        reader=vtk.vtkPLYReader();reader.SetFileName(str(f));reader.Update()
        assert reader.GetOutput().GetNumberOfPolys()==len(faces)
        path,_=core.generate_paths(vertices,faces,xyz,nrm,kind='zigzag')
        f=Path(d)/'preview.ply';f.write_bytes(cli._preview_ribbon(path,[245,142,44]))
        reader=vtk.vtkPLYReader();reader.SetFileName(str(f));reader.Update()
        assert reader.GetOutput().GetNumberOfPolys()>10


def test_full_export_sha_verify_and_tamper(tmp_path,monkeypatch):
    xyz,nrm=sample_plane()
    c1=tmp_path/'c1_sample';c1.mkdir()
    (c1/'normal_xyz.csv').write_text('x_m,y_m,z_m,nx,ny,nz,source_sample_index\n'+
        ''.join(','.join(str(float(a)) for a in (*p,*n))+',0\n' for p,n in zip(xyz,nrm)),encoding='utf8')
    (c1/'object_quality.json').write_text(json.dumps({'no_inferred_geometry':True,
        'output_measured_points':len(xyz),'world_frame':'depth_optical_of_sample_0'}))
    (c1/'registration_quality.json').write_text(json.dumps({'views_accepted':3}))
    (c1/'processing_run.json').write_text(json.dumps({'run_id':'c1_demo',
        'output_points':len(xyz),'metric_accuracy_verified':False,
        'metric_gate':'NOT_TESTED','accepted_capture_ids':['a','b','c']}))
    (c1/'sha256_manifest.json').write_text(json.dumps({'dummy':'test'}))
    fake=ModuleType('c1_trusted_cloud')
    fake.verify=lambda folder:{'points':len(xyz)}
    monkeypatch.setitem(sys.modules,'c1_trusted_cloud',fake)
    out=cli.execute(c1,tmp_path/'results')
    proof=cli.verify(out)
    assert proof['zigzag_points']>10
    assert proof['contour_points']>2
    assert (out/'surface_mesh.ply').is_file()
    result=json.loads((out/'surface_coverage.json').read_text())
    assert result['underside_coverage_verified'] is False
    assert (out/'processing_run.json').is_file()
    assert len(list(out.iterdir()))==9
    assert cli.verify(out)==proof
    source_hash=sha256((c1/'normal_xyz.csv').read_bytes()).hexdigest()
    assert source_hash==sha256((c1/'normal_xyz.csv').read_bytes()).hexdigest()
    f=out/'contour.csv';f.write_bytes(f.read_bytes()+b'edited')
    with pytest.raises(core.C2Error,match='C2_OUTPUT_SHA_MISMATCH'):
        cli.verify(out)
