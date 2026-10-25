"""08.04: pure camera contract and native isolated renderer acceptance."""
from __future__ import annotations
import hashlib
import json
import math
import os
from pathlib import Path
import subprocess
import sys
import pytest

from scantopath.modules.viewer3d.application.navigation import CameraView


def test_camera_contract_orbit_pan_zoom_reset_and_axes():
    camera = CameraView()
    assert camera.zoom == 1 and not camera.axes
    moved = camera.update('orbit', 30, 20).update('pan', 60, -90).update('zoom', 2)
    assert moved.azimuth == 30 and moved.elevation == 20
    assert moved.pan_x == pytest.approx(.1) and moved.pan_y == pytest.approx(-.15)
    assert moved.zoom == pytest.approx(1.5625)
    assert moved.axes is False
    assert camera == CameraView()  # immutable input unchanged
    assert moved.update('axes').axes
    assert moved.update('reset') == CameraView()
    assert moved.update('axes').update('reset').axes
    assert CameraView.from_json(moved.to_json()) == moved


@pytest.mark.parametrize('data', [
    '{"bad":1}', '[]', '{}', 'not-json', '{"azimuth": NaN}',
    CameraView(axes=True).to_json().replace('"axes":true', '"axes":42'),
])
def test_untrusted_navigation_payload_rejected(data):
    with pytest.raises((ValueError, TypeError)):
        CameraView.from_json(data)


@pytest.mark.parametrize('action,x,y', [
    ('unknown',0,0), ('orbit',float('nan'),0), ('pan',float('inf'),0),
    ('zoom',True,0), ('axes',10001,0), ('orbit','bad',0),
])
def test_invalid_controls_rejected(action,x,y):
    with pytest.raises((ValueError, TypeError)):
        CameraView().update(action,x,y)


def test_camera_clamps_extreme_user_moves():
    p = CameraView().update('orbit',10000,10000).update('zoom',1000).update('pan',10000,-10000)
    assert p.elevation == 80 and p.zoom == 30.0 and abs(p.pan_x) <= 2 and abs(p.pan_y) <= 2


def _subprocess(*arguments):
    root=Path(__file__).resolve().parents[1]
    env={**os.environ,'PYTHONPATH':str(root/'src')+os.pathsep+os.environ.get('PYTHONPATH','')}
    return subprocess.run([sys.executable,'-X','faulthandler','-m',
        'scantopath.modules.viewer3d.infrastructure.render_navigation',*map(str,arguments)],
        cwd=root, env=env, stdout=subprocess.PIPE,stderr=subprocess.PIPE,timeout=45)


def test_isolated_fixture_orbit_zoom_axes_produces_distinct_png(tmp_path):
    a=tmp_path/'a.png';b=tmp_path/'b.png'
    neutral=CameraView().to_json()
    moved=CameraView().update('orbit',45,20).update('zoom',2).update('axes').to_json()
    p=_subprocess('--kind','fixture','--output',a,'--state',neutral)
    assert p.returncode==0,p.stderr[-1200:]
    q=_subprocess('--kind','fixture','--output',b,'--state',moved)
    assert q.returncode==0,q.stderr[-1200:]
    assert b'SCANTOPATH_NAV_PREVIEW_OK' in q.stdout
    assert a.read_bytes().startswith(b'\x89PNG\r\n\x1a\n')
    assert b.read_bytes().startswith(b'\x89PNG\r\n\x1a\n')
    assert hashlib.sha256(a.read_bytes()).digest()!=hashlib.sha256(b.read_bytes()).digest()


def test_isolated_ply_camera_keeps_source_and_metadata(tmp_path):
    path=tmp_path/'fixture.ply'
    path.write_text('ply\nformat ascii 1.0\nelement vertex 4\nproperty float x\nproperty float y\n'
                    'property float z\nend_header\n0 0 0\n1 0 0\n0 1 0\n0 0 1\n',encoding='ascii')
    original=path.read_bytes(); sha=hashlib.sha256(original).hexdigest()
    out=tmp_path/'render.png';meta=tmp_path/'render.json'
    p=_subprocess('--kind','ply','--output',out,'--metadata',meta,'--input',path,
                  '--expected-sha256',sha,'--state',CameraView().update('orbit',45,15).to_json())
    assert p.returncode==0,p.stderr[-1200:]
    assert b'SCANTOPATH_NAV_PREVIEW_OK' in p.stdout
    data=json.loads(meta.read_text(encoding='utf-8'))
    assert data['point_count']==4 and data['source_sha256']==sha
    assert data['units']==data['coordinate_frame']=='unknown'
    assert path.read_bytes()==original
    assert out.read_bytes().startswith(b'\x89PNG\r\n\x1a\n')
    # Refuse navigation when source changed since successful import.
    path.write_bytes(original+b'\n')
    bad=_subprocess('--kind','ply','--output',tmp_path/'no.png',
                    '--metadata',tmp_path/'no.json','--input',path,
                    '--expected-sha256',sha,'--state',CameraView().to_json())
    assert bad.returncode==2
    assert not (tmp_path/'no.png').exists()
    assert path.read_bytes()!=original


def test_no_qt_vtk_in_application_domain_and_no_database_import():
    import ast
    base=Path(__file__).resolve().parents[1]/'src/scantopath/modules/viewer3d'
    for path in list((base/'application').glob('*.py')) + list((base/'domain').glob('*.py')):
        tree=ast.parse(path.read_text('utf-8'))
        imports=[n.module for n in ast.walk(tree) if isinstance(n,ast.ImportFrom) and n.module]
        imports +=[a.name for n in ast.walk(tree) if isinstance(n,ast.Import) for a in n.names]
        assert not any(i.startswith(('vtk','PySide6','scantopath.metadata','scantopath.storage')) for i in imports)
