"""FT-06.1 R2 provenance and no-stale-pose integration contracts."""
import inspect
from scantopath.modules.geometry.presentation.live_geometry_worker import LiveGeometryThread
from scantopath.modules.capture.application.live_snapshot import FrozenGeometry, freeze_geometry, save_snapshot
from scantopath.modules.geometry.application.live_charuco_isolation import (
    CharucoIsolationResult, isolate_charuco_object,
)


def test_optical_flow_requires_current_depth_isolation():
    source=inspect.getsource(LiveGeometryThread.run)
    assert 'pose_provider=self._pose_bridge.estimate' in source
    assert 'if not isolated.usable:' in source
    assert 'scope_revision != self._scope_revision' in source
    assert 'self._pose_bridge.reset()' in source


def test_snapshot_records_research_pose_provenance():
    assert 'board_pose_source' in inspect.signature(freeze_geometry).parameters
    source=inspect.getsource(save_snapshot)
    assert "'board_pose_is_estimated'" in source
    assert 'board_pose_source' in FrozenGeometry.__dataclass_fields__


def test_conventional_mode_backward_compatible():
    assert 'pose_provider' in inspect.signature(isolate_charuco_object).parameters
    r=CharucoIsolationResult('CHARUCO_OBJECT_FOUND',None,0,0,None,0.,0,'sample')
    assert r.pose_source=='detected' and r.pose_age_frames==0
    w=LiveGeometryThread()
    assert w.statistics()['scope_mode']=='scene'
    assert w.statistics()['reference_mode']=='depth'
    w.request_stop()
