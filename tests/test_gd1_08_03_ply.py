"""08.03 PLY format/provenance/child render acceptance; no Qt required."""
from __future__ import annotations
import json
import os
from pathlib import Path
import struct
import subprocess
import sys

import pytest
from scantopath.modules.viewer3d.application.ply_contracts import PlySummary
from scantopath.modules.viewer3d.infrastructure.ply_header import inspect_ply


def ascii_ply(path: Path, *, colors: bool = False) -> Path:
    header = ('ply\nformat ascii 1.0\nelement vertex 3\n'
              'property float x\nproperty float y\nproperty float z\n')
    if colors:
        header += 'property uchar red\nproperty uchar green\nproperty uchar blue\n'
    header += 'end_header\n'
    rows = ['0 0 0', '1 0 0', '0 2 0']
    if colors:
        rows = [a + b for a, b in zip(rows, (' 255 0 0', ' 0 255 0', ' 0 0 255'))]
    path.write_text(header + '\n'.join(rows) + '\n', encoding='ascii')
    return path


def test_ascii_xyz_and_rgb_header_sha256(tmp_path):
    p=ascii_ply(tmp_path/'valid.ply', colors=True)
    header=inspect_ply(p)
    assert header.vertex_count==3 and header.ply_format=='ascii' and header.has_rgb
    assert header.source_bytes==p.stat().st_size
    import hashlib
    assert header.source_sha256==hashlib.sha256(p.read_bytes()).hexdigest()


def test_binary_ply_little_endian(tmp_path):
    p=tmp_path/'binary.ply'
    p.write_bytes(b'ply\nformat binary_little_endian 1.0\nelement vertex 1\n'
                  b'property float x\nproperty float y\nproperty float z\nend_header\n'
                  +struct.pack('<fff',1.,2.,3.))
    assert inspect_ply(p).vertex_count==1
    assert inspect_ply(p).ply_format=='binary_little_endian'


@pytest.mark.parametrize('contents', [
    b'junk\n',
    b'ply\nformat ascii 1.0\nelement vertex 2\nproperty float x\nend_header\n',
    b'ply\nformat ascii 1.0\nelement vertex 999999999\n'
    b'property float x\nproperty float y\nproperty float z\nend_header\n',
    b'ply\nformat ascii 1.0\nelement vertex 1\n'
    b'property list uchar int x\nproperty float y\nproperty float z\nend_header\n',
])
def test_invalid_header_rejected(tmp_path,contents):
    p=tmp_path/'bad.ply';p.write_bytes(contents)
    with pytest.raises(ValueError):inspect_ply(p)


def test_source_contract_rejects_untrusted_metric_units(tmp_path):
    p=ascii_ply(tmp_path/'fixture.ply')
    header=inspect_ply(p)
    d=dict(name=p.name,source_sha256=header.source_sha256,source_bytes=header.source_bytes,
           point_count=3,bounds=[0.,1.,0.,2.,0.,0.],has_rgb=False,
           ply_format='ascii',units='unknown',coordinate_frame='unknown')
    result=PlySummary.from_result(d)
    assert result.units==result.coordinate_frame=='unknown'
    for invalid in (dict(d, units='mm'),dict(d,point_count=True),
                    dict(d,bounds=[0,1,0,2,0,float('nan')]),dict(d,source_sha256='wrong')):
        with pytest.raises(ValueError):PlySummary.from_result(invalid)


def test_render_ply_in_separate_process_has_real_points(tmp_path):
    p=ascii_ply(tmp_path/'3-points.ply', colors=True)
    original = p.read_bytes()
    png=tmp_path/'preview.png'; metadata=tmp_path/'metadata.json'
    env={**os.environ,'PYTHONPATH':str(Path(__file__).resolve().parents[1]/'src')}
    proc=subprocess.run([sys.executable,'-X','faulthandler','-m',
          'scantopath.modules.viewer3d.infrastructure.render_ply',
          '--input',str(p),'--output',str(png),'--metadata',str(metadata)],
          env=env,capture_output=True,text=True,timeout=60)
    assert proc.returncode==0,proc.stdout+proc.stderr
    assert 'SCANTOPATH_PLY_PREVIEW_OK' in proc.stdout
    assert png.read_bytes().startswith(b'\x89PNG\r\n\x1a\n')
    result=PlySummary.from_result(json.loads(metadata.read_text(encoding='utf-8')))
    assert result.point_count==3 and result.bounds==(0.,1.,0.,2.,0.,0.)
    assert result.name==p.name and result.has_rgb
    assert p.read_bytes()==original


def test_bad_ply_isolated_child_fails_without_main_process_crash(tmp_path):
    p=tmp_path/'bad.ply';p.write_bytes(b'not a ply')
    out=tmp_path/'preview.png'; meta=tmp_path/'result.json'
    proc=subprocess.run([sys.executable,'-m','scantopath.modules.viewer3d.infrastructure.render_ply',
             '--input',str(p),'--output',str(out),'--metadata',str(meta)],
            capture_output=True,text=True,timeout=15)
    assert proc.returncode!=0
    assert not out.exists() and not meta.exists()


def test_binary_ply_renders_real_points_in_subprocess(tmp_path):
    path=tmp_path/'binary_real.ply'
    hdr=(b'ply\nformat binary_little_endian 1.0\nelement vertex 3\n'
         b'property float x\nproperty float y\nproperty float z\nend_header\n')
    original=hdr+b''.join(struct.pack('<fff',*v) for v in ((-1.,0.,0.),(2.,4.,0.),(0.,0.,5.)))
    path.write_bytes(original)
    png=tmp_path/'result.png'; meta=tmp_path/'result.json'
    p=subprocess.run([sys.executable,'-m',
                      'scantopath.modules.viewer3d.infrastructure.render_ply',
                      '--input',str(path),'--output',str(png),'--metadata',str(meta)],
                     capture_output=True,text=True,timeout=60)
    assert p.returncode==0, p.stderr
    result=PlySummary.from_result(json.loads(meta.read_text(encoding='utf-8')))
    assert result.point_count==3
    assert result.bounds==(-1.,2.,0.,4.,0.,5.)
    assert not result.has_rgb and result.ply_format=='binary_little_endian'
    assert path.read_bytes()==original
    assert png.read_bytes().startswith(b'\x89PNG\r\n\x1a\n')
