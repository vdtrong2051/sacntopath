"""GD2-10.08.2 regression: Inspector receives B but measuring panel does not."""
from __future__ import annotations

import pytest
from PySide6.QtWidgets import QApplication

from scantopath.ui.shell.geometry_measurement import GeometryMeasurementPanel
from tests.unit.geometry.test_gd2_10_08_2_anchor_visual import prepare
from tests.unit.geometry.test_gd2_10_08_2_measurement_ui import pick


@pytest.fixture
def qt_app():
    return QApplication.instance() or QApplication([])


def deliver_click(viewer, view, receipt, idx, u, v, *, echo):
    """Mimic Qt click, then native pick -> Inspector, then optional pick signal."""
    viewer.page.point_requested.emit(u, v)
    selection = pick(view, receipt, idx)
    viewer._selected = selection
    viewer.scene_inspection.emit({'kind': 'LỰA CHỌN HÌNH HỌC'})
    if echo:
        viewer.point_pick_completed.emit(selection)
    return selection


@pytest.mark.parametrize('echo', [False, True])
def test_second_click_on_another_point_completes_AB(qt_app, tmp_path, echo):
    view, receipt, viewer, panel = prepare(tmp_path, qt_app)
    try:
        deliver_click(viewer, view, receipt, 0, .3, .4, echo=echo)
        assert panel._session.first is not None
        assert panel._session.last is None
        assert 'NEO A' in panel.readout.text()
        deliver_click(viewer, view, receipt, 1, .6, .7, echo=echo)
        assert panel._session.last is not None
        assert len(panel._anchors) == 2
        assert 'ĐÃ ĐO' in panel.readout.text()
        assert ' mm' in panel.readout.text()
    finally:
        panel.dispose()
        viewer.page.close()


def test_same_point_twice_counts_as_two_distinct_clicks(qt_app, tmp_path):
    view, receipt, viewer, panel = prepare(tmp_path, qt_app)
    try:
        deliver_click(viewer, view, receipt, 0, .4, .5, echo=True)
        assert panel._session.last is None
        deliver_click(viewer, view, receipt, 0, .4, .5, echo=True)
        assert panel._session.last.distance_mm == 0.0
        assert len(panel._anchors) == 2
    finally:
        panel.dispose()
        viewer.page.close()


def test_unprompted_inspection_refresh_does_not_create_B(qt_app, tmp_path):
    view, receipt, viewer, panel = prepare(tmp_path, qt_app)
    try:
        deliver_click(viewer, view, receipt, 0, .4, .5, echo=True)
        viewer.scene_inspection.emit({'kind': 'LỰA CHỌN HÌNH HỌC'})
        viewer.scene_inspection.emit({'kind': 'MÔ HÌNH 3D'})
        assert panel._session.last is None
        assert len(panel._anchors) == 1
    finally:
        panel.dispose()
        viewer.page.close()


def test_mismatched_scene_does_not_accept_B(qt_app, tmp_path):
    view, receipt, viewer, panel = prepare(tmp_path, qt_app)
    try:
        deliver_click(viewer, view, receipt, 0, .4, .5, echo=True)
        viewer._descriptor.source_sha256 = '0'*64
        viewer.page.point_requested.emit(.6,.7)
        viewer._selected = pick(view, receipt, 1)
        viewer.scene_inspection.emit({'kind': 'LỰA CHỌN HÌNH HỌC'})
        assert panel._session is None or panel._session.last is None
    finally:
        panel.dispose()
        viewer.page.close()
