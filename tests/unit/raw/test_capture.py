import json
import numpy as np
import pytest
from scantopath.acquisition.sources import SyntheticSource, FrameBundle, OrbbecSDKv2Source
from scantopath.domain.models import CaptureMetadata, CaptureKind, Pose
from scantopath.storage.session_store import SessionStore


def test_commit_and_replay(tmp_path):
    store = SessionStore(tmp_path)
    final = store.commit(SyntheticSource().capture(), "session-1", "object-1", Pose())
    assert (final/"COMMITTED").is_file()
    assert store.list_committed("session-1") == [final]
    meta, depth, rgb = store.read(final)
    assert not meta.measured and meta.kind == CaptureKind.SYNTHETIC
    assert depth.dtype == np.uint16 and rgb.shape == (48,64,3)
    assert (depth>0).any()
    assert meta.depth_scale_m_per_unit == 0.001


def test_reject_synthetic_as_measured():
    f = SyntheticSource().capture()
    with pytest.raises(ValueError):
        CaptureMetadata(session_id="s", specimen_id="p", kind="synthetic",
                        camera_model="fake", intrinsics=f.intrinsics,
                        depth_scale_m_per_unit=0.001, measured=True, pose=Pose())


def test_reject_shape_mismatch_and_traversal(tmp_path):
    store=SessionStore(tmp_path)
    f=SyntheticSource().capture()
    with pytest.raises(ValueError):store.commit(f,"../escape","sample")
    bad=FrameBundle(rgb=f.rgb,depth=f.depth[:,1:],intrinsics=f.intrinsics,
                    scale_m_per_unit=f.scale_m_per_unit,kind=f.kind,camera_model=f.camera_model)
    with pytest.raises(ValueError):store.commit(bad,"valid","sample")


def test_camera_not_claimed_working():
    with pytest.raises(NotImplementedError):OrbbecSDKv2Source().capture()


def test_reject_uncommitted(tmp_path):
    with pytest.raises(ValueError):SessionStore(tmp_path).read(tmp_path)
