"""Qt presentation controller for live 3D tools and source-backed selections.

Inherits the live controller; native VTK stays in an isolated subprocess.
Only results for the active source and scene may reach the Inspector;
displayed coordinates are not independently verified metric measurements.
"""
from __future__ import annotations

from concurrent.futures import Future
from pathlib import Path

from PySide6.QtCore import QEvent, Signal, Qt

from PySide6.QtGui import QShortcut, QKeySequence
from PySide6.QtWidgets import QLabel

from ..application.scene_contracts import SceneSelectionRef
from .live_controller import LiveViewer3DController
from .live_tools import LiveViewerTools


class InteractiveViewer3DController(LiveViewer3DController):
    scene_inspection = Signal(object)

    def __init__(self, parent, *, session_factory):
        super().__init__(parent, session_factory=session_factory)
        self.page.findChild(QLabel,'viewer3dTitle').setText('Kiểm tra mô hình 3D')
        self._pick_future: Future | None = None
        self._layer_future: Future | None = None
        self._grid_future: Future | None = None
        self._grid_enabled = True
        self._grid_mode = 'xy'
        self._selected: SceneSelectionRef | None = None
        self._inspected_scene = None
        self._visible_geometry = True
        self._tool_mode = 'orbit'
        self.tools = LiveViewerTools(self.page.surface)
        self.tools.mode_changed.connect(self._set_tool_mode)
        self.tools.camera_action.connect(self._handle_toolbar_camera)
        self.tools.layer_changed.connect(self._change_layer)
        self.tools.grid_changed.connect(self._change_grid)
        self._install_keyboard_shortcuts()
        self.page.surface.installEventFilter(self)
        self.tools.move(8, 8)
        self.tools.raise_()
        # Keep old objectNames for compatibility, but remove duplicate controls.
        nav = self.page.layout().itemAt(1).layout()
        for index in range(nav.count()):
            widget = nav.itemAt(index).widget()
            if widget is not None:
                widget.hide()
        self.page.layer_label.hide()
        self.page.point_inspector.hide()
        self.page.note.setStyleSheet('font-size: 12px; color: #64748b;')
        self._ready_tools()

    def _handle_toolbar_camera(self, action: str) -> None:
        if action == "zoom_in":
            self.navigate("zoom", 1.0, 0.0)
        elif action == "zoom_out":
            self.navigate("zoom", -1.0, 0.0)
        else:
            self.navigate(action, 0.0, 0.0)
    def _install_keyboard_shortcuts(self):
        shortcuts = (
            ('S', lambda: self._set_tool_mode('select')),
            ('R', lambda: self._set_tool_mode('orbit')),
            ('P', lambda: self._set_tool_mode('pan')),
            ('F', lambda: self.navigate('reset',0,0)),
            ('G', lambda: self.tools.grid_button.toggle()),
            ('L', lambda: self.tools.layer_button.toggle()),
            ('+', lambda: self.navigate('zoom',1,0)),
            ('-', lambda: self.navigate('zoom',-1,0)),
            ('Escape', self._clear_selection),
        )
        self._shortcuts = []
        for key, func in shortcuts:
            shortcut = QShortcut(QKeySequence(key),self.page)
            shortcut.setContext(Qt.WidgetWithChildrenShortcut)
            shortcut.activated.connect(func)
            self._shortcuts.append(shortcut)

    def _clear_selection(self):
        self.page.preview.cancel_drag()
        self._selected = None
        self._emit_scene()
        self.page.set_status('Đã bỏ lựa chọn hình học.')

    def eventFilter(self, watched, event):
        if watched is self.page.surface and event.type() in (QEvent.Resize, QEvent.Show):
            self.tools.move(8, 8)
            self.tools.raise_()
        return super().eventFilter(watched, event)

    def _ready_tools(self):
        self.page.preview.interaction_mode = self._tool_mode
        available = self._live_phase == 'ready' and self._last_frame_revision >= 0 and not self._legacy_mode
        self.tools.setEnabled(available)
        self.page.preview.set_pick_enabled(
            available and self._visible_geometry and self._tool_mode == 'select')

    def _set_tool_mode(self, mode: str):
        if mode not in ('select', 'orbit', 'pan'):
            return
        self._tool_mode = mode
        self.page.preview.cancel_drag()
        self.tools.set_mode(mode)
        self._ready_tools()

    def _emit_scene(self):
        if self._descriptor is None:
            self.scene_inspection.emit(None)
            return
        d = self._descriptor
        bounds = d.bounds
        fields = (
            ('Tệp nguồn', d.name),
            ('Định dạng', d.source_format.upper()),
            ('Loại hình học', 'Lưới bề mặt' if d.geometry_kind == 'mesh' else 'Đám mây điểm'),
            ('Số đỉnh', f'{d.point_count:,}'),
            ('Số mặt', f'{d.face_count:,}'),
            ('X nhỏ nhất', format(bounds[0], '.12g')),
            ('X lớn nhất', format(bounds[1], '.12g')),
            ('Y nhỏ nhất', format(bounds[2], '.12g')),
            ('Y lớn nhất', format(bounds[3], '.12g')),
            ('Z nhỏ nhất', format(bounds[4], '.12g')),
            ('Z lớn nhất', format(bounds[5], '.12g')),
            ('Màu RGB', 'Có' if d.has_rgb else 'Không'),
            ('SHA-256 nguồn', d.source_sha256),
            ('Đơn vị', 'Chưa xác nhận'),
            ('Hệ tọa độ', 'Chưa xác nhận'),
        )
        if self._selected is None:
            self.scene_inspection.emit({
                'kind': 'MÔ HÌNH 3D', 'title': d.name, 'fields': fields,
                'note': 'Dữ liệu từ tệp ngoài; không đồng nhất với metadata dự án SQLite.',
                'copy_xyz': None})
            return
        s = self._selected
        picking = (
            ('Đối tượng đã chọn', 'Mặt' if s.kind == 'face' else 'Điểm'),
            ('Mã phần tử', str(s.element_id)),
            ('X', format(s.xyz[0], '.12g')),
            ('Y', format(s.xyz[1], '.12g')),
            ('Z', format(s.xyz[2], '.12g')),
            ('Phiên cảnh', str(s.scene_revision)),
        )
        self.scene_inspection.emit({
            'kind': 'LỰA CHỌN HÌNH HỌC', 'title': d.name, 'fields': picking + fields,
            'note': ('XYZ là tọa độ giao điểm trên mặt.' if s.kind == 'face' else
                     'XYZ là tọa độ điểm đã chọn.') +
                    ' Không có xác nhận đơn vị đo hoặc hiệu chuẩn.',
            'copy_xyz': ', '.join(repr(v) for v in s.xyz)})

    def load_ply(self, filename: str | Path) -> bool:
        self._pick_future = self._layer_future = self._grid_future = None
        self._selected = None
        self._inspected_scene = None
        self._visible_geometry = True
        self._grid_enabled = True
        self._grid_mode = 'xy'
        self.tools.reset_layer()
        self.scene_inspection.emit(None)
        ok = super().load_ply(filename)
        self._ready_tools()
        return ok

    def _poll_live(self):
        super()._poll_live()
        if self._closing or self._disposed or self._legacy_mode:
            return
        token = (self._expected_scene_revision, self._descriptor.source_sha256) if self._descriptor else None
        if self._live_phase == 'ready' and token != self._inspected_scene:
            self._inspected_scene = token
            self._selected = None
            self._emit_scene()
        self._poll_selection()
        self._poll_visibility()
        self._poll_grid()
        self._ready_tools()

    def _drain_newest_frame(self):
        super()._drain_newest_frame()
        self._ready_tools()

    def pick_point(self, u: float, v: float) -> bool:
        if self._legacy_mode:
            return super().pick_point(u, v)
        if (self._closing or self._live_phase != 'ready' or not self._visible_geometry or
                self._pick_future is not None or self._live_session is None or
                self._last_frame_revision < 0):
            return False
        try:
            self._pick_future = self._live_session.pick(
                u, v, self._expected_scene_revision, self._last_frame_revision)
            self.page.set_status('Đang xác định điểm hoặc mặt được chọn…')
            return True
        except (ValueError, RuntimeError):
            self.page.set_status('Góc nhìn đang thay đổi. Hãy thử chọn lại khi hình ổn định.')
            return False

    def _poll_selection(self):
        future = self._pick_future
        if future is None or not future.done():
            return
        self._pick_future = None
        try:
            result = future.result()
            d = self._descriptor
            if (d is None or self._live_phase != 'ready' or
                    result['scene_revision'] != self._expected_scene_revision or
                    result['frame_revision'] != self._last_frame_revision or
                    result['source_sha256'] != d.source_sha256 or
                    result['geometry_kind'] != d.geometry_kind):
                return
            if not result['hit']:
                self._selected = None
                self.page.set_status('Không có điểm hoặc mặt tại vị trí đã chọn.')
            else:
                kind = result['kind']
                idx = result['element_id']
                limit = d.point_count if kind == 'point' else d.face_count
                if (kind != ('face' if d.geometry_kind == 'mesh' else 'point') or
                        type(idx) is not int or not 0 <= idx < limit):
                    raise ValueError('INVALID_PICK_ELEMENT')
                self._selected = SceneSelectionRef(
                    d.source_sha256, self._expected_scene_revision, kind, idx,
                    tuple(result['xyz']))
                self.page.set_status('Đã chọn ' + ('mặt' if kind == 'face' else 'điểm') +
                                     f' số {idx}. Xem thông tin trong bảng Thuộc tính.')
            self._emit_scene()
        except (ValueError, KeyError, TypeError, RuntimeError):
            self._selected = None
            self._emit_scene()
            self.page.set_status('Không thể xác định hình học tại vị trí nhấn.', is_error=True)

    def navigate(self, action: str, dx: float = 0.0, dy: float = 0.0) -> bool:
        result = super().navigate(action, dx, dy)
        if result and not self._legacy_mode:
            self._selected = None
            self._emit_scene()
        return result

    def _change_layer(self, visible: bool):
        if self._legacy_mode or self._live_phase != 'ready' or self._layer_future is not None:
            self.tools.set_layer(self._visible_geometry)
            return
        try:
            self._layer_future = self._live_session.set_visibility(visible)
            self._visible_geometry = visible
            self._selected = None
            self._emit_scene()
        except (ValueError, RuntimeError):
            self.page.set_status('Không thể thay đổi hiển thị lớp hình học.', is_error=True)
        self._ready_tools()

    def _change_grid(self, enabled: bool, mode: str):
        if (self._legacy_mode or self._live_phase != 'ready' or
                self._grid_future is not None or self._live_session is None):
            self.tools.set_grid(self._grid_enabled, self._grid_mode)
            return
        try:
            self._grid_future = self._live_session.set_grid(enabled,mode)
            self._grid_enabled, self._grid_mode = enabled,mode
        except (ValueError, RuntimeError):
            self.tools.set_grid(self._grid_enabled,self._grid_mode)
            self.page.set_status('Không thể đổi lưới tham chiếu.',is_error=True)

    def _poll_grid(self):
        future = self._grid_future
        if future is None or not future.done():
            return
        self._grid_future = None
        try:
            result = future.result()
            if (result.get('grid_enabled') != self._grid_enabled or
                    result.get('grid_mode') != self._grid_mode):
                raise ValueError('GRID_STATE_MISMATCH')
        except (ValueError,RuntimeError):
            self._show_live_failure('Lưới tham chiếu không cập nhật. Hãy chọn Thử lại.')

    def _poll_visibility(self):
        future = self._layer_future
        if future is None or not future.done():
            return
        self._layer_future = None
        try:
            future.result()
        except (ValueError, RuntimeError):
            self.page.set_status('Không thể thay đổi lớp hình học. Chọn Thử lại.', is_error=True)
            self._show_live_failure('Bộ hiển thị không phản hồi khi thay đổi lớp. Chọn Thử lại.')

    def _show_live_failure(self, message: str):
        self._pick_future = self._layer_future = self._grid_future = None
        self._selected = None
        self._inspected_scene = None
        self.scene_inspection.emit(None)
        super()._show_live_failure(message)

    def _select_fallback(self, enabled: bool):
        self._pick_future = self._layer_future = self._grid_future = None
        self._selected = None
        self._inspected_scene = None
        self.scene_inspection.emit(None)
        super()._select_fallback(enabled)
        self.tools.setVisible(not enabled)
        self.page.point_inspector.setVisible(enabled)
        self.page.layer_label.setVisible(enabled)
        # PNG fallback must retain its original accessible navigation controls.
        nav = self.page.layout().itemAt(1).layout()
        for index in range(nav.count()):
            widget = nav.itemAt(index).widget()
            if widget is not None:
                widget.setVisible(enabled)
        self._ready_tools()

    def begin_shutdown(self) -> bool:
        self.scene_inspection.emit(None)
        return super().begin_shutdown()
