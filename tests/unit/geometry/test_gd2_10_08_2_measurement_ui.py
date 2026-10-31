"""GD2-10.08.2: PLY RGB-index mapping and Qt presenter fail-closed gates."""
from dataclasses import replace
from hashlib import sha256

import numpy as np
import pytest
from PySide6.QtCore import QObject, Signal
from PySide6.QtWidgets import QApplication, QVBoxLayout, QWidget

from scantopath.modules.geometry.application.measurements import MeasurementError
from scantopath.modules.geometry.application.service import GeometryService
from tests.support.raw_fixture import raw
from scantopath.modules.viewer3d.application.scene_contracts import SceneSelectionRef
from scantopath.ui.shell.geometry_measurement import (
    PreviewMeasurementSession, GeometryMeasurementPanel,
)
from scantopath.ui.shell.geometry_preview import write_preview_ply


def fixture(tmp_path):
    packet = raw()
    meta = packet.metadata
    rgb = np.full((meta.color.height, meta.color.width, 3), (21, 133, 219), dtype=np.uint8)
    view = GeometryService.process(depth_u16=packet.depth_u16_copy(), color_rgb=rgb,
                                  metadata=meta, capture_id=meta.capture_id)
    assert len(view.colored_point_indices) >= 3
    # Simulate a colored subset with gaps: PLY index must not be used as XYZ ID.
    ids = view.colored_point_indices[::2].copy()
    colors = view.colors_rgb[::2].copy()
    view = replace(view, colored_point_indices=ids, colors_rgb=colors)
    receipt = write_preview_ply(view, tmp_path/'temporary.ply')
    return view, receipt


def pick(view, receipt, row, rev=3):
    p = view.points_xyz_m[view.colored_point_indices[row]]
    rounded = tuple(float(x) for x in np.asarray(p, dtype=np.float32))
    return SceneSelectionRef(receipt.ply_sha256, rev, 'point', row, rounded)


def test_real_mapping_and_distance_uses_xyz64_not_ply_float32(tmp_path):
    view, r = fixture(tmp_path)
    s = PreviewMeasurementSession(view, r, 3)
    a = pick(view,r,0)
    b = pick(view,r,1)
    assert s.consume(a) is None
    result = s.consume(b)
    x0, x1 = (view.points_xyz_m[view.colored_point_indices[j]] for j in (0,1))
    assert result.point_indices == (int(view.colored_point_indices[0]), int(view.colored_point_indices[1]))
    assert result.distance_m == pytest.approx(float(np.linalg.norm(x1-x0)))
    assert result.distance_mm == pytest.approx(result.distance_m * 1000)
    assert result.status == 'PROVISIONAL_NOT_METRIC_VALIDATED'
    assert result.source_capture_id == r.capture_id
    assert len(result.cloud_revision_sha256) == 64


def test_third_click_begins_new_pair(tmp_path):
    view,r=fixture(tmp_path); s=PreviewMeasurementSession(view,r,3)
    s.consume(pick(view,r,0)); assert s.consume(pick(view,r,1)) is not None
    assert s.consume(pick(view,r,2)) is None
    assert s.first.point_index == int(view.colored_point_indices[2]) and s.last is None


@pytest.mark.parametrize('change', ['source','revision','kind','index','coordinates','units'])
def test_fail_closed_mismatched_or_tampered_pick(tmp_path, change):
    view,r=fixture(tmp_path); s=PreviewMeasurementSession(view,r,3)
    x=pick(view,r,0)
    if change=='source': x=replace(x,source_sha256='0'*64)
    elif change=='revision': x=replace(x,scene_revision=5)
    elif change=='kind': x=replace(x,kind='face')
    elif change=='index': x=replace(x,element_id=len(view.colored_point_indices))
    elif change=='coordinates': x=replace(x,xyz=(x.xyz[0]+.1,x.xyz[1],x.xyz[2]))
    else:
        # SceneSelectionRef refuses unverified metric provenance at construction.
        with pytest.raises(ValueError, match='UNVERIFIED_METRIC_PROVENANCE'):
            replace(x, units='m')
        return
    with pytest.raises(MeasurementError):s.consume(x)
    assert s.first is None


def test_reject_other_capture_and_invalid_mapping(tmp_path):
    view,r=fixture(tmp_path)
    with pytest.raises(MeasurementError):
        PreviewMeasurementSession(replace(view,geometry=replace(view.geometry,source_capture_id='other')),r,3)
    with pytest.raises(MeasurementError):
        PreviewMeasurementSession(replace(view,colored_point_indices=np.array([-1],dtype=np.int32)),r,3)


def test_source_content_not_mutated_after_measure(tmp_path):
    view,r=fixture(tmp_path); before=r.path.read_bytes()
    xyz=view.points_xyz_m.copy(); ids=view.colored_point_indices.copy()
    s=PreviewMeasurementSession(view,r,3)
    s.consume(pick(view,r,0)); s.consume(pick(view,r,1))
    np.testing.assert_array_equal(view.points_xyz_m,xyz)
    np.testing.assert_array_equal(view.colored_point_indices,ids)
    assert r.path.read_bytes()==before
    assert sha256(before).hexdigest()==r.ply_sha256


class FakeViewer(QObject):
    scene_inspection = Signal(object)
    point_pick_completed = Signal(object)
    def __init__(self):
        super().__init__()
        self.page=QWidget();self.page.setLayout(QVBoxLayout())
        self._descriptor=None
        self._current_source=None
        self._pending_source=None
        self._live_phase='idle'
        self._legacy_mode=False
        self._expected_scene_revision=None
        self._selected=None
        self.modes=[]
    def _set_tool_mode(self,mode):self.modes.append(mode)


def test_ui_mode_and_stale_scene_invalidation(tmp_path):
    app=QApplication.instance() or QApplication([])
    view,r=fixture(tmp_path); viewer=FakeViewer()
    panel=GeometryMeasurementPanel(viewer,viewer)
    try:
        panel.bind_preview(r,view)
        assert not panel.mode_button.isEnabled()
        viewer._current_source=r.path
        viewer._descriptor=type('D',(),{'source_sha256':r.ply_sha256,
                                       'point_count':r.colored_points,
                                       'geometry_kind':'points'})()
        viewer._expected_scene_revision=3
        viewer._live_phase='ready'
        panel._poll()
        assert panel.mode_button.isEnabled()
        panel.mode_button.setChecked(True)
        assert viewer.modes[-1]=='select'
        viewer._selected=pick(view,r,0)
        viewer.point_pick_completed.emit(viewer._selected)
        assert 'Chọn điểm B' in panel.readout.text()
        viewer._selected=pick(view,r,1)
        viewer.point_pick_completed.emit(viewer._selected)
        assert ' mm ' in panel.readout.text()
        viewer.scene_inspection.emit(None)
        assert not panel.mode_button.isEnabled()
        assert panel._session is None
    finally:
        panel.dispose()
        viewer.page.close()


def test_ui_external_scene_rejected(tmp_path):
    app=QApplication.instance() or QApplication([])
    view,r=fixture(tmp_path);viewer=FakeViewer()
    panel=GeometryMeasurementPanel(viewer,viewer)
    try:
        panel.bind_preview(r,view)
        viewer._current_source=tmp_path/'outside.ply'
        viewer._descriptor=type('D',(),{'source_sha256':'0'*64,
                                       'point_count':r.colored_points,
                                       'geometry_kind':'points'})()
        viewer._live_phase='ready';viewer._expected_scene_revision=4
        panel._poll()
        assert panel._session is None
        assert not panel.mode_button.isEnabled()
    finally:
        panel.dispose();viewer.page.close()


def test_repeat_same_point_is_valid_zero_distance_and_inspection_is_not_a_click(tmp_path):
    app = QApplication.instance() or QApplication([])
    view, receipt = fixture(tmp_path)
    viewer = FakeViewer()
    panel = GeometryMeasurementPanel(viewer, viewer)
    try:
        panel.bind_preview(receipt, view)
        viewer._current_source = receipt.path
        viewer._descriptor = type('D', (), {
            'source_sha256': receipt.ply_sha256,
            'point_count': receipt.colored_points,
            'geometry_kind': 'points',
        })()
        viewer._expected_scene_revision = 3
        viewer._live_phase = 'ready'
        panel._poll()
        assert panel.mode_button.isEnabled()
        panel.mode_button.setChecked(True)
        same = pick(view, receipt, 0)
        viewer._selected = same
        viewer.point_pick_completed.emit(same)
        assert 'Chọn điểm B' in panel.readout.text()
        # A passive inspector refresh must not consume B.
        viewer.scene_inspection.emit({'kind': 'LỰA CHỌN HÌNH HỌC'})
        assert 'Chọn điểm B' in panel.readout.text()
        viewer.point_pick_completed.emit(None)
        assert 'Không bắt trúng điểm B' in panel.readout.text()
        assert panel._session.first is not None
        # The second *fresh* click may resolve to the same PLY point ID.
        viewer.point_pick_completed.emit(same)
        assert '0.000000 m' in panel.readout.text()
        assert '0.000 mm' in panel.readout.text()
        assert panel._session.last is not None
        # Third click starts a new pair, as in the 10.06 contract.
        viewer._selected = pick(view, receipt, 1)
        viewer.point_pick_completed.emit(viewer._selected)
        assert 'Chọn điểm B' in panel.readout.text()
    finally:
        panel.dispose()
        viewer.page.close()


def test_external_scene_signal_blocks_pick_consumption(tmp_path):
    app = QApplication.instance() or QApplication([])
    view, receipt = fixture(tmp_path)
    viewer = FakeViewer()
    panel = GeometryMeasurementPanel(viewer, viewer)
    try:
        panel.bind_preview(receipt, view)
        viewer._current_source = receipt.path
        viewer._descriptor = type('D', (), {
            'source_sha256': receipt.ply_sha256,
            'point_count': receipt.colored_points,
            'geometry_kind': 'points',
        })()
        viewer._expected_scene_revision = 3
        viewer._live_phase = 'ready'
        panel._poll()
        panel.mode_button.setChecked(True)
        viewer._selected = pick(view, receipt, 0)
        viewer.point_pick_completed.emit(viewer._selected)
        assert panel._session.first is not None
        viewer.scene_inspection.emit(None)
        assert panel._session is None
        viewer.point_pick_completed.emit(viewer._selected)
        assert panel._session is None
    finally:
        panel.dispose()
        viewer.page.close()
