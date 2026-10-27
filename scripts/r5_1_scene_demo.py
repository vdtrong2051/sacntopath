"""R5.1 read-only native fixture demonstration. Evidence is outside the repo."""
from __future__ import annotations
import argparse
import hashlib
import json
from pathlib import Path
from tempfile import TemporaryDirectory

from scantopath.modules.viewer3d.infrastructure.resident_poc.client import ResidentRenderClient
from scantopath.modules.viewer3d.application.scene_contracts import SceneDescriptor

FIXTURES = {
    'ply_points.ply': ('ply\nformat ascii 1.0\nelement vertex 4\nproperty float x\n'
                       'property float y\nproperty float z\nend_header\n'
                       '0 0 0\n1 0 0\n1 1 0\n0 1 0\n'),
    'ply_faces.ply': ('ply\nformat ascii 1.0\nelement vertex 4\nproperty float x\n'
                      'property float y\nproperty float z\nelement face 1\n'
                      'property list uchar int vertex_indices\nend_header\n'
                      '0 0 0\n1 0 0\n1 1 0\n0 1 0\n4 0 1 2 3\n'),
    'obj_faces.obj': 'v 0 0 0\nv 1 0 0\nv 1 1 0\nv 0 1 0\nf 1 2 3 4\n',
}


def run(evidence_dir: Path) -> Path:
    if evidence_dir.is_symlink():
        raise ValueError('UNSAFE_EVIDENCE_DIR')
    evidence_dir.mkdir(parents=True, exist_ok=True)
    receipt = evidence_dir / 'R5_1_GEOMETRY_PROOF.json'
    if receipt.exists():
        receipt.unlink()  # Never accept stale PASS if a new run fails.
    with TemporaryDirectory(prefix='r51-fixtures-') as work:
        cases = []
        paths = []
        for name, content in FIXTURES.items():
            p = Path(work) / name
            p.write_text(content, encoding='ascii')
            paths.append(p)
        with ResidentRenderClient(256, 192, timeout=60) as client:
            pid = client.pid
            for path in paths:
                sha = hashlib.sha256(path.read_bytes()).hexdigest()
                response = client.open_source(path.resolve(), sha)
                descriptor = SceneDescriptor.from_result(response)
                expected_kind = 'points' if path.name == 'ply_points.ply' else 'mesh'
                if descriptor.geometry_kind != expected_kind or descriptor.point_count != 4 or descriptor.face_count != (0 if expected_kind == 'points' else 1):
                    raise RuntimeError('GEOMETRY_MISMATCH')
                if descriptor.source_sha256 != sha or hashlib.sha256(path.read_bytes()).hexdigest() != sha:
                    raise RuntimeError('SOURCE_CHANGED')
                client.camera('orbit', 18, 8)
                if client.pid != pid or response['open_count'] != len(cases) + 1:
                    raise RuntimeError('RENDER_HOST_RESTARTED')
                cases.append({'name': path.name, 'kind': descriptor.geometry_kind,
                              'vertices': descriptor.point_count, 'faces': descriptor.face_count,
                              'sha256': sha, 'scene_revision': response['scene_revision']})
        report = {'schema':'r5.1-geometry-proof-v1', 'status':'PASS',
                  'cases':cases,'process_reused':True,'source_unchanged':True,
                  'limitations':'Fixture point, quad PLY and OBJ only; not UI HMI/picking or external OBJ materials.'}
        receipt.write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
        print('R5.1 GEOMETRY PASS: 3 fixtures, single host, read-only input',flush=True)
    return receipt


def main() -> int:
    parser=argparse.ArgumentParser()
    parser.add_argument('--evidence-dir',type=Path,required=True)
    result=run(parser.parse_args().evidence_dir)
    print('R5.1 receipt:',result,flush=True)
    return 0

if __name__=='__main__':
    raise SystemExit(main())
