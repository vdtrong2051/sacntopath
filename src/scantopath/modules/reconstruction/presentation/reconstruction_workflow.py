"""FT-11 Qt orchestration. Reuses FT09/FT10 scripts and the existing VTK viewer.

No second camera, renderer, object store or SQLite selection authority. All
heavy work is performed by bounded QProcess children outside the GUI thread.
"""
from __future__ import annotations

import json
from pathlib import Path
import sys
from datetime import datetime, timezone

from PySide6.QtCore import QObject, QProcess, QSettings, QTimer, Qt, Signal
from PySide6.QtWidgets import (
    QAbstractItemView, QFileDialog, QFrame, QHBoxLayout, QLabel, QListWidget,
    QMessageBox, QPushButton, QTabWidget, QTreeWidget, QTreeWidgetItem,
    QVBoxLayout, QWidget, QDialog, QDialogButtonBox, QFormLayout, QDoubleSpinBox,
    QLineEdit, QCheckBox, QComboBox,
)

from scantopath.application.contracts import WorkspaceId


class ReconstructionPanel(QFrame):
    process_requested = Signal()
    view_requested = Signal()
    mode_requested = Signal()
    export_requested = Signal()
    reopen_requested = Signal()
    pose_selected = Signal(int)
    history_requested = Signal(str)
    c1_requested = Signal()
    reference_requested = Signal()
    c2_requested = Signal()
    c2_open_requested = Signal()
    c2_source_requested = Signal()
    c2_view_requested = Signal(str)
    session_raw_requested = Signal()
    session_result_requested = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName('ft11ReconstructionPanel')
        root = QVBoxLayout(self)
        # FT-11 R2: compact desktop density; do not create nested scroll panels.
        root.setContentsMargins(12, 9, 12, 9)
        root.setSpacing(8)

        head = QHBoxLayout()
        title = QLabel('TÁI TẠO 3D · ĐA GÓC', self)
        title.setObjectName('ft11Heading')
        head.addWidget(title, 1)
        self.open_source = QPushButton('Mở chuỗi đã thu…', self)
        self.open_source.setObjectName('ft11OpenSequence')
        self.open_source.clicked.connect(self.process_requested.emit)
        head.addWidget(self.open_source)
        root.addLayout(head)

        self.phase = QLabel('Sẵn sàng · Thu chuỗi từ tab Thu nhận hoặc mở một chuỗi FT-09.', self)
        self.phase.setObjectName('ft11Phase')
        self.phase.setWordWrap(True)
        root.addWidget(self.phase)

        metrics = QHBoxLayout()
        self.frames = QLabel('Frame: —', self)
        self.poses = QLabel('Pose: —', self)
        self.points = QLabel('Điểm XYZ: —', self)
        for metric in (self.frames, self.poses, self.points):
            metric.setObjectName('ft11Metric')
            metrics.addWidget(metric, 1)
        root.addLayout(metrics)

        actions = QHBoxLayout()
        self.view_button = QPushButton('Xem mô hình 3D', self)
        self.view_button.setObjectName('ft11View')
        self.view_button.clicked.connect(self.view_requested.emit)
        self.mode_button = QPushButton('Màu theo góc', self)
        self.mode_button.setObjectName('ft11ViewMode')
        self.mode_button.clicked.connect(self.mode_requested.emit)
        self.export_button = QPushButton('Lưu phiên…', self)
        self.export_button.setObjectName('ft11Export')
        self.export_button.clicked.connect(self.export_requested.emit)
        self.reopen_button = QPushButton('Mở phiên đã lưu…', self)
        self.reopen_button.setObjectName('ft11Reopen')
        self.reopen_button.clicked.connect(self.reopen_requested.emit)
        for w in (self.view_button, self.mode_button, self.export_button, self.reopen_button):
            actions.addWidget(w)
        actions.addStretch(1)
        root.addLayout(actions)

        c1_actions = QHBoxLayout()
        self.c1_button = QPushButton('C1 · Cloud vật thể & normal', self)
        self.c1_button.setObjectName('c1RunGeometry')
        self.c1_button.setToolTip('FT-12→15: lọc cloud, normal, provenance, kiểm tra pose. Không tự chứng nhận sai số 10 mm.')
        self.c1_button.clicked.connect(self.c1_requested.emit)
        self.metric_button = QPushButton('Nhập kích thước chuẩn…', self)
        self.metric_button.setObjectName('c1MetricReference')
        self.metric_button.clicked.connect(self.reference_requested.emit)
        self.metric_button.setToolTip('Nhập chiều x/y/z thực đo để đánh giá demo gate 10 mm. Không thay hiệu chuẩn cảm biến.')
        self.c1_status = QLabel('C1: chưa chạy · sai số kích thước chưa đo.', self)
        self.c1_status.setObjectName('c1QualityState')
        c1_actions.addWidget(self.c1_button)
        c1_actions.addWidget(self.metric_button)
        c1_actions.addWidget(self.c1_status, 1)
        root.addLayout(c1_actions)

        c2_actions = QHBoxLayout()
        self.c2_button = QPushButton('C2 · Tạo mesh & đường dẫn', self)
        self.c2_button.setObjectName('c2RunSurfacePath')
        self.c2_button.setToolTip('FT-16–18: mesh chỉ dùng mặt có hỗ trợ dữ liệu đo; đường dẫn tham chiếu XYZ + normal.')
        self.c2_button.clicked.connect(self.c2_requested.emit)
        self.c2_source = QPushButton('Mở cloud C1…', self)
        self.c2_source.setObjectName('c2OpenSourceC1')
        self.c2_source.clicked.connect(self.c2_source_requested.emit)
        self.c2_open = QPushButton('Mở kết quả C2…', self)
        self.c2_open.setObjectName('c2OpenResult')
        self.c2_open.clicked.connect(self.c2_open_requested.emit)
        self.c2_mesh = QPushButton('Mesh', self)
        self.c2_mesh.setObjectName('c2ViewMesh')
        self.c2_mesh.clicked.connect(lambda: self.c2_view_requested.emit('mesh'))
        self.c2_zigzag = QPushButton('Zigzag', self)
        self.c2_zigzag.setObjectName('c2ViewZigzag')
        self.c2_zigzag.clicked.connect(lambda: self.c2_view_requested.emit('zigzag'))
        self.c2_contour = QPushButton('Contour', self)
        self.c2_contour.setObjectName('c2ViewContour')
        self.c2_contour.clicked.connect(lambda: self.c2_view_requested.emit('contour'))
        for button in (self.c2_button, self.c2_source, self.c2_open, self.c2_mesh, self.c2_zigzag, self.c2_contour):
            c2_actions.addWidget(button)
        c2_actions.addStretch(1)
        root.addLayout(c2_actions)
        session_row = QHBoxLayout()
        self.quality = QComboBox(self)
        self.quality.setObjectName('finalReconstructionDensity')
        self.quality.addItem('Mịn · voxel 2 mm', 'fine')
        self.quality.addItem('Cân bằng · voxel 4 mm', 'balanced')
        self.quality.setToolTip('Chọn trước khi mở chuỗi RAW/chạy lại. Dữ liệu đo thật không nội suy thêm điểm.')
        session_row.addWidget(self.quality)
        self.session_raw = QPushButton('RAW của phiên Project', self)
        self.session_raw.setObjectName('finalProjectRaw')
        self.session_raw.clicked.connect(self.session_raw_requested.emit)
        self.session_result = QPushButton('Mesh/Path của phiên Project', self)
        self.session_result.setObjectName('finalProjectResult')
        self.session_result.clicked.connect(self.session_result_requested.emit)
        session_row.addWidget(self.session_raw)
        session_row.addWidget(self.session_result)
        session_row.addStretch(1)
        root.addLayout(session_row)
        self.c2_status = QLabel('C2: cần cloud C1; đường dẫn chỉ là hình học, chưa điều khiển robot.', self)
        self.c2_status.setObjectName('c2SurfacePathStatus')
        self.c2_status.setWordWrap(True)
        root.addWidget(self.c2_status)

        pose_label = QLabel('POSE VÀ CHẤT LƯỢNG TRACKING', self)
        pose_label.setObjectName('ft11SectionTitle')
        root.addWidget(pose_label)
        self.pose_table = QTreeWidget(self)
        self.pose_table.setObjectName('ft11PoseTable')
        self.pose_table.setHeaderLabels(['Frame', 'Trạng thái', 'Overlap', 'RMSE (mm)', 'Nguyên nhân'])
        self.pose_table.setRootIsDecorated(False)
        self.pose_table.setAlternatingRowColors(True)
        self.pose_table.setUniformRowHeights(True)
        self.pose_table.setSelectionMode(QAbstractItemView.SingleSelection)
        self.pose_table.setMinimumHeight(185)
        self.pose_table.header().setStretchLastSection(True)
        self.pose_table.itemSelectionChanged.connect(self._pose_changed)
        root.addWidget(self.pose_table, 2)
        self.pose_empty = QLabel('Chưa có dữ liệu pose. Chọn “Mở chuỗi đã thu…” để tái tạo không cần camera.', self)
        self.pose_empty.setObjectName('ft11PoseEmpty')
        self.pose_empty.setWordWrap(True)
        root.addWidget(self.pose_empty)
        self.pose_table.hide()

        history_label = QLabel('PHIÊN ĐÃ LƯU GẦN ĐÂY', self)
        history_label.setObjectName('ft11SectionTitle')
        root.addWidget(history_label)
        self.history = QListWidget(self)
        self.history.setObjectName('ft11History')
        self.history.setMaximumHeight(105)
        self.history.itemDoubleClicked.connect(
            lambda item: self.history_requested.emit(str(item.data(Qt.UserRole))))
        root.addWidget(self.history)
        self.history_empty = QLabel('Chưa có phiên xuất. Sau khi tái tạo, chọn “Lưu phiên…” để lưu và mở lại.', self)
        self.history_empty.setObjectName('ft11HistoryEmpty')
        self.history_empty.setWordWrap(True)
        root.addWidget(self.history_empty)
        self.history.hide()
        self.note = QLabel('Cloud đo thật · Pose ước lượng · Chưa kiểm chứng độ chính xác kích thước.', self)
        self.note.setObjectName('ft11Note')
        self.note.setWordWrap(True)
        root.addWidget(self.note)
        self.set_ready(False, False)

    def set_ready(self, ready: bool, busy: bool):
        self.open_source.setEnabled(not busy)
        self.view_button.setEnabled(ready and not busy)
        self.mode_button.setEnabled(ready and not busy)
        self.export_button.setEnabled(ready and not busy)
        self.reopen_button.setEnabled(not busy)
        self.c1_button.setEnabled(ready and not busy)
        self.metric_button.setEnabled(ready and not busy)
        self.c2_button.setEnabled(getattr(self, '_has_c1', False) and not busy)
        self.c2_open.setEnabled(not busy)
        self.c2_source.setEnabled(not busy)
        for button in (self.c2_mesh, self.c2_zigzag, self.c2_contour):
            button.setEnabled(getattr(self, '_has_c2', False) and not busy)

    def set_c2_available(self, has_c1: bool, has_c2: bool):
        self._has_c1 = bool(has_c1)
        self._has_c2 = bool(has_c2)
        self.c2_button.setEnabled(self._has_c1)
        for button in (self.c2_mesh, self.c2_zigzag, self.c2_contour):
            button.setEnabled(self._has_c2)

    def _pose_changed(self):
        item = self.pose_table.currentItem()
        if item is not None:
            self.pose_selected.emit(int(item.data(0, Qt.UserRole)))

    def set_tracking(self, record: dict):
        self.pose_table.clear()
        rows = record.get('frames', [])
        # FT-09 records may use 'samples' as the source key.
        if not rows:
            rows = record.get('samples', [])
        for i, row in enumerate(rows):
            idx = row.get('sample_index', i)
            status = str(row.get('status', '?'))
            overlap = row.get('overlap')
            rmse = row.get('rmse_m')
            quality = row.get('quality') if isinstance(row.get('quality'), dict) else {}
            if overlap is None:
                overlap = quality.get('overlap')
            if rmse is None:
                rmse = quality.get('inlier_rmse_m', quality.get('rmse_m'))
            labels = [str(idx), status,
                      '—' if overlap is None else f'{100 * overlap:.1f}%',
                      '—' if rmse is None else f'{1000 * rmse:.2f}',
                      str(row.get('reject_code') or '—')]
            item = QTreeWidgetItem(self.pose_table, labels)
            item.setData(0, Qt.UserRole, int(idx))
            item.setToolTip(4, labels[4])
        has_poses = self.pose_table.topLevelItemCount() > 0
        self.pose_table.setVisible(has_poses)
        self.pose_empty.setVisible(not has_poses)
        self.frames.setText(f'Frame: {record.get("source_frame_count", "—")}')
        self.poses.setText(f'Pose: {record.get("accepted_poses", "—")}')

    def clear_tracking(self):
        self.pose_table.clear()
        self.pose_table.hide()
        self.pose_empty.show()
        self.frames.setText('Frame: —')
        self.poses.setText('Pose: —')
        self.points.setText('Điểm XYZ: —')

    def set_history(self, paths):
        self.history.clear()
        for p in paths:
            path = Path(p)
            if path.is_dir() and (path/'reconstruction.json').is_file():
                from PySide6.QtWidgets import QListWidgetItem
                item = QListWidgetItem(path.name, self.history)
                item.setData(Qt.UserRole, str(path))
                item.setToolTip(str(path))
        has_history = self.history.count() > 0
        self.history.setVisible(has_history)
        self.history_empty.setVisible(not has_history)


class ReconstructionWorkflowController(QObject):
    """One FT-11 workflow owner for Capture → FT10 → viewer / portable bundle."""
    changed = Signal(str)

    def __init__(self, view):
        super().__init__(view)
        self.view = view
        self.repo = Path(__file__).resolve().parents[5]
        self.scripts = self.repo/'scripts'
        self.settings = QSettings('ScanToPath', 'FT11Reconstruction')
        self.panel = ReconstructionPanel(view)
        self._job: QProcess | None = None
        self._kind = ''
        self._stdout = ''
        self._message: dict = {}
        self._sequence: Path | None = None
        self._cloud: Path | None = None
        self._c1: Path | None = None
        self._c2: Path | None = None
        self._c2_display = 'mesh'
        self._reference: Path | None = None
        self._bundle: Path | None = None
        self._debug = False
        self._closing = False
        self._viewer_actions_installed = False
        self._tracking: dict = {}
        self._default_output = Path.home()/'Documents'/'ScanToPath'/'Reconstruction'
        self._last_output = self._default_output
        self._project_context = None
        self._fine = True  # measured point density: 2 mm, not viewer point size
        self._attach_processing_tab()
        self._wire()
        # Context hint shares the existing Explorer; it is NOT a fake SQLite entity.
        self.explorer_context = QLabel('', self.view.project_explorer)
        self.explorer_context.setObjectName('ft11ExplorerReconstructionContext')
        self.explorer_context.setWordWrap(True)
        self.view.project_explorer.layout().insertWidget(1, self.explorer_context)
        self.explorer_context.hide()
        self._load_history()

    def _attach_processing_tab(self):
        old = self.view.project_workspace.processing_workspace.panel
        host = self.view.page_for(WorkspaceId.PROCESSING).findChild(QWidget, 'workspaceScrollContent')
        if host is None or host.layout() is None:
            raise RuntimeError('FT11_PROCESSING_WORKSPACE_MISSING')
        layout = host.layout()
        index = layout.indexOf(old)
        if index < 0:
            raise RuntimeError('FT11_SQLITE_PROCESSING_PANEL_MISSING')
        layout.removeWidget(old)
        self.tabs = QTabWidget(host)
        self.tabs.setObjectName('ft11ProcessingTabs')
        self.tabs.addTab(self.panel, 'Tái tạo đa góc')
        self.tabs.addTab(old, 'Lịch sử xử lý SQLite')
        self.tabs.setCurrentWidget(self.panel)
        layout.insertWidget(index, self.tabs, 1)

    def _wire(self):
        self.panel.process_requested.connect(self._choose_sequence)
        self.panel.view_requested.connect(self._view_current)
        self.panel.mode_requested.connect(self._toggle_mode)
        self.panel.export_requested.connect(self._choose_export)
        self.panel.reopen_requested.connect(self._choose_bundle)
        self.panel.history_requested.connect(self._verify_bundle)
        self.panel.c1_requested.connect(self._start_c1)
        self.panel.reference_requested.connect(self._enter_metric_reference)
        self.panel.c2_requested.connect(self._start_c2)
        self.panel.c2_open_requested.connect(self._choose_c2)
        self.panel.c2_source_requested.connect(self._choose_c1)
        self.panel.c2_view_requested.connect(self._view_c2)
        self.panel.session_raw_requested.connect(self._open_session_raw)
        self.panel.session_result_requested.connect(self._open_session_result)
        self.panel.pose_selected.connect(self._show_pose)
        self.view.live_3d.sequence_completed.connect(self._sequence_complete)
        self.view.live_3d.sequence_processing_started.connect(self._tracking_started)

    @property
    def safe_to_dispose(self):
        return self._job is None or self._job.state() == QProcess.NotRunning

    def begin_shutdown(self):
        self._closing = True
        if self._job is not None and self._job.state() != QProcess.NotRunning:
            # QProcess is allowed to finish and notify the MainWindow shutdown gate.
            return False
        return True

    def _status(self, text):
        self.panel.phase.setText(text)
        self.changed.emit(text)
        self.view.task_event_panel.add_ui_event('Tái tạo 3D: ' + text)
        # Existing Task Dock contract uses canonical source/state enums.
        detail = text.casefold()
        if any(word in detail for word in ('không thể', 'không hợp lệ', 'thất bại', 'bị lỗi')):
            state = 'failed'
        elif any(word in detail for word in ('hoàn thành', 'đã xác minh', 'sẵn sàng xem')):
            state = 'succeeded'
        else:
            state = 'running'
        self.view.task_event_panel.record_operation('Reconstruction', state, text)

    def sync_workspace_context(self, workspace):
        # Project selection remains authoritative; show external cloud provenance
        # above the tree instead of silently pretending it belongs to SQLite.
        active = workspace in (WorkspaceId.INSPECT3D, WorkspaceId.PROCESSING)
        available = self._cloud is not None or self._bundle is not None or self._c1 is not None or self._c2 is not None
        self.explorer_context.setVisible(bool(active and available))
        self.view.explorer_dock.setWindowTitle(
            'Dữ liệu dự án · Phiên 3D' if active and available else 'Cây dự án')
        if active and available:
            source = self._c2 or self._bundle or self._c1 or self._cloud
            self.explorer_context.setText(
                'PHIÊN TÁI TẠO ĐANG MỞ\n' + source.name +
                ('\nGắn với phiên Project và RAW đã lưu' if self._project_context else
                 '\nDữ liệu ngoài Project · cần chọn phiên để lưu đồng bộ'))
            self.explorer_context.setToolTip(str(source))

    def _selected_session(self):
        from scantopath.modules.reconstruction.application.project_sessions import selected_ui_session
        return selected_ui_session(self.view)

    def _open_session_raw(self):
        from scantopath.modules.reconstruction.application.project_sessions import latest_raw_sequence
        try:
            context = self._selected_session()
            if context is None:
                self._status('Chọn phiên quét trong Cây dự án trước khi mở RAW.')
                return
            self._start_merge(latest_raw_sequence(context))
        except (OSError, ValueError, KeyError) as exc:
            self._status('Không tìm thấy RAW của phiên: ' + str(exc)[:140])

    def _open_session_result(self):
        from scantopath.modules.reconstruction.application.project_sessions import latest_result
        try:
            context = self._selected_session()
            if context is None:
                self._status('Chọn phiên quét trong Cây dự án trước khi mở mesh/path.')
                return
            self._verify_project_c2(context, latest_result(context))
        except (OSError, ValueError, KeyError) as exc:
            self._status('Không tìm thấy mesh/path của phiên: ' + str(exc)[:140])

    def _verify_project_c2(self, context, folder):
        if self._job is not None:
            return
        self._project_context = context
        from scantopath.modules.reconstruction.application.project_sessions import project_pipeline_root
        self._last_output = project_pipeline_root(context)/'03_RECONSTRUCTION'
        self._choose_c2_folder(folder)

    def _choose_c2_folder(self, folder):
        if self._job is not None:
            return
        self._start('c2_verify', 'c2_surface_to_path.py', ['--verify', str(folder)])
        self._status('Đang xác minh kết quả Mesh/Path theo SHA-256…')

    def _load_history(self):
        history = self.settings.value('portable_bundles', [], type=list)
        self.panel.set_history(history if isinstance(history, list) else [])

    def _remember(self, path):
        current = self.settings.value('portable_bundles', [], type=list)
        current = current if isinstance(current, list) else []
        items = [str(path)] + [v for v in current if v != str(path)]
        self.settings.setValue('portable_bundles', items[:12])
        self._load_history()

    def _tracking_started(self, count: int):
        if not self._closing:
            self._status(f'Đang tính pose và chất lượng FT-09 cho {count} frame…')

    def _sequence_complete(self, folder: str, accepted: int, total: int, state: str):
        if self._closing:
            return
        self._start_merge(Path(folder))

    def _choose_sequence(self):
        if self._job is not None:
            return
        folder = QFileDialog.getExistingDirectory(
            self.panel, 'Chọn chuỗi FT-09/FT-08.17 đã lưu', str(Path.home()))
        if folder:
            self._start_merge(Path(folder))

    def _start_merge(self, source: Path):
        if self._job is not None or self._closing:
            return
        if not (source/'tracking_sequence.json').is_file():
            self._status('Chuỗi không hợp lệ: thiếu tracking_sequence.json')
            return
        from scantopath.modules.reconstruction.application.project_sessions import sequence_context, project_pipeline_root
        try:
            context = sequence_context(source)
        except (ValueError, OSError, KeyError) as exc:
            self._status('RAW không có quyền sở hữu phiên hợp lệ: ' + str(exc)[:140])
            return
        self._sequence = source
        self._project_context = context
        self._last_output = (project_pipeline_root(self._project_context,create=True)/'03_RECONSTRUCTION'
                             if self._project_context else self._default_output)
        self._fine = self.panel.quality.currentData() == 'fine'
        self._cloud = self._bundle = self._c1 = self._c2 = self._reference = None
        self.panel.set_c2_available(False, False)
        self.panel.c2_status.setText('C2: đang chờ cloud C1 từ phiên quét mới.')
        self.panel.c1_status.setText('C1: sẽ chạy sau khi tích lũy FT-10.')
        self._tracking = {}
        self._debug = False
        self.panel.clear_tracking()
        self.sync_workspace_context(self.view.active_workspace)
        self._start('merge', 'ft10_merge_multiview.py', [
            '--input-sequence', str(source), '--out', str(self._last_output),
            '--voxel-mm', '2.0' if self._fine else '4.0'])
        self._status('Đang ghép cloud · FT-09 pose → FT-10 accumulation…')

    def _enter_metric_reference(self):
        if self._sequence is None or self._cloud is None or self._job is not None:
            return
        dialog = QDialog(self.panel)
        dialog.setWindowTitle('Đo kích thước mẫu · FT-14')
        layout = QFormLayout(dialog)
        edits = {}
        for label, axis in (('Chiều X (mm)', 'x'), ('Chiều Y (mm)', 'y'), ('Chiều Z (mm)', 'z')):
            edit = QDoubleSpinBox(dialog)
            edit.setRange(0.01, 100000.0)
            edit.setDecimals(2)
            edit.setValue(100.0)
            edit.setSuffix(' mm')
            edits[axis] = edit
            layout.addRow(label, edit)
        method = QLineEdit('Đo kích thước bằng thước cặp/thước', dialog)
        instrument = QLineEdit('Thước đối chứng', dialog)
        aligned = QCheckBox('Tôi xác nhận các trục XYZ của cloud khớp hướng đo trên vật', dialog)
        layout.addRow('Phương pháp đo', method)
        layout.addRow('Dụng cụ', instrument)
        layout.addRow(aligned)
        note = QLabel('Chỉ kiểm tra kích thước theo bounding box trên các trục đã xác nhận; không phải chứng nhận calibration.', dialog)
        note.setWordWrap(True)
        layout.addRow(note)
        buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel, dialog)
        buttons.accepted.connect(dialog.accept)
        buttons.rejected.connect(dialog.reject)
        layout.addRow(buttons)
        if dialog.exec() != QDialog.Accepted:
            return
        if not aligned.isChecked() or not method.text().strip() or not instrument.text().strip():
            QMessageBox.warning(self.panel, 'Thiếu bằng chứng đo',
                'Cần xác nhận hướng XYZ và ghi phương pháp/dụng cụ đo thực tế.')
            return
        record = {'axes_mm':{ax:float(spin.value()) for ax, spin in edits.items()},
                  'measurement_method':method.text().strip(),
                  'reference_instrument':instrument.text().strip(),
                  'axis_alignment_confirmed':True,
                  'created_utc':datetime.now(timezone.utc).isoformat(),
                  'source_ft09':str(self._sequence)}
        reference_folder = self._last_output/'operator_references'
        reference_folder.mkdir(parents=True, exist_ok=True)
        from uuid import uuid4
        reference = reference_folder/('reference_'+uuid4().hex[:12]+'.json')
        reference.write_text(json.dumps(record, ensure_ascii=False, indent=2)+'\n', encoding='utf8')
        self._reference = reference
        self._status('Đã nhập kích thước chuẩn · chạy lại C1 để kiểm tra gate 10 mm.')
        self._start_c1()

    def _context_for_c1(self, source):
        from scantopath.modules.reconstruction.application.project_sessions import (
            context_for_c1, project_pipeline_root)
        context = context_for_c1(source)
        self._project_context = context
        if context is not None:
            record = json.loads((Path(source)/'processing_run.json').read_text(encoding='utf8'))
            self._sequence = Path(record['input_source']['ft09_dir'])
        else:
            self._sequence = None
        self._last_output = (project_pipeline_root(context,create=True)/'03_RECONSTRUCTION'
                             if context else self._default_output)

    def _choose_c1(self):
        if self._job is not None:
            return
        folder = QFileDialog.getExistingDirectory(
            self.panel, 'Chọn cloud C1 đã lưu để dựng mesh/path', str(self._last_output/'C1_Results'))
        if not folder:
            return
        try:
            self._context_for_c1(Path(folder))
        except (OSError, ValueError, KeyError) as exc:
            self._status('Cloud C1 không khớp phiên: ' + str(exc)[:140])
            return
        self._start('c1_verify', 'c1_trusted_cloud.py', ['--verify', folder])
        self._status('C2: đang xác minh C1 SHA-256 trước khi dựng mesh…')

    def _choose_c2(self):
        if self._job is not None:
            return
        folder = QFileDialog.getExistingDirectory(
            self.panel, 'Chọn artifact C2 đã lưu', str(self._last_output/'C2_Results'))
        if not folder:
            return
        self._project_context = None  # external reopen cannot inherit previous Project owner
        self._last_output = self._default_output
        self._start('c2_verify', 'c2_surface_to_path.py', ['--verify', folder])
        self._status('C2: đang xác minh SHA-256 và đường dẫn đã lưu…')

    def _start_c2(self):
        if self._closing or self._job is not None or self._c1 is None:
            return
        self._c2 = None
        self.panel.set_c2_available(True, False)
        self.panel.c2_status.setText('C2: đang dựng mesh, sinh Zigzag và Contour…')
        self._start('c2', 'c2_surface_to_path.py', [
            '--c1', str(self._c1), '--out', str(self._last_output/'C2_Results'),
            '--mesh-spacing-mm', '3.5' if self._fine else '6.0'])
        self._status('C2: FT-16 Mesh → FT-17 Zigzag → FT-18 Contour & Export…')

    def _view_c2(self, kind):
        if self._c2 is None or kind not in ('mesh', 'zigzag', 'contour'):
            return
        self._c2_display = kind
        self._debug = False
        self._view_current()

    def _start_c1(self):
        if self._closing or self._job is not None or self._sequence is None or self._cloud is None:
            return
        self._c1 = self._c2 = None
        self.panel.set_c2_available(False, False)
        self.panel.c2_status.setText('C2: chờ cloud C1 sau khi chạy lại.')
        self.panel.c1_status.setText('C1: đang phân tích cloud và pose…')
        args = ['--sequence', str(self._sequence), '--cloud', str(self._cloud),
                '--out', str(self._last_output/'C1_Results')]
        if self._reference is not None:
            args += ['--reference', str(self._reference)]
        if self._project_context:
            args += ['--store-root', self._project_context['store_root']]
        args += ['--voxel-mm', '2.0' if self._fine else '4.0',
                 '--sor-sigma', '3.2' if self._fine else '2.5']
        self._start('c1', 'c1_trusted_cloud.py', args)
        self._status('C1: đang tách vật thể, ước lượng normal, kiểm tra pose và provenance…')

    def _choose_export(self):
        if self._cloud is None or self._sequence is None or self._job is not None:
            return
        destination = QFileDialog.getExistingDirectory(
            self.panel, 'Chọn vị trí lưu phiên tái tạo', str(Path.home()/'Documents'))
        if destination:
            self._start('export', 'ft11_bundle.py', [
                '--export', '--source-sequence', str(self._sequence),
                '--source-cloud', str(self._cloud), '--out', destination])
            self._status('Đang lưu cloud, pose và báo cáo; kiểm tra SHA-256…')

    def _choose_bundle(self):
        if self._job is not None:
            return
        folder = QFileDialog.getExistingDirectory(
            self.panel, 'Mở phiên ScanToPath_Reconstruction đã lưu', str(Path.home()/'Documents'))
        if folder:
            self._verify_bundle(folder)

    def _verify_bundle(self, folder: str):
        if self._job is not None:
            return
        self._start('verify', 'ft11_bundle.py', ['--verify', str(folder)])
        self._status('Đang xác minh phiên đã lưu · SHA-256 và PLY…')

    def _start(self, kind, script, args):
        if self._job is not None:
            return
        binary = self.scripts/script
        if not binary.is_file():
            self._status('Thiếu công cụ xử lý: ' + script)
            return
        job = QProcess(self)
        job.setProcessChannelMode(QProcess.MergedChannels)
        job.setWorkingDirectory(str(self.repo))
        job.readyReadStandardOutput.connect(self._collect)
        job.finished.connect(self._finished)
        job.errorOccurred.connect(self._error)
        self._job = job
        self._kind = kind
        self._stdout = ''
        self._message = {}
        self.panel.set_ready(False, True)
        job.start(sys.executable, ['-X', 'utf8', str(binary), *args])

    def _collect(self):
        if self._job is None:
            return
        data = bytes(self._job.readAllStandardOutput()).decode('utf-8', 'replace')
        self._stdout += data
        while '\n' in self._stdout:
            line, self._stdout = self._stdout.split('\n', 1)
            try:
                obj = json.loads(line)
            except (ValueError, TypeError):
                continue
            if isinstance(obj, dict):
                if (obj.get('FT10_STATUS') in ('ACCEPTED', 'BLOCKED') or
                    obj.get('FT11_STATUS') in ('VERIFIED', 'EXPORTED', 'BLOCKED') or
                    obj.get('C1_STATUS') in ('READY', 'VERIFIED', 'BLOCKED') or
                    obj.get('C2_STATUS') in ('READY', 'VERIFIED', 'BLOCKED')):
                    self._message = obj
                elif obj.get('FT10_STATUS') == 'VIEW_ACCUMULATED':
                    self.panel.points.setText('Voxel: ' + str(obj.get('merged_voxels', '—')))

    def _error(self, reason):
        if self._closing:
            return
        if reason == QProcess.FailedToStart:
            job = self._job
            self._job = None
            self._kind = ''
            if job is not None:
                job.deleteLater()
            self.panel.set_ready(self._cloud is not None or self._bundle is not None, False)
            self._status('Không khởi động được tiến trình Python xử lý.')

    def _finished(self, code, exit_status):
        if self._job is None:
            return
        self._collect()
        job = self._job
        kind = self._kind
        message = self._message
        self._job = None
        self._kind = ''
        if job is not None:
            job.deleteLater()
        if self._closing:
            QTimer.singleShot(0, self.view.close)
            return
        good = code == 0 and exit_status == QProcess.NormalExit
        if (not good or message.get('FT10_STATUS') == 'BLOCKED'
                or message.get('FT11_STATUS') == 'BLOCKED'
                or message.get('C1_STATUS') == 'BLOCKED'
                or message.get('C2_STATUS') == 'BLOCKED'):
            self.panel.set_ready(self._cloud is not None or self._bundle is not None, False)
            if kind == 'c1':
                self.panel.c1_status.setText('C1 từ chối: ' + str(message.get('code','PROCESS_FAILED')))
            self._status('Không thể hoàn tất ' + kind + ': ' + str(message.get('code', 'PROCESS_FAILED')))
            return
        try:
            if kind == 'merge' and message.get('FT10_STATUS') == 'ACCEPTED':
                self._cloud = Path(message['artifact_dir'])
                self._tracking = json.loads((self._sequence/'tracking_sequence.json').read_text(encoding='utf-8'))
                self.panel.set_tracking(self._tracking)
                self.panel.points.setText('Điểm XYZ: ' + str(message['points']))
                self._status('Tái tạo hoàn thành · PLY đã xác minh · Sẵn sàng xem 3D')
                self.panel.set_ready(True, False)
                self.sync_workspace_context(self.view.active_workspace)
                if self._viewer_actions_installed:
                    self._viewer_export_button.setEnabled(True)
                self._view_current()
                self._start_c1()  # C1 follows FT10 automatically, but FT10 remains viewable on failure.
            elif kind in ('verify', 'export') and message.get('FT11_STATUS') in ('VERIFIED', 'EXPORTED'):
                self._bundle = Path(message['artifact_dir'])
                self._project_context = None
                self._last_output = self._default_output
                self._c1 = self._c2 = self._reference = None
                self.panel.set_c2_available(False, False)
                self.panel.c1_status.setText('C1: không có RAW để xử lý lại phiên portable này.')
                self._cloud = None
                self._sequence = None
                self._tracking = json.loads((self._bundle/'poses/tracking_sequence.json').read_text(encoding='utf-8'))
                self.panel.set_tracking(self._tracking)
                self.panel.points.setText('Điểm XYZ: ' + str(message['points']))
                self._remember(self._bundle)
                self._status('Phiên đã xác minh · Có thể mở lại cloud và pose')
                self.panel.set_ready(True, False)
                self.sync_workspace_context(self.view.active_workspace)
                self.panel.export_button.setEnabled(False)  # imported portable bundle has no RAW
                if self._viewer_actions_installed:
                    self._viewer_export_button.setEnabled(False)
                self._view_current()
            elif kind == 'c1' and message.get('C1_STATUS') == 'READY':
                self._c1 = Path(message['artifact_dir'])
                self.panel.set_c2_available(True, False)
                result = message.get('metric_gate', 'NOT_TESTED')
                self.panel.c1_status.setText('C1: ' + result.replace('_',' ') +
                                              ' · pose chỉ đạt kiểm tra hình học')
                self.panel.points.setText('Điểm XYZ: ' + str(message['points']))
                self._status('C1 hoàn thành · cloud vật thể và normal đã lưu · Metric: ' + result)
                self.panel.set_ready(True, False)
                self._debug = False
                self._view_current()
                self._start_c2()  # C2 follows C1 automatically; C1 remains independently usable.
            elif kind == 'c1_verify' and message.get('C1_STATUS') == 'VERIFIED':
                self._c1 = Path(message['artifact_dir'])
                self._c2 = None
                self._tracking = {}
                self.panel.clear_tracking()
                self.panel.points.setText('Điểm XYZ: ' + str(message['points']))
                self.panel.set_c2_available(True, False)
                self._status('Đã xác minh cloud C1; bắt đầu dựng C2 từ artifact đã lưu.')
                self._start_c2()
            elif kind in ('c2', 'c2_verify') and message.get('C2_STATUS') in ('READY', 'VERIFIED'):
                self._c2 = Path(message['artifact_dir'])
                project_warning = ''
                if kind == 'c2' and self._project_context is not None and self._sequence is not None and self._c1 is not None:
                    try:
                        from scantopath.modules.reconstruction.application.project_sessions import record_c2
                        record_c2(self._project_context,self._sequence,self._c1,self._c2)
                        # Refresh the existing Project tree after SQLite run publication.
                        # Do not manufacture a second Explorer or alter its owner.
                        QTimer.singleShot(0, self.view._reload_project_store)
                    except (OSError, ValueError, RuntimeError, KeyError) as exc:
                        project_warning = ' · CHƯA GẮN VÀO PROJECT: ' + str(exc)[:100]
                self._c2_display = 'mesh'
                self.panel.set_c2_available(self._c1 is not None, True)
                self.panel.c2_status.setText(
                    f'C2: {message["faces"]} tam giác · Zigzag {message["zigzag_points"]} điểm · '
                    f'Contour {message["contour_points"]} điểm · Mặt dưới chưa kiểm chứng')
                self.panel.set_ready(True, False)
                self._status('C2 hoàn thành · Mesh và đường dẫn XYZ + normal đã lưu'
                             + project_warning + ' · Chưa chứng nhận metric')
                self.sync_workspace_context(self.view.active_workspace)
                self._view_current()
            else:
                self._status('Kết quả tiến trình không đúng giao thức FT-11: ' + kind)
                self.panel.set_ready(False, False)
        except (OSError, KeyError, ValueError) as exc:
            self.panel.set_ready(False, False)
            self._status('Không thể đọc kết quả: ' + type(exc).__name__)

    def _main_ply(self):
        if self._c2 is not None and not self._debug:
            name = {'mesh': 'surface_mesh.ply',
                    'zigzag': 'zigzag_preview.ply',
                    'contour': 'contour_preview.ply'}[self._c2_display]
            return self._c2/name
        if self._c1 is not None and not self._debug:
            return self._c1/'trusted_object_cloud.ply'
        if self._bundle is not None:
            return self._bundle/'cloud'/('debug_view_colored.ply' if self._debug else 'merged_measured.ply')
        if self._cloud is not None:
            return self._cloud/('debug_view_colored.ply' if self._debug else 'merged_measured.ply')
        return None

    def _view_current(self):
        ply = self._main_ply()
        if ply is None or not ply.is_file():
            return
        self.view._navigate(WorkspaceId.INSPECT3D)
        if self.view.active_workspace is not WorkspaceId.INSPECT3D:
            self._status('Không thể chuyển sang Kiểm tra 3D')
            return
        viewer = self.view.viewer3d
        self._install_viewer_actions(viewer)
        if not viewer.load_ply(str(ply)):
            self._status('Viewer đang bận hoặc không thể mở PLY; kết quả vẫn được lưu.')
            return
        if hasattr(viewer, 'set_reconstruction_context'):
            points = self.panel.points.text().replace('Điểm XYZ: ', '')
            viewer.set_reconstruction_context((
                ('Loại kết quả', 'C2 Mesh / Path tham chiếu · FT-16–18' if self._c2 and not self._debug else ('C1 cloud vật thể · FT-12/15' if self._c1 and not self._debug else 'Cloud tích lũy đa góc · FT-10')),
                ('Số frame', self.panel.frames.text().replace('Frame: ', '')),
                ('Pose hợp lệ', self.panel.poses.text().replace('Pose: ', '')),
                ('Số điểm', points),
                ('Nguồn hình học', 'FT-05.8 ChArUco + FT-09 pose + C1 SOR/PCA' if self._c1 and not self._debug else 'Điểm đo RGB-D · voxel 4 mm mặc định'),
                ('Độ tin cậy', 'Pose ước lượng · kích thước chưa kiểm chứng'),
                ('C1 · metric', self.panel.c1_status.text()),
                ('C2 · đường dẫn', self.panel.c2_status.text()),
                ('C2 · độ phủ mặt đáy', 'CHƯA KIỂM CHỨNG'),
            ))
        label = ('Xem cloud C1' if self._debug and self._c1 is not None else
                 'Xem cloud tổng hợp' if self._debug else 'Màu theo góc')
        self.panel.mode_button.setText(label)
        self._viewer_mode_button.setText(label)

    def _install_viewer_actions(self, viewer):
        if self._viewer_actions_installed:
            return
        # Reuse the original Viewer header, not another sidebar or renderer.
        row = viewer.page.layout().itemAt(0).layout()
        if row is None:
            raise RuntimeError('FT11_VIEWER_HEADER_MISSING')
        self._viewer_mode_button = QPushButton('Màu theo góc', viewer.page)
        self._viewer_mode_button.setObjectName('ft11ViewerMode')
        self._viewer_mode_button.clicked.connect(self._toggle_mode)
        self._viewer_export_button = QPushButton('Lưu phiên…', viewer.page)
        self._viewer_export_button.setObjectName('ft11ViewerExport')
        self._viewer_export_button.clicked.connect(self._choose_export)
        self._viewer_export_button.setEnabled(self._cloud is not None and self._sequence is not None)
        self._viewer_pose_button = QPushButton('Pose & chất lượng', viewer.page)
        self._viewer_pose_button.setObjectName('ft11ViewerPoses')
        self._viewer_pose_button.clicked.connect(self._open_pose_workspace)
        # Keep optional Viewer controls in the EXISTING VTK advanced toolbar.
        # Their original QPushButtons and signal wiring are unchanged.
        if hasattr(viewer, 'tools') and hasattr(viewer.tools, 'advanced_menu'):
            menu = viewer.tools.advanced_menu
            menu.addSeparator()
            safe = menu.addAction('Xem trước an toàn (tương thích)')
            safe.setCheckable(True)
            safe.triggered.connect(viewer.safe_preview_button.setChecked)
            retry = menu.addAction('Thử lại hiển thị')
            retry.triggered.connect(viewer.retry_button.click)
            menu.aboutToShow.connect(
                lambda: (safe.setChecked(viewer.safe_preview_button.isChecked()),
                         retry.setEnabled(viewer.retry_button.isEnabled())))
            viewer.safe_preview_button.hide()
            viewer.retry_button.hide()
        self._viewer_pose_button.setText('Xem pose')
        for button in (self._viewer_export_button, self._viewer_mode_button,
                       self._viewer_pose_button):
            row.insertWidget(1, button)
        self._viewer_actions_installed = True

    def _open_pose_workspace(self):
        self.view._navigate(WorkspaceId.PROCESSING)
        self.tabs.setCurrentWidget(self.panel)

    def _toggle_mode(self):
        if self._job is None:
            self._debug = not self._debug
            self._view_current()

    def _show_pose(self, index: int):
        if self._closing:
            return
        rows = self._tracking.get('frames') or self._tracking.get('samples') or []
        row = next((r for i, r in enumerate(rows) if r.get('sample_index', i) == index), None)
        if row is None:
            return
        inspector = self.view.property_inspector
        inspector.set_selection(None)
        inspector.kind_label.setText('POSE 6DOF')
        inspector.title_label.setText('Frame ' + str(index))
        inspector.section_label.setText('TRACKING QUALITY · FT-09')
        inspector.details.clear()
        from PySide6.QtWidgets import QTreeWidgetItem
        quality = row.get('quality') if isinstance(row.get('quality'), dict) else {}
        for key in ('status', 'accepted_for_trajectory', 'reject_code'):
            QTreeWidgetItem(inspector.details, [key, str(row.get(key, '—'))])
        for key in ('overlap', 'inlier_rmse_m', 'inlier_count', 'rotation_deg', 'translation_m'):
            QTreeWidgetItem(inspector.details, [key, str(quality.get(key, '—'))])
        T = row.get('T_world_depth')
        if isinstance(T, list) and len(T) == 4:
            for r, values in enumerate(T):
                QTreeWidgetItem(inspector.details, [f'Pose [{r}]', '  '.join(f'{float(x):.6f}' for x in values)])
        inspector.note.setText('T_world_depth · mét · pose ước lượng, chưa kiểm chứng metric.')
        inspector.empty_label.hide()
        inspector.context_frame.show()
        inspector.context_separator.show()
        inspector.properties_frame.show()
        inspector.actions_frame.hide()

