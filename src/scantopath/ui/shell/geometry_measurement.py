"""GD2-10.08.2: source-backed two-point measurement in Capture Geometry Preview.

Qt presentation owns no VTK/RAW/SQL clients. A temporary PLY is only the
visual transport. Its point IDs are mapped to the original ValidGeometry rows;
its float32 coordinates are never used as authoritative measurement inputs.
"""
from __future__ import annotations

from math import isfinite

import numpy as np
from PySide6.QtCore import QObject, QTimer, Qt, Slot
from PySide6.QtWidgets import QFrame, QHBoxLayout, QLabel, QPushButton

from scantopath.modules.geometry.application.measurements import (
    MeasurementError, MeasurementResult, PointSelection,
    select_measurement_point, measure_selected_points,
)
from scantopath.modules.geometry.application.service import SingleViewXYZRGB
from scantopath.modules.viewer3d.application.scene_contracts import SceneSelectionRef


class PreviewMeasurementSession:
    """A validated point-ID bridge bound to exactly one rendered scene revision."""

    def __init__(self, view: SingleViewXYZRGB, receipt, scene_revision: int):
        if (not isinstance(view, SingleViewXYZRGB) or
                view.frame != 'depth_optical' or view.units != 'm' or
                view.metric_validated or
                type(scene_revision) is not int or scene_revision < 1 or
                view.source_capture_id != receipt.capture_id or
                type(receipt.ply_sha256) is not str or len(receipt.ply_sha256) != 64 or
                type(receipt.colored_points) is not int or
                receipt.colored_points != len(view.colored_point_indices) or
                not isinstance(view.colored_point_indices, np.ndarray) or
                view.colored_point_indices.dtype != np.int32 or
                view.colored_point_indices.ndim != 1 or
                receipt.xyz_points != len(view.points_xyz_m)):
            raise MeasurementError('PREVIEW_MAPPING_INVALID', 'Invalid preview Geometry identity')
        indices = view.colored_point_indices
        if (len(indices) == 0 or np.any(indices < 0) or
                np.any(indices >= len(view.points_xyz_m)) or
                len(np.unique(indices)) != len(indices)):
            raise MeasurementError('PREVIEW_MAPPING_INVALID', 'Invalid RGB-to-XYZ index mapping')
        self._view = view
        self._indices = indices.copy()
        self._indices.setflags(write=False)
        self.capture_id = receipt.capture_id
        self.preview_sha256 = receipt.ply_sha256
        self.scene_revision = scene_revision
        self.first: PointSelection | None = None
        self.last: MeasurementResult | None = None

    def clear(self) -> None:
        self.first = None
        self.last = None

    def consume(self, picked: SceneSelectionRef) -> MeasurementResult | None:
        """Reject forged/stale/mixed scene picks, then use GD2-10.06 precisely."""
        if (not isinstance(picked, SceneSelectionRef) or
                picked.kind != 'point' or
                picked.source_sha256 != self.preview_sha256 or
                picked.scene_revision != self.scene_revision or
                type(picked.element_id) is not int or
                not 0 <= picked.element_id < len(self._indices) or
                picked.units != 'unknown' or
                picked.coordinate_frame != 'unknown'):
            raise MeasurementError('PREVIEW_SCENE_MISMATCH', 'Not the bound RAW point scene')
        source_index = int(self._indices[picked.element_id])
        real_xyz = self._view.points_xyz_m[source_index]
        # VTK reads 32-bit coordinates from the temporary PLY. Cross-check the
        # selected point against the expected rounded XYZ, but do NOT measure it.
        expected = np.asarray(real_xyz, dtype=np.float32).astype(np.float64)
        supplied = np.asarray(picked.xyz, dtype=np.float64)
        if (not np.isfinite(supplied).all() or
                not np.allclose(supplied, expected, rtol=1e-6, atol=2e-6)):
            raise MeasurementError('PREVIEW_PICK_COORDINATE_MISMATCH', 'PLY point is not the mapped XYZ')
        selected = select_measurement_point(self._view.geometry, source_index)
        if selected.source_capture_id != self.capture_id:
            raise MeasurementError('PREVIEW_CAPTURE_MISMATCH', 'Capture identity changed')
        if self.last is not None:
            self.clear()  # Third click begins a new A/B pair.
        if self.first is None:
            self.first = selected
            return None
        result = measure_selected_points(self.first, selected)
        self.last = result
        return result


class GeometryMeasurementPanel(QObject):
    """Opt-in UI; only the verified active RAW Preview enables two-point mode."""

    def __init__(self, viewer, parent: QObject):
        super().__init__(parent)
        self.viewer = viewer
        self._view: SingleViewXYZRGB | None = None
        self._receipt = None
        self._session: PreviewMeasurementSession | None = None
        self._seen_pick = None
        self._pending_uv = None
        self._pick_echo_to_ignore = None
        self._anchors = []
        self._frame_revision = None
        self._closing = False

        self.panel = QFrame(viewer.page)
        self.panel.setObjectName('gd2GeometryMeasurementPanel')
        layout = QHBoxLayout(self.panel)
        layout.setContentsMargins(8, 5, 8, 5)
        layout.setSpacing(8)
        self.mode_button = QPushButton('Đo 2 điểm', self.panel)
        self.mode_button.setObjectName('gd2MeasureTwoPointsButton')
        self.mode_button.setCheckable(True)
        self.mode_button.setEnabled(False)
        self.clear_button = QPushButton('Xóa phép đo', self.panel)
        self.clear_button.setObjectName('gd2MeasureClearButton')
        self.clear_button.setEnabled(False)
        self.readout = QLabel('Chưa mở RAW Geometry Preview để đo.', self.panel)
        self.readout.setObjectName('gd2MeasurementReadout')
        self.readout.setTextFormat(Qt.PlainText)
        self.readout.setWordWrap(True)
        layout.addWidget(self.mode_button)
        layout.addWidget(self.clear_button)
        layout.addWidget(self.readout, 1)
        viewer.page.layout().insertWidget(2, self.panel)
        self.mode_button.toggled.connect(self._toggle)
        self.clear_button.clicked.connect(self.reset_pair)
        viewer.scene_inspection.connect(self._scene_changed)
        viewer.point_pick_completed.connect(self._picked)
        if hasattr(viewer.page, 'point_requested'):
            viewer.page.point_requested.connect(self._point_requested)
        preview = getattr(viewer.page, 'preview', None)
        if preview is not None and hasattr(preview, 'selection_drag_ignored'):
            preview.selection_drag_ignored.connect(self._drag_ignored)
        self._timer = QTimer(self)
        self._timer.setInterval(200)
        self._timer.timeout.connect(self._poll)
        self._timer.start()

    def bind_preview(self, receipt, view: SingleViewXYZRGB) -> None:
        self.unbind()
        if view.source_capture_id != receipt.capture_id:
            raise MeasurementError('PREVIEW_CAPTURE_MISMATCH', 'Capture ID differs')
        self._view = view
        self._receipt = receipt
        self.readout.setText('Đang tải Preview. Chỉ đo khi VTK xác nhận đúng SHA-256 và phiên cảnh.')
        self._poll()

    def unbind(self) -> None:
        was_measuring = self.mode_button.isChecked()
        self._session = None
        self._view = None
        self._receipt = None
        self._seen_pick = None
        self._pending_uv = None
        self._pick_echo_to_ignore = None
        self._frame_revision = None
        self._clear_anchors()
        self.mode_button.blockSignals(True)
        self.mode_button.setChecked(False)
        self.mode_button.setEnabled(False)
        self.mode_button.blockSignals(False)
        if was_measuring and hasattr(self.viewer, '_set_tool_mode'):
            self.viewer._set_tool_mode('orbit')
        self.clear_button.setEnabled(False)
        self.readout.setText('Không có RAW Geometry Preview hợp lệ để đo.')

    def reset_pair(self) -> None:
        if self._session is not None:
            self._session.clear()
        self._seen_pick = None
        self._pending_uv = None
        self._pick_echo_to_ignore = None
        self._clear_anchors()
        self.clear_button.setEnabled(False)
        if self._session is not None:
            self.readout.setText('Chọn điểm A rồi B · PROVISIONAL_NOT_METRIC_VALIDATED')

    def _matches_viewer(self) -> bool:
        r = self._receipt
        d = getattr(self.viewer, '_descriptor', None)
        return (not self._closing and r is not None and self._view is not None and
                getattr(self.viewer, '_live_phase', None) == 'ready' and
                getattr(self.viewer, '_pending_source', None) is None and
                getattr(self.viewer, '_current_source', None) == r.path and
                getattr(d, 'source_sha256', None) == r.ply_sha256 and
                getattr(d, 'point_count', None) == r.colored_points and
                getattr(d, 'geometry_kind', None) == 'points' and
                getattr(self.viewer, '_expected_scene_revision', None) is not None and
                not getattr(self.viewer, '_legacy_mode', False))

    @Slot()
    def _poll(self) -> None:
        if self._closing:
            return
        if self._receipt is None:
            return
        if not self._matches_viewer():
            pending = getattr(self.viewer, '_pending_source', None)
            if pending == self._receipt.path:
                return
            # The renderer is switching/replaced. Never keep a stale A/B pair.
            phase = getattr(self.viewer, '_live_phase', None)
            # A just-bound preview may not yet have entered the Render Host
            # loading phase. Do not discard its Capture while the first scene
            # is still idle; later source mismatches must still fail closed.
            if (phase == 'idle' and self._session is None and
                    getattr(self.viewer, '_current_source', None) is None):
                return
            if phase not in ('starting', 'loading'):
                self.unbind()
            return
        revision = getattr(self.viewer, '_expected_scene_revision', None)
        if self._session is None or self._session.scene_revision != revision:
            try:
                self._session = PreviewMeasurementSession(self._view, self._receipt, revision)
            except MeasurementError:
                self.unbind()
                return
            self._seen_pick = None
            self._frame_revision = getattr(self.viewer, '_last_frame_revision', None)
            self.mode_button.setEnabled(True)
            self.readout.setText('Bấm Đo 2 điểm → nhấp ngắn vào A → nhấp ngắn vào B. Chưa kiểm định.')
        # A camera move changes the projected pixel coordinates. Never show
        # annotations at stale screen positions after a new rendered frame.
        frame = getattr(self.viewer, '_last_frame_revision', None)
        if isinstance(frame, int) and frame >= 0:
            if self._frame_revision is None:
                self._frame_revision = frame
            elif frame != self._frame_revision:
                self._frame_revision = frame
                if self._anchors:
                    self.reset_pair()
                    self.readout.setText(
                        'Góc nhìn đã thay đổi: xóa neo màn hình cũ. Nhấp A rồi B để đo lại.'
                    )

    @Slot(bool)
    def _toggle(self, enabled: bool) -> None:
        if self._session is None or not self._matches_viewer():
            self.mode_button.blockSignals(True)
            self.mode_button.setChecked(False)
            self.mode_button.blockSignals(False)
            return
        self.reset_pair()
        if enabled:
            self.viewer._set_tool_mode('select')
            self.readout.setText('BƯỚC 1/2: Nhấp ngắn vào điểm A trên mô hình. Sẽ xuất hiện neo vàng A.')
        else:
            self.viewer._set_tool_mode('orbit')
            self.readout.setText('Đã tắt đo. Bật lại để chọn A và B.')

    @Slot(object)
    def _scene_changed(self, payload) -> None:
        if self._closing or self._receipt is None:
            return
        if payload is None:
            # An external load resets the scene before its new source is ready.
            if getattr(self.viewer, '_pending_source', None) != self._receipt.path:
                self.unbind()
            return
        if not self._matches_viewer():
            self._poll()
            return
        # The inspector signal is emitted from a native pick *before* the
        # point_pick_completed signal. A fresh mouse intent is the single-shot
        # token, so general Inspector refreshes never count as new picks.
        # This fallback closes the gap when Qt shows a new selected point but
        # the completion signal is lost or filtered.
        if (self._pending_uv is not None and self._session is not None
                and self.mode_button.isChecked()
                and isinstance(payload, dict)
                and payload.get('kind') == 'LỰA CHỌN HÌNH HỌC'):
            selected = getattr(self.viewer, '_selected', None)
            if isinstance(selected, SceneSelectionRef):
                self._picked(selected)
                # The native controller normally emits a second notification
                # for the same pick. Suppress that echo, not a later click.
                self._pick_echo_to_ignore = selected

    @Slot(object)
    def _picked(self, picked) -> None:
        """Consume one new native pick; deduplicate the optional event echo."""
        if self._pick_echo_to_ignore is not None:
            echo = self._pick_echo_to_ignore
            self._pick_echo_to_ignore = None
            if picked == echo:
                return
        if (self._closing or self._session is None or
                not self.mode_button.isChecked() or not self._matches_viewer()):
            return
        if picked is None:
            self._pending_uv = None
            target = 'B' if self._session.first is not None else 'A'
            self.readout.setText(
                f'Không bắt trúng điểm {target}. Hãy nhấp ngắn vào vùng có điểm màu; '
                'không kéo chuột. Lựa chọn trước đó được giữ nguyên.'
            )
            return
        if (not isinstance(picked, SceneSelectionRef) or
                picked != getattr(self.viewer, '_selected', None)):
            return
        uv = self._pending_uv
        self._pending_uv = None
        try:
            result = self._session.consume(picked)
        except MeasurementError as exc:
            self.reset_pair()
            self.readout.setText('Không chấp nhận điểm chọn: ' + exc.code)
            return
        self.clear_button.setEnabled(True)
        if result is None:
            self._anchors = [('A', uv)] if uv is not None else []
            self._show_anchors()
            a = self._session.first
            self.readout.setText(
                f'BƯỚC 2/2: ĐÃ NEO A (XYZ #{a.point_index}). '
                'Chọn điểm B bằng một cú nhấp ngắn; sẽ hiện neo B và đường nối. '
                'PROVISIONAL_NOT_METRIC_VALIDATED'
            )
        else:
            if uv is not None and self._anchors:
                self._anchors = [self._anchors[0], ('B', uv)]
            self._show_anchors()
            self.readout.setText(
                f'ĐÃ ĐO A–B: {result.distance_m:.6f} m = {result.distance_mm:.3f} mm · '
                f'XYZ {result.point_indices} · PROVISIONAL_NOT_METRIC_VALIDATED. '
                'Xóa phép đo để chọn lại.'
            )


    def _clear_anchors(self) -> None:
        self._anchors = []
        preview = getattr(self.viewer.page, 'preview', None)
        if preview is not None and hasattr(preview, 'set_measurement_anchors'):
            preview.set_measurement_anchors([])

    def _show_anchors(self) -> None:
        preview = getattr(self.viewer.page, 'preview', None)
        if preview is not None and hasattr(preview, 'set_measurement_anchors'):
            preview.set_measurement_anchors(self._anchors)

    @Slot(float, float)
    def _point_requested(self, u: float, v: float) -> None:
        """Remember where the user clicked; paint only after VTK confirms a hit."""
        if (self._session is None or not self.mode_button.isChecked() or
                not self._matches_viewer()):
            return
        if (isfinite(u) and isfinite(v) and 0 <= u <= 1 and 0 <= v <= 1):
            # A new click is a new event even when VTK returns the same ID.
            self._pick_echo_to_ignore = None
            self._pending_uv = (float(u), float(v))
            target = 'B' if self._session.first is not None and self._session.last is None else 'A'
            self.readout.setText(f'Đang xác định điểm {target} từ Viewer…')

    @Slot()
    def _drag_ignored(self) -> None:
        if (self._session is None or not self.mode_button.isChecked() or
                not self._matches_viewer()):
            return
        self._pending_uv = None
        target = 'B' if self._session.first is not None and self._session.last is None else 'A'
        self.readout.setText(
            f'Chưa chọn {target}: chuột đã bị kéo hơn 6 px. '
            'Hãy nhấp và thả nhanh, không kéo. Neo trước được giữ nguyên.'
        )

    def dispose(self) -> None:
        self._closing = True
        self._timer.stop()
        self.unbind()
