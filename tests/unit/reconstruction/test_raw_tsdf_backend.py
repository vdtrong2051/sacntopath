import importlib.util
import json
import tempfile
import unittest
from pathlib import Path
import numpy as np
spec=importlib.util.spec_from_file_location('raw_tsdf_fusion',Path(__file__).resolve().parents[3]/'scripts'/'raw_tsdf_fusion.py')
import sys
module=importlib.util.module_from_spec(spec);sys.modules[spec.name]=module;spec.loader.exec_module(module)


def view(sample=0, shift=0., drop=False, z_mm=600):
    H=W=90
    raw=np.full((H,W),z_mm,dtype=np.uint16)
    mask=np.zeros((H,W),bool);mask[15:75,15:75]=True
    if drop:mask[35:40,:]=False
    fx=fy=600.;cx=cy=45.
    y,x=np.nonzero(mask)
    z=raw[y,x]*.001
    xyz=np.stack(((x-cx)/fx*z,(y-cy)/fy*z,z),axis=1)
    T=np.eye(4);T[0,3]=shift
    xyz[:,0]+=shift
    return module.DepthView(sample,'sample'+str(sample),raw,mask,fx,fy,cx,cy,.001,T,xyz)

class TestTsdf(unittest.TestCase):
    def test_config_bad(self):
        with self.assertRaises(module.TsdfError):module.Config(voxel_mm=.5)
    def test_smooth_does_not_fill_missing(self):
        x=view(); x.raw_depth_u16[34,34]=602
        y=module.smooth_masked_depth(x.raw_depth_u16,x.mask,4)
        self.assertEqual(y[34,34],600)
        self.assertEqual(y[3,3],x.raw_depth_u16[3,3])
        self.assertFalse(x.mask[3,3])
    def test_volume_budget(self):
        with self.assertRaises(module.TsdfError) as e:
            module.calculate_volume([view()],module.Config(max_voxels=10000))
        self.assertEqual(e.exception.code,'TSDF_VOLUME_BUDGET_EXCEEDED')
    def test_synthetic_fusion_and_vtk_mesh(self):
        v0=view();v1=view(1,0.002)
        cfg=module.Config(voxel_mm=2.5,truncation_mm=9,support_mm=8)
        tsdf,weight,support,low,diagnostics=module.integrate_tsdf([v0,v1],cfg)
        self.assertGreater(np.count_nonzero(weight),50)
        self.assertGreater(np.count_nonzero(support>=2),10)
        vv,ff,report=module.reconstruct_mesh(tsdf,weight,low,cfg,np.vstack([v0.measured_xyz_world,v1.measured_xyz_world]))
        self.assertGreater(len(ff),12)
        self.assertLess(np.ptp(vv[:,2]),.02)
        self.assertFalse(report['underside_verified'])
        self.assertTrue(module._ply_bytes(vv,ff).startswith(b'ply\n'))
    def test_no_observation(self):
        x=view();x.T_world_depth[:3,3]=[3.,3.,3.]
        # world bounds follow measured, so inconsistent transform must not claim a surface.
        with self.assertRaises(module.TsdfError):module.integrate_tsdf([x],module.Config())
    def test_21_view_fusion(self):
        cfg=module.Config(voxel_mm=2.5,truncation_mm=9,support_mm=8)
        views=[view(i,shift=(i-10)*.00025) for i in range(21)]
        tsdf,weights,support,low,records=module.integrate_tsdf(views,cfg)
        self.assertEqual(len(records),21)
        self.assertGreater(np.count_nonzero(support>=2),100)
        verts,faces,report=module.reconstruct_mesh(tsdf,weights,low,cfg,
            np.concatenate([v.measured_xyz_world for v in views]))
        self.assertGreater(len(faces),100)
        self.assertLess(np.ptp(verts[:,2]),.02)

    def test_manifest_tamper(self):
        with tempfile.TemporaryDirectory() as td:
            p=Path(td);a=b'abc';(p/'tsdf_fused_mesh.ply').write_bytes(a)
            (p/'sha256_manifest.json').write_bytes(module.json_bytes({'files':{'tsdf_fused_mesh.ply':module.sha256(a).hexdigest()}}))
            self.assertTrue(module._verify_result(p))
            (p/'tsdf_fused_mesh.ply').write_bytes(b'xyz')
            with self.assertRaises(module.TsdfError):module._verify_result(p)

if __name__=='__main__':unittest.main()
