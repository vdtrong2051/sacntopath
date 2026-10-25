"""08.05 isolated point-picking and data contract (no GUI required)."""
from __future__ import annotations
import json
import os
from pathlib import Path
import subprocess
import sys

import pytest
from scantopath.modules.viewer3d.application.picking import PickResult,image_click_uv
from scantopath.modules.viewer3d.application.navigation import CameraView
from scantopath.modules.viewer3d.infrastructure.ply_header import inspect_ply
from scantopath.modules.viewer3d.infrastructure.pick_point import pick_point


def test_letterbox_coordinates_and_bottom_left_vtk():
    assert image_click_uv(50,0,300,200,200,200) == (0.0, 1.0)
    assert image_click_uv(249,301,300,400,200,200) is None
    assert image_click_uv(150,200,300,400,200,200) == pytest.approx((100/199, 1-100/199))
    assert image_click_uv(20,100,300,200,200,200) is None
    with pytest.raises(ValueError):image_click_uv(float('nan'),10,300,200,200,200)
    with pytest.raises(ValueError):image_click_uv(1,1,10,20,30,20)


def test_pick_contract_rejects_malformed_and_metric_claims():
    raw={'hit':True,'point_id':0,'xyz':[1.,2.,3.],'rgb':[5,50,255],
         'display_uv':[.5,.5],'source_id':'fixture:08.02',
         'units':'unknown','coordinate_frame':'unknown'}
    result=PickResult.from_result(raw)
    assert result.point_id==0 and result.rgb==(5,50,255)
    for bad in [dict(raw,point_id=True),dict(raw,xyz=[1,float('nan'),3]),
                dict(raw,units='mm'),dict(raw,display_uv=[.5,-.2]),
                dict(raw,rgb=[256,0,0]),dict(raw,untrusted_data='x'),
                dict(raw,hit=False),dict(raw,source_id='')]:
        with pytest.raises(ValueError):PickResult.from_result(bad)
    miss=dict(raw,hit=False,point_id=None,xyz=None,rgb=None,display_uv=None)
    assert PickResult.from_result(miss).hit is False


def test_native_fixture_pick_known_ids_and_miss(tmp_path):
    # Screen locations are deterministic for the accepted 1000x620 fixture.
    coords=[(.350,.258),(.651,.258),(.350,.744),(.297,.172),(.704,.829)]
    expected=[(0.,0.,0.),(.25,0.,0.),(0.,.25,0.),(0.,0.,.25),(.25,.25,.25)]
    for idx,(u,v) in enumerate(coords):
        picked=pick_point('fixture',CameraView(),u,v,tmp_path/'result.json')
        assert picked.hit and picked.point_id == idx
        assert picked.xyz == expected[idx]
        assert picked.rgb is None
    miss=pick_point('fixture',CameraView(),.05,.05,tmp_path/'miss.json')
    assert not miss.hit and miss.point_id is None
    assert PickResult.from_result(json.loads((tmp_path/'miss.json').read_text())).hit is False


def _ply(path: Path) -> Path:
    path.write_text('ply\nformat ascii 1.0\nelement vertex 1\n'
                    'property float x\nproperty float y\nproperty float z\n'
                    'property uchar red\nproperty uchar green\nproperty uchar blue\n'
                    'end_header\n0 0 0 18 177 243\n',encoding='ascii')
    return path


def test_native_ply_color_and_source_fingerprint(tmp_path):
    source=_ply(tmp_path/'one.ply')
    fingerprint=inspect_ply(source).source_sha256
    original=source.read_bytes()
    result=pick_point('ply',CameraView(),.5,.5,tmp_path/'result.json',source,fingerprint)
    assert result.point_id==0 and result.xyz==(0.,0.,0.) and result.rgb==(18,177,243)
    assert result.source_id==fingerprint
    assert result.units==result.coordinate_frame=='unknown'
    assert source.read_bytes()==original
    with pytest.raises(ValueError,match='changed'):
        pick_point('ply',CameraView(),.5,.5,tmp_path/'stale.json',source,'0'*64)
    assert not (tmp_path/'stale.json').exists()


def test_isolated_picker_subprocess_uses_machine_readable_result(tmp_path):
    source=_ply(tmp_path/'one.ply')
    result=tmp_path/'picked.json'
    root=Path(__file__).resolve().parents[1]
    environment={**os.environ,'PYTHONPATH':str(root/'src')}
    module='scantopath.modules.viewer3d.infrastructure.pick_point'
    proc=subprocess.run([sys.executable,'-m',module,'--kind','ply',
        '--state',CameraView().to_json(),'--u','0.5','--v','0.5',
        '--input',str(source),'--expected-sha256',inspect_ply(source).source_sha256,
        '--output',str(result)],env=environment,capture_output=True,text=True,timeout=25)
    assert proc.returncode==0,proc.stdout+proc.stderr
    assert 'SCANTOPATH_POINT_PICK_OK' in proc.stdout
    assert PickResult.from_result(json.loads(result.read_text())).rgb==(18,177,243)
    result.unlink()
    proc=subprocess.run([sys.executable,'-m',module,'--kind','ply',
        '--state',CameraView().to_json(),'--u','0.5','--v','0.5',
        '--input',str(source),'--expected-sha256','0'*64,
        '--output',str(result)],env=environment,capture_output=True,text=True,timeout=25)
    assert proc.returncode==2 and 'SOURCE_CHANGED' in proc.stdout
    assert not result.exists()


def test_application_and_domain_never_import_gui_or_vtk():
    import ast
    root=Path(__file__).resolve().parents[1]/'src/scantopath/modules/viewer3d'
    for layer in ('application','domain'):
        for file in (root/layer).rglob('*.py'):
            t=ast.parse(file.read_text(encoding='utf8'))
            targets=[n.module for n in ast.walk(t) if isinstance(n,ast.ImportFrom) and n.module]
            targets.extend(a.name for n in ast.walk(t) if isinstance(n,ast.Import) for a in n.names)
            assert not any(s.startswith(('PySide6','vtk','scantopath.ui')) for s in targets),file
