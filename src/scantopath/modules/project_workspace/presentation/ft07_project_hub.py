"""FT-07 project-centric workspace. The Explorer remains authoritative selection.

No filesystem/SQLite access on Qt GUI thread. Derived snapshots are loaded
using a short-lived worker and are never represented as fake RAW Captures.
"""
from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import Qt, QThread, QTimer, Signal
from PySide6.QtWidgets import (
    QFrame, QFileDialog, QHBoxLayout, QLabel, QMessageBox, QPushButton,
    QTreeWidget, QTreeWidgetItem, QVBoxLayout, QWidget, QApplication,
)

from scantopath.application.contracts import SelectionRef, WorkspaceId
from scantopath.modules.project_workspace.infrastructure.derived_artifacts import (
    DerivedSnapshot, list_snapshots, attach_snapshot, resolve_snapshot,
)


class _ArtifactJob(QThread):
    success = Signal(object)
    failed = Signal(str)

    def __init__(self, operation: str, root: str, session_id: str,
                 owner: tuple[str, str] = ('', ''), source: str = '', parent=None):
        super().__init__(parent)
        self.operation = operation
        self.root = root
        self.session_id = session_id
        self.owner = owner
        self.source = source

    def run(self):
        try:
            if self.operation == 'list':
                result = list_snapshots(self.root, self.session_id)
            elif self.operation == 'attach':
                project_id, specimen_id = self.owner
                result = attach_snapshot(self.root, project_id, specimen_id,
                                         self.session_id, self.source)
            else:
                raise ValueError('FT07_INVALID_ARTIFACT_OPERATION')
            self.success.emit((self.root, self.session_id, self.operation, result))
        except Exception as exc:
            self.failed.emit(type(exc).__name__ + ': ' + str(exc)[:220])


class ProjectHub(QFrame):
    """One central entity page; never a second all-project hierarchy."""

    selected = Signal(object)
    capture_open_requested = Signal(object)
    open_artifact_requested = Signal(object)
    process_artifact_requested = Signal(object)
    change_store_requested = Signal()
    create_project_requested = Signal()
    create_specimen_requested = Signal()
    create_session_requested = Signal()
    capture_session_requested = Signal()
    import_snapshot_requested = Signal()

    _TITLES = {'project': 'Dự án', 'specimen': 'Vật mẫu', 'scan_session': 'Phiên quét',
               'capture': 'Bản thu RAW', 'processing_run': 'Lần xử lý'}

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName('ft07ProjectHub')
        self._trees = ()
        self._selection = None
        self._current_artifact = None
        self._artifacts = ()
        self._store_root = None
        self._updating = False
        self._pending_selection = None
        self._can_write = False
        self._busy = False
        root = QVBoxLayout(self)
        root.setContentsMargins(14, 10, 14, 10)
        root.setSpacing(9)

        top = QHBoxLayout()
        self.crumb = QLabel('Kho dữ liệu', self)
        self.crumb.setObjectName('ft07Breadcrumb')
        self.crumb.setWordWrap(True)
        top.addWidget(self.crumb, 1)
        self.change_button = QPushButton('Đổi kho', self)
        self.change_button.clicked.connect(self.change_store_requested.emit)
        top.addWidget(self.change_button)
        root.addLayout(top)

        self.heading = QLabel('DỰ ÁN', self)
        self.heading.setObjectName('ft07EntityTitle')
        font = self.heading.font()
        font.setPointSize(max(font.pointSize(), 13))
        font.setBold(True)
        self.heading.setFont(font)
        root.addWidget(self.heading)
        self.description = QLabel('Chọn một đối tượng trong cây dự án để xem chi tiết.', self)
        self.description.setWordWrap(True)
        root.addWidget(self.description)

        actions = QHBoxLayout()
        self.primary = QPushButton('Tạo dự án', self)
        self.primary.setObjectName('ft07PrimaryAction')
        actions.addWidget(self.primary)
        self.secondary = QPushButton('Thao tác tiếp', self)
        self.secondary.setObjectName('ft07SecondaryAction')
        self.secondary.hide()
        actions.addWidget(self.secondary)
        self.import_button = QPushButton('Gắn Snapshot…', self)
        self.import_button.setObjectName('ft07AttachSnapshot')
        self.import_button.clicked.connect(self.import_snapshot_requested.emit)
        self.import_button.hide()
        actions.addWidget(self.import_button)
        actions.addStretch(1)
        root.addLayout(actions)

        self.list_title = QLabel('Nội dung', self)
        self.list_title.setObjectName('ft07ChildrenTitle')
        root.addWidget(self.list_title)
        self.items = QTreeWidget(self)
        self.items.setObjectName('ft07EntityChildren')
        self.items.setHeaderLabels(['Tên / mã', 'Loại', 'Trạng thái / thông tin'])
        self.items.setRootIsDecorated(False)
        self.items.setAlternatingRowColors(True)
        self.items.setUniformRowHeights(True)
        self.items.setTextElideMode(Qt.ElideMiddle)
        self.items.itemClicked.connect(self._clicked)
        self.items.itemDoubleClicked.connect(self._opened)
        self.items.header().setStretchLastSection(True)
        root.addWidget(self.items, 1)

        self.detail = QLabel('', self)
        self.detail.setWordWrap(True)
        self.detail.setObjectName('ft07DetailSummary')
        root.addWidget(self.detail)
        self.notice = QLabel('', self)
        self.notice.setObjectName('ft07InlineNotice')
        self.notice.setWordWrap(True)
        root.addWidget(self.notice)
        self.show_bundle(None)

    def _reset_button(self, button, text, action=None):
        try:
            button.clicked.disconnect()
        except (RuntimeError, TypeError):
            pass
        button.setText(text)
        button.setVisible(action is not None)
        if action is not None:
            button.clicked.connect(action)

    def _clicked(self, item, _column):
        if self._updating:
            return
        ref = item.data(0, Qt.UserRole)
        if isinstance(ref, SelectionRef):
            # Let a real double-click arrive before changing the entire page.
            self._pending_selection = ref
            delay = (QApplication.instance().doubleClickInterval() if QApplication.instance()
                     else 350) + 40
            QTimer.singleShot(delay, lambda candidate=ref: self._commit_click(candidate))
        elif isinstance(ref, DerivedSnapshot):
            self._current_artifact = ref
            self.detail.setText(
                f'Snapshot xử lý · {ref.point_count:,} điểm · {ref.reference_mode} · '
                f'{"Có điểm ước lượng" if ref.estimated else "Không đánh dấu điểm ước lượng"}\n'
                'Dữ liệu dẫn xuất: chưa xác minh độ chính xác hình học.')
            self._configure_artifact_actions()

    def _commit_click(self, candidate):
        if self._pending_selection == candidate:
            self._pending_selection = None
            self._current_artifact = None
            self.selected.emit(candidate)

    def _opened(self, item, _column):
        ref = item.data(0, Qt.UserRole)
        self._pending_selection = None
        if isinstance(ref, DerivedSnapshot):
            self._current_artifact = ref
            self.open_artifact_requested.emit(ref)
        elif isinstance(ref, SelectionRef):
            if ref.entity_type == 'capture':
                # Resolve SelectionRef/WorkflowContext first; open in next Qt turn.
                self.selected.emit(ref)
                QTimer.singleShot(0, lambda source=ref: self.capture_open_requested.emit(source))
            else:
                self.selected.emit(ref)

    def _configure_artifact_actions(self):
        artifact = self._current_artifact
        if artifact is None:
            return
        self._reset_button(self.primary, 'Kiểm tra 3D',
                           lambda: self.open_artifact_requested.emit(artifact))
        self._reset_button(self.secondary, 'Chuyển sang Xử lý',
                           lambda: self.process_artifact_requested.emit(artifact))
        self.import_button.show()

    def show_bundle(self, bundle):
        self._trees = bundle.trees if bundle is not None else ()
        self._store_root = bundle.info.root if bundle is not None else None
        self._artifacts = ()
        self._selection = None
        self._current_artifact = None
        self._pending_selection = None
        self.set_selection(None)

    def _path(self, ref):
        for tree in self._trees:
            p = tree.project
            if ref == SelectionRef('project', p.project_id):
                return (p.name,), tree, None, None
            for node in tree.specimens:
                s = node.specimen
                if ref == SelectionRef('specimen', s.specimen_id):
                    return (p.name, s.label), tree, node, None
                for session in node.sessions:
                    full = (p.name, s.label, session.label)
                    if ref == SelectionRef('scan_session', session.session_id):
                        return full, tree, node, session
                    if any(ref == SelectionRef('capture', c.capture_id) for c in session.captures):
                        return full + ('RAW',), tree, node, session
                    if any(ref == SelectionRef('processing_run', r.run_id) for r in session.processing_runs):
                        return full + ('Xử lý',), tree, node, session
        return (), None, None, None

    def session_context(self):
        if self._selection is None:
            return None
        _, tree, node, session = self._path(self._selection)
        if tree is None or node is None or session is None or self._store_root is None:
            return None
        return (str(self._store_root), tree.project.project_id,
                node.specimen.specimen_id, session.session_id)

    def set_selection(self, selection):
        if selection != self._selection:
            self._pending_selection = None
            self._current_artifact = None
            self._artifacts = ()
        self._selection = selection
        self._updating = True
        try:
            self.items.clear()
            path, tree, node, session = self._path(selection) if selection else ((), None, None, None)
            self.crumb.setText(' / '.join(('Kho', *path)) if path else 'Kho dữ liệu')
            self.heading.setText(self._TITLES.get(selection.entity_type, 'KHO DỮ LIỆU').upper()
                                 if selection else 'DANH SÁCH DỰ ÁN')
            self.detail.clear()
            self.notice.clear()
            self.import_button.setVisible(False)
            self._reset_button(self.secondary, '', None)
            if tree is None:
                self.description.setText('Chọn dự án từ danh sách hoặc từ cây bên trái.')
                self.list_title.setText(f'{len(self._trees)} dự án')
                for t in self._trees:
                    self._row(t.project.storage.public_code or t.project.name, 'Dự án',
                              t.project.name, SelectionRef('project', t.project.project_id))
                self._reset_button(self.primary, '+ Tạo dự án', self.create_project_requested.emit)
            elif node is None:
                self.description.setText(tree.project.description or 'Dự án chưa có mô tả.')
                self.list_title.setText(f'{len(tree.specimens)} vật mẫu trong dự án')
                for n in tree.specimens:
                    self._row(n.specimen.label, 'Vật mẫu', f'{len(n.sessions)} phiên',
                              SelectionRef('specimen', n.specimen.specimen_id))
                self._reset_button(self.primary, '+ Thêm vật mẫu', self.create_specimen_requested.emit)
            elif session is None:
                self.description.setText(node.specimen.description or 'Vật mẫu chưa có mô tả.')
                self.list_title.setText(f'{len(node.sessions)} phiên quét của vật mẫu')
                for s in node.sessions:
                    self._row(s.label, 'Phiên quét', 'Đang mở' if s.state == 'open' else 'Đã đóng',
                              SelectionRef('scan_session', s.session_id))
                self._reset_button(self.primary, '+ Tạo phiên quét', self.create_session_requested.emit)
            elif selection.entity_type == 'scan_session':
                self.description.setText(f'Phiên: {session.label} · '
                                         + ('Đang mở' if session.state == 'open' else 'Đã đóng'))
                self._populate_session(session)
                self._reset_button(self.primary, 'Thu nhận RGB-D', self.capture_session_requested.emit)
                self.import_button.show()
            elif selection.entity_type == 'capture':
                cap = next(c for c in session.captures if c.capture_id == selection.entity_id)
                self.description.setText(f'RAW {cap.kind} · Đăng ký {cap.registered_at}')
                self.detail.setText(f'RAW schema v{cap.schema_version}; trạng thái: {cap.storage.state}. '
                                    'Tính toàn vẹn tệp không chứng minh độ chính xác hình học.')
                self.list_title.setText('Nguồn dữ liệu đã chọn')
                self._reset_button(self.primary, 'Phát lại RAW',
                                   lambda: self.capture_open_requested.emit(selection))
            else:
                run = next(r for r in session.processing_runs if r.run_id == selection.entity_id)
                self.description.setText(f'{run.stage} · {run.algorithm} · {run.state}')
                self.detail.setText('Đầu vào: ' + (', '.join(run.input_capture_ids) or 'Chưa có')
                                    + '\nĐầu ra tham chiếu: ' + (', '.join(run.output_files) or 'Chưa có'))
                self.list_title.setText('Lần xử lý được chọn')
                self._reset_button(self.primary, '', None)
            self.items.resizeColumnToContents(0)
            self.items.resizeColumnToContents(1)
        finally:
            self._updating = False
        self.set_controls(self._can_write, selection, self._busy)

    def _row(self, title, kind, info, ref):
        item = QTreeWidgetItem(self.items, [str(title), str(kind), str(info)])
        item.setData(0, Qt.UserRole, ref)
        for i in range(3):
            item.setToolTip(i, item.text(i))

    def _populate_session(self, session):
        self.list_title.setText(f'Phiên quét · {len(session.captures)} RAW · '
                                f'{len(self._artifacts)} Snapshot · {len(session.processing_runs)} lần xử lý')
        for cap in session.captures:
            self._row(cap.storage.public_code or cap.capture_id[:8], 'RAW', cap.kind,
                      SelectionRef('capture', cap.capture_id))
        for item in self._artifacts:
            self._row('Snapshot ' + item.artifact_id[:8], 'Snapshot PLY',
                      f'{item.point_count:,} điểm · {item.reference_mode}', item)
        for run in session.processing_runs:
            self._row(run.storage.public_code or run.run_id[:8], 'Lần xử lý', run.state,
                      SelectionRef('processing_run', run.run_id))
        if not self._artifacts:
            self.notice.setText('Snapshot đã lưu ngoài kho chưa tự xuất hiện trong phiên; '
                                'chọn “Gắn Snapshot…” hoặc lưu từ Live khi đang chọn phiên.')

    def set_snapshots(self, session_id: str, artifacts):
        context = self.session_context()
        if context is None or context[3] != session_id or self._selection.entity_type != 'scan_session':
            return
        self._artifacts = tuple(artifacts)
        self.set_selection(self._selection)

    def set_controls(self, writable, selection, busy):
        self._can_write, self._busy = bool(writable), bool(busy)
        self.change_button.setEnabled(not busy)
        if self._current_artifact is not None:
            self.primary.setEnabled(not busy)
            self.secondary.setEnabled(not busy)
        else:
            if selection is not None and selection.entity_type == 'capture':
                self.primary.setEnabled(not busy)
            else:
                can = selection is None or selection.entity_type in ('project', 'specimen', 'scan_session')
                self.primary.setEnabled(writable and not busy and can)
        self.import_button.setEnabled(writable and not busy and self.session_context() is not None)


class ProjectHubPresenter:
    """Drop-in replacement for ProjectDashboardPresenter; no second selection authority."""

    def __init__(self, view, controller):
        self.view, self.controller = view, controller
        self.panel = ProjectHub()
        self._store = controller.recent_stores.panel
        self._workers = []
        self._closing = False
        self._bundle = None
        self._processing_artifact = None
        self._needs_list = None
        scroll = view._pages[WorkspaceId.PROJECTS].findChild(QWidget, 'workspaceScrollContent')
        if scroll is None:
            raise RuntimeError('FT07_PROJECT_SCROLL_HOST_MISSING')
        layout = scroll.layout()
        layout.insertWidget(4, self.panel)
        self.panel.hide()
        # Remove duplicated informational cards; the Store chooser and one
        # Project Hub remain the two mutually-exclusive central states.
        for idx in range(layout.count()):
            w = layout.itemAt(idx).widget()
            if w is not None and w is not self._store and w is not self.panel:
                w.hide()
        self.panel.selected.connect(self._select_explorer)
        self.panel.change_store_requested.connect(self._show_store_chooser)
        self.panel.create_project_requested.connect(controller._create_project)
        self.panel.create_specimen_requested.connect(controller._create_specimen)
        self.panel.create_session_requested.connect(controller._create_session)
        self.panel.capture_session_requested.connect(self._open_capture_for_session)
        self.panel.import_snapshot_requested.connect(self._import_snapshot_dialog)
        self.panel.open_artifact_requested.connect(self._inspect_snapshot)
        self.panel.process_artifact_requested.connect(self._process_snapshot)
        controller.project_loader.loaded.connect(self._on_loaded)
        controller.project_loader.failed.connect(self._on_failed)
        controller.project_loader.busy_changed.connect(self._on_busy)
        controller.project_writer.busy_changed.connect(self._update_actions)
        view.project_explorer.selection_changed.connect(self._on_selection)
        self._store.show()

    def begin_shutdown(self) -> bool:
        self._closing = True
        return not any(job.isRunning() for job in self._workers)

    def _spawn(self, op, root, session_id, owner=('', ''), source=''):
        if self._closing:
            return
        if self._workers:
            if op == 'list':
                self._needs_list = (root, session_id)
            self.panel.notice.setText('Đang xử lý Snapshot trước đó…')
            return
        worker = _ArtifactJob(op, root, session_id, owner, source, self.view)
        self._workers.append(worker)
        worker.success.connect(self._artifact_done)
        worker.failed.connect(lambda message: self.panel.notice.setText('Snapshot: ' + message))
        worker.finished.connect(lambda w=worker: self._cleanup(w))
        worker.start()
        self.panel.notice.setText('Đang ' + ('gắn Snapshot vào phiên…' if op == 'attach' else 'tải Snapshot…'))

    def _cleanup(self, worker):
        if worker.isRunning() or not worker.wait(0):
            from PySide6.QtCore import QTimer
            QTimer.singleShot(20, lambda: self._cleanup(worker))
            return
        if worker in self._workers:
            self._workers.remove(worker)
        worker.deleteLater()
        if self._closing:
            from PySide6.QtCore import QTimer
            QTimer.singleShot(0, self.view.close)
        elif not self._workers and self._needs_list is not None:
            root, session_id = self._needs_list
            self._needs_list = None
            self._list_if_active(root, session_id)

    def _artifact_done(self, payload):
        if self._closing:
            return
        root, session_id, op, data = payload
        ctx = self.panel.session_context()
        if ctx is None or ctx[0] != root or ctx[3] != session_id:
            return  # UI context changed while background I/O was running.
        if op == 'attach':
            self.panel.notice.setText('Đã gắn Snapshot vào phiên quét.')
            self._needs_list = (root, session_id)
        else:
            self.panel.set_snapshots(session_id, data)
            self.panel.notice.setText(f'{len(data)} Snapshot đã gắn với phiên hiện tại.')

    def _list_if_active(self, root, session_id):
        ctx = self.panel.session_context()
        if ctx is not None and ctx[0] == root and ctx[3] == session_id:
            self._spawn('list', root, session_id)

    def _on_loaded(self, bundle):
        self._processing_artifact = None
        self._bundle = bundle
        self.panel.show_bundle(bundle)
        self.panel.set_selection(self.view.project_explorer.selection)
        self._store.hide()
        self.panel.show()
        self._update_actions()
        self._load_current_snapshots()

    def _on_failed(self, _message):
        self._processing_artifact = None
        self._bundle = None
        self.panel.show_bundle(None)
        self.panel.hide()
        self._store.show()
        self._update_actions()

    def _on_busy(self, busy):
        if busy:
            self.panel.hide()
            self._store.show()
        self._update_actions()

    def _show_store_chooser(self):
        self.panel.hide()
        self._store.show()

    def _on_selection(self, selection):
        self.panel.set_selection(selection)
        if self._processing_artifact is not None:
            ctx = self.panel.session_context()
            if ctx is None or ctx[3] != self._processing_artifact[2]:
                self._processing_artifact = None
                self.controller.processing_workspace.clear_snapshot_source()
        self._update_actions()
        self._load_current_snapshots()

    def _update_actions(self, *_args):
        self.panel.set_controls(self.controller._can_write_project(),
                                self.view.project_explorer.selection,
                                self.controller.project_loader.busy or self.controller.project_writer.busy)

    def _select_explorer(self, selection):
        if not self.view.project_explorer.select_ref(selection):
            self.panel.notice.setText('Không tìm thấy đối tượng trong cây dự án đang mở.')

    def _load_current_snapshots(self):
        ctx = self.panel.session_context()
        if ctx and self.panel._selection.entity_type == 'scan_session':
            self._spawn('list', ctx[0], ctx[3])

    def _open_capture_for_session(self):
        ctx = self.panel.session_context()
        if ctx is None:
            return
        _, tree, node, session = self.panel._path(self.panel._selection)
        if session is None or session.state != 'open':
            self.panel.notice.setText('Cần chọn một phiên quét đang mở.')
            return
        self.view._navigate(WorkspaceId.CAPTURE)
        self.view.capture_workspace_layout.tabs.setCurrentWidget(self.view.capture_live.panel)

    def _import_snapshot_dialog(self):
        ctx = self.panel.session_context()
        if ctx is None:
            self.panel.notice.setText('Chọn một phiên quét trước khi gắn Snapshot.')
            return
        folder = QFileDialog.getExistingDirectory(self.panel, 'Chọn thư mục snapshot_…', str(Path.home()))
        if folder:
            self._spawn('attach', ctx[0], ctx[3], (ctx[1], ctx[2]), folder)

    def on_snapshot_saved(self, folder):
        """FT-06 save completion -> automatically attach only with valid Session context."""
        ctx = self.panel.session_context()
        if ctx is None or not self.controller._can_write_project():
            self.view.task_event_panel.add_ui_event(
                'Snapshot đã lưu ngoài dự án; hãy chọn một phiên quét để gắn thủ công.')
            return
        _, tree, node, session = self.panel._path(self.panel._selection)
        if session is None or session.state != 'open':
            self.view.task_event_panel.add_ui_event('Phiên không mở; Snapshot chưa được gắn.')
            return
        self._spawn('attach', ctx[0], ctx[3], (ctx[1], ctx[2]), folder)

    def _snapshot_source(self, artifact):
        if not isinstance(artifact, DerivedSnapshot):
            return None
        ctx = self.panel.session_context()
        if ctx is None or ctx[1:4] != (artifact.project_id, artifact.specimen_id, artifact.session_id):
            self.panel.notice.setText('Snapshot không thuộc ngữ cảnh phiên hiện tại.')
            return None
        try:
            # Read-only resolve is limited to one small metadata JSON + hashes.
            return resolve_snapshot(ctx[0], artifact)
        except Exception as exc:
            self.panel.notice.setText('Snapshot không khả dụng: ' + str(exc)[:180])
            return None

    def _inspect_snapshot(self, artifact):
        source = self._snapshot_source(artifact)
        if source is None:
            return
        self.view._navigate(WorkspaceId.INSPECT3D)
        if self.view.active_workspace is not WorkspaceId.INSPECT3D:
            return
        if not self.view.viewer3d.load_ply(str(source)):
            self.panel.notice.setText('Viewer đang bận hoặc không thể mở PLY.')

    def _process_snapshot(self, artifact):
        source = self._snapshot_source(artifact)
        if source is None:
            return
        self._processing_artifact = (artifact.artifact_id, str(source), artifact.session_id)
        self.view._navigate(WorkspaceId.PROCESSING)
        if self.view.active_workspace is WorkspaceId.PROCESSING:
            self.controller.processing_workspace.set_snapshot_source(
                artifact.artifact_id, artifact.session_id, str(source))
            self.view._set_status('Nguồn Xử lý: Snapshot ' + artifact.artifact_id[:8] +
                                  ' · chỉ chuyển ngữ cảnh, chưa chạy thuật toán.')
            self.view.task_event_panel.add_ui_event(
                'Đã chọn Snapshot ' + artifact.artifact_id[:8] +
                ' cho Xử lý; pipeline xử lý chưa được kích hoạt tự động.')
