"""R3.2 — Project dashboard: read-only DTO presentation + existing write commands.

This widget never imports SQLite/RAW or generates numbering. The Explorer remains
selection authority; all write actions are delegated to 07.5's guarded service.
"""
from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QComboBox, QFrame, QHBoxLayout, QLabel, QPushButton, QTabWidget,
    QTreeWidget, QTreeWidgetItem, QVBoxLayout, QWidget,
)

from scantopath.application.contracts import SelectionRef, WorkspaceId


class ProjectDashboard(QFrame):
    """Central Project/Specimen/Session overview, not a second Explorer tree."""

    selected = Signal(object)
    change_store_requested = Signal()
    create_project_requested = Signal()
    create_specimen_requested = Signal()
    create_session_requested = Signal()

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName('projectDashboard')
        self.setAccessibleName('Không gian quản lý dự án')
        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)
        header = QWidget(self)
        header.setObjectName('dashboardHeader')
        row = QHBoxLayout(header)
        row.setContentsMargins(14, 10, 14, 10)
        row.setSpacing(9)
        self.title = QLabel('DỰ ÁN', header)
        self.title.setObjectName('dashboardTitle')
        row.addWidget(self.title)
        row.addStretch(1)
        self.change_button = QPushButton('Đổi kho', header)
        self.change_button.setObjectName('dashboardChangeStore')
        self.change_button.clicked.connect(self.change_store_requested.emit)
        row.addWidget(self.change_button)
        self.create_project_button = QPushButton('+ Tạo dự án', header)
        self.create_project_button.setObjectName('dashboardCreateProject')
        self.create_project_button.clicked.connect(self.create_project_requested.emit)
        row.addWidget(self.create_project_button)
        root.addWidget(header)
        root.addWidget(self._separator('dashboardHeaderSeparator'))

        context = QWidget(self)
        context.setObjectName('dashboardContext')
        summary = QVBoxLayout(context)
        summary.setContentsMargins(14, 11, 14, 12)
        summary.setSpacing(7)
        self.store_label = QLabel('Chưa chọn kho dữ liệu', context)
        self.store_label.setObjectName('dashboardStoreLabel')
        summary.addWidget(self.store_label)
        project_row = QHBoxLayout()
        project_row.setSpacing(8)
        project_row.addWidget(QLabel('Dự án:', context))
        self.project_combo = QComboBox(context)
        self.project_combo.setObjectName('dashboardProjectSelect')
        self.project_combo.setMinimumWidth(160)
        self.project_combo.currentIndexChanged.connect(self._combo_changed)
        project_row.addWidget(self.project_combo, 1)
        summary.addLayout(project_row)
        self.stats_label = QLabel('Chọn dự án để xem dữ liệu.', context)
        self.stats_label.setObjectName('dashboardStats')
        summary.addWidget(self.stats_label)
        root.addWidget(context)
        root.addWidget(self._separator('dashboardContextSeparator'))

        tabs = QTabWidget(self)
        tabs.setObjectName('dashboardTabs')
        self.tabs = tabs
        definitions = (
            ('specimen', 'Vật mẫu', ('Mã', 'Tên vật mẫu', 'Phiên quét')),
            ('scan_session', 'Phiên quét', ('Mã', 'Tên phiên', 'Trạng thái', 'Vật mẫu')),
            ('capture', 'Bản thu', ('Mã', 'Loại dữ liệu', 'Phiên quét')),
            ('processing_run', 'Lần xử lý', ('Mã', 'Công đoạn', 'Trạng thái', 'Phiên quét')),
        )
        self.tables: dict[str, QTreeWidget] = {}
        for kind, title, headers in definitions:
            table = QTreeWidget(tabs)
            table.setObjectName('dashboardTable_' + kind)
            table.setHeaderLabels(list(headers))
            table.setRootIsDecorated(False)
            table.setUniformRowHeights(True)
            table.setAlternatingRowColors(True)
            table.setSelectionMode(QTreeWidget.SingleSelection)
            table.setHorizontalScrollBarPolicy(Qt.ScrollBarAsNeeded)
            table.setTextElideMode(Qt.ElideMiddle)
            table.setMinimumHeight(120)
            table.currentItemChanged.connect(self._row_changed)
            table.header().setStretchLastSection(True)
            tabs.addTab(table, title)
            self.tables[kind] = table
        root.addWidget(tabs, 1)

        actions = QWidget(self)
        actions.setObjectName('dashboardActions')
        footer = QHBoxLayout(actions)
        footer.setContentsMargins(14, 7, 14, 9)
        footer.setSpacing(8)
        self.create_specimen_button = QPushButton('+ Thêm vật mẫu', actions)
        self.create_specimen_button.setObjectName('dashboardCreateSpecimen')
        self.create_specimen_button.clicked.connect(self.create_specimen_requested.emit)
        footer.addWidget(self.create_specimen_button)
        self.create_session_button = QPushButton('+ Tạo phiên quét', actions)
        self.create_session_button.setObjectName('dashboardCreateSession')
        self.create_session_button.clicked.connect(self.create_session_requested.emit)
        footer.addWidget(self.create_session_button)
        footer.addStretch(1)
        root.addWidget(actions)
        self._trees = ()
        self._project_for: dict[SelectionRef, SelectionRef] = {}
        self._selection: SelectionRef | None = None
        self._visible_project_ref: SelectionRef | None = None
        self._updating = False
        self.set_controls(False, None, False)
        self._set_projects(())

    def _separator(self, name: str) -> QFrame:
        line = QFrame(self)
        line.setObjectName(name)
        line.setFixedHeight(1)
        return line

    def _set_projects(self, trees) -> None:
        self._updating = True
        self.project_combo.clear()
        self.project_combo.addItem('Chọn dự án…', None)
        for tree in trees:
            p = tree.project
            self.project_combo.addItem(
                f'{p.storage.public_code or "Chưa cấp mã"} · {p.name}',
                SelectionRef('project', p.project_id),
            )
        self.project_combo.setCurrentIndex(0)
        self._updating = False

    def _combo_changed(self, index: int) -> None:
        if not self._updating and index > 0:
            selection = self.project_combo.itemData(index)
            if selection is not None:
                self.selected.emit(selection)

    def _row_changed(self, item: QTreeWidgetItem | None, _previous) -> None:
        if not self._updating and item is not None:
            selection = item.data(0, Qt.UserRole)
            if selection is not None:
                self.selected.emit(selection)

    def show_bundle(self, bundle) -> None:
        self._trees = bundle.trees
        self._project_for.clear()
        for tree in self._trees:
            project = SelectionRef('project', tree.project.project_id)
            self._project_for[project] = project
            for node in tree.specimens:
                spec_ref = SelectionRef('specimen', node.specimen.specimen_id)
                self._project_for[spec_ref] = project
                for session in node.sessions:
                    session_ref = SelectionRef('scan_session', session.session_id)
                    self._project_for[session_ref] = project
                    for cap in session.captures:
                        self._project_for[SelectionRef('capture', cap.capture_id)] = project
                    for run in session.processing_runs:
                        self._project_for[SelectionRef('processing_run', run.run_id)] = project
        self.store_label.setText(f'Kho: {Path(bundle.info.root).name} · SQLite v{bundle.info.schema_version}')
        self.store_label.setToolTip(bundle.info.root)
        self._set_projects(self._trees)
        self._visible_project_ref = None
        self._populate_project(None)
        self.set_selection(None)
        self.show()

    def reset(self) -> None:
        self._trees = ()
        self._project_for.clear()
        self._set_projects(())
        self._clear_tables()
        self._selection = None
        self._visible_project_ref = None
        self.hide()

    def _clear_tables(self) -> None:
        self._updating = True
        for table in self.tables.values():
            table.clear()
        self._updating = False

    def set_selection(self, selection: SelectionRef | None) -> None:
        self._selection = selection
        project_ref = self._project_for.get(selection)
        self._updating = True
        index = next((i for i in range(1, self.project_combo.count())
                      if self.project_combo.itemData(i) == project_ref), 0)
        self.project_combo.setCurrentIndex(index)
        self._updating = False
        if project_ref != self._visible_project_ref:
            self._populate_project(project_ref)
            self._visible_project_ref = project_ref
        self._updating = True
        for table in self.tables.values():
            for i in range(table.topLevelItemCount()):
                item = table.topLevelItem(i)
                if item.data(0, Qt.UserRole) == selection:
                    table.setCurrentItem(item)
                    break
        self._updating = False

    def _populate_project(self, project_ref: SelectionRef | None) -> None:
        self._clear_tables()
        if project_ref is None:
            self.stats_label.setText('Chọn dự án để xem vật mẫu, phiên quét và dữ liệu liên quan.')
            return
        tree = next((t for t in self._trees if t.project.project_id == project_ref.entity_id), None)
        if tree is None:
            return
        specs = len(tree.specimens)
        sessions = sum(len(n.sessions) for n in tree.specimens)
        captures = sum(len(s.captures) for n in tree.specimens for s in n.sessions)
        runs = sum(len(s.processing_runs) for n in tree.specimens for s in n.sessions)
        self.stats_label.setText(
            f'Vật mẫu: {specs}   ·   Phiên quét: {sessions}   ·   Bản thu: {captures}   ·   Lần xử lý: {runs}'
        )
        self._updating = True
        try:
            for node in tree.specimens:
                spec = node.specimen
                self._item('specimen', (
                    spec.storage.public_code or 'Chưa cấp mã', spec.label, str(len(node.sessions))
                ), SelectionRef('specimen', spec.specimen_id))
                for session in node.sessions:
                    code = session.storage.public_code or 'Chưa cấp mã'
                    self._item('scan_session', (code, session.label,
                               'Đang mở' if session.state == 'open' else 'Đã đóng', spec.label),
                               SelectionRef('scan_session', session.session_id))
                    for cap in session.captures:
                        self._item('capture', (cap.storage.public_code or 'Chưa cấp mã',
                                              cap.kind, session.label),
                                   SelectionRef('capture', cap.capture_id))
                    for run in session.processing_runs:
                        self._item('processing_run', (run.storage.public_code or 'Chưa cấp mã',
                                                     run.stage, run.state, session.label),
                                   SelectionRef('processing_run', run.run_id))
        finally:
            self._updating = False

    def _item(self, kind: str, columns: tuple[str, ...], selection: SelectionRef) -> None:
        item = QTreeWidgetItem(self.tables[kind], list(columns))
        item.setData(0, Qt.UserRole, selection)
        for column, value in enumerate(columns):
            item.setToolTip(column, value)

    def set_controls(self, writable: bool, selection: SelectionRef | None, busy: bool) -> None:
        self.change_button.setEnabled(not busy)
        self.create_project_button.setEnabled(writable and not busy)
        self.create_specimen_button.setEnabled(writable and not busy and selection is not None
                                               and selection.entity_type == 'project')
        self.create_session_button.setEnabled(writable and not busy and selection is not None
                                              and selection.entity_type == 'specimen')


class ProjectDashboardPresenter:
    """Signal-only integration with existing loader/writer/Explorer; no new DB client."""

    def __init__(self, view, controller) -> None:
        self.view = view
        self.controller = controller
        self.panel = ProjectDashboard()
        store = controller.recent_stores.panel
        scroll = view._pages[WorkspaceId.PROJECTS].findChild(QWidget, 'workspaceScrollContent')
        if scroll is None:
            raise RuntimeError('Project workspace scroll host missing')
        scroll.layout().insertWidget(4, self.panel)
        self.panel.hide()
        self.panel.selected.connect(self._select_explorer)
        self.panel.change_store_requested.connect(self._show_store_chooser)
        self.panel.create_project_requested.connect(controller._create_project)
        self.panel.create_specimen_requested.connect(controller._create_specimen)
        self.panel.create_session_requested.connect(controller._create_session)
        controller.project_loader.loaded.connect(self._on_loaded)
        controller.project_loader.failed.connect(self._on_failed)
        controller.project_loader.busy_changed.connect(self._on_busy)
        controller.project_writer.busy_changed.connect(self._update_actions)
        view.project_explorer.selection_changed.connect(self._on_selection)
        self._store = store

    def _on_loaded(self, bundle) -> None:
        self.panel.show_bundle(bundle)
        # 07.5 may have reselected the newly created item before this signal
        # reaches the dashboard; recover that existing authoritative selection.
        self.panel.set_selection(self.view.project_explorer.selection)
        self._store.hide()
        self._update_actions()

    def _on_failed(self, _message: str) -> None:
        self.panel.reset()
        self._store.show()
        self._update_actions()

    def _show_store_chooser(self) -> None:
        self.panel.hide()
        self._store.show()

    def _on_busy(self, busy: bool) -> None:
        # A new store load must not leave an old store dashboard onscreen.
        if busy:
            self.panel.reset()
            self._store.show()
        self._update_actions()

    def _update_actions(self, *_args) -> None:
        self.panel.set_controls(
            self.controller._can_write_project(), self.view.project_explorer.selection,
            self.controller.project_loader.busy or self.controller.project_writer.busy,
        )

    def _on_selection(self, selection) -> None:
        self.panel.set_selection(selection)
        self._update_actions()

    def _select_explorer(self, selection: SelectionRef) -> None:
        tree = self.view.project_explorer.tree
        def walk(node):
            if node.data(0, Qt.UserRole) == selection:
                return node
            for i in range(node.childCount()):
                found = walk(node.child(i))
                if found is not None:
                    return found
            return None
        for i in range(tree.topLevelItemCount()):
            target = walk(tree.topLevelItem(i))
            if target is not None:
                tree.setCurrentItem(target)
                return
