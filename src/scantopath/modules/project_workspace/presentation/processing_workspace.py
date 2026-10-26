"""R3.4 -- read-only ProcessingRun workspace, backed by the existing Project DTO load.

The Explorer remains the single selection authority. No SQLite, filesystem
probe, RAW verification, algorithm execution, or implicit database open here.
"""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QAbstractItemView, QComboBox, QFrame, QHBoxLayout, QLabel, QTreeWidget,
    QTreeWidgetItem, QVBoxLayout, QWidget,
)

from scantopath.application.contracts import SelectionRef, WorkspaceId
from scantopath.modules.project_workspace.application.models import ProjectTree, ProcessingRunSummary


@dataclass(frozen=True, slots=True)
class ProcessingEntry:
    ref: SelectionRef
    project_ref: SelectionRef
    project_name: str
    specimen_name: str
    session_name: str
    run: ProcessingRunSummary


def flatten_processing_runs(trees: tuple[ProjectTree, ...]) -> tuple[ProcessingEntry, ...]:
    """Pure DTO flattening. Never manufacture or execute a ProcessingRun."""
    results: list[ProcessingEntry] = []
    for tree in trees:
        parent = SelectionRef("project", tree.project.project_id)
        for specimen in tree.specimens:
            for session in specimen.sessions:
                for run in session.processing_runs:
                    results.append(ProcessingEntry(
                        ref=SelectionRef("processing_run", run.run_id),
                        project_ref=parent,
                        project_name=tree.project.name,
                        specimen_name=specimen.specimen.label,
                        session_name=session.label,
                        run=run,
                    ))
    return tuple(results)


_STATES = {
    "pending": "Chờ xử lý", "queued": "Đang chờ", "running": "Đang chạy",
    "succeeded": "Hoàn thành", "failed": "Thất bại", "cancelled": "Đã hủy",
}


def _state(value: str) -> str:
    return _STATES.get(value, value)


class ProcessingWorkspace(QFrame):
    """Compact filter, real ProcessingRun table and contextual read-only details."""

    selected = Signal(object)

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("processingWorkspace")
        self.setAccessibleName("Danh sách lần xử lý đã ghi nhận")
        self._entries: tuple[ProcessingEntry, ...] = ()
        self._by_ref: dict[SelectionRef, ProcessingEntry] = {}
        self._updating = False
        self._selection: SelectionRef | None = None

        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        header = QWidget(self)
        header.setObjectName("processingHeader")
        heading_row = QHBoxLayout(header)
        heading_row.setContentsMargins(13, 9, 13, 9)
        self.heading = QLabel("LẦN XỬ LÝ", header)
        self.heading.setObjectName("processingHeading")
        heading_row.addWidget(self.heading)
        heading_row.addStretch(1)
        self.count_label = QLabel("Chưa mở kho", header)
        self.count_label.setObjectName("processingCount")
        heading_row.addWidget(self.count_label)
        root.addWidget(header)
        root.addWidget(self._separator("processingHeaderSeparator"))

        filter_area = QWidget(self)
        filter_area.setObjectName("processingFilters")
        filters = QHBoxLayout(filter_area)
        filters.setContentsMargins(13, 8, 13, 8)
        filters.setSpacing(9)
        filters.addWidget(QLabel("Dự án", filter_area))
        self.project_filter = QComboBox(filter_area)
        self.project_filter.setObjectName("processingProjectFilter")
        self.project_filter.setMinimumWidth(135)
        self.project_filter.setMinimumContentsLength(12)
        self.project_filter.currentIndexChanged.connect(self._rebuild_table)
        filters.addWidget(self.project_filter, 2)
        filters.addWidget(QLabel("Trạng thái", filter_area))
        self.state_filter = QComboBox(filter_area)
        self.state_filter.setObjectName("processingStateFilter")
        self.state_filter.addItem("Tất cả", None)
        self.state_filter.currentIndexChanged.connect(self._rebuild_table)
        filters.addWidget(self.state_filter, 1)
        root.addWidget(filter_area)
        root.addWidget(self._separator("processingFilterSeparator"))

        self.table = QTreeWidget(self)
        self.table.setObjectName("processingRunTable")
        self.table.setHeaderLabels(["Mã", "Công đoạn", "Trạng thái", "Phiên quét", "Tạo lúc (UTC)"])
        self.table.setRootIsDecorated(False)
        self.table.setUniformRowHeights(True)
        self.table.setAlternatingRowColors(True)
        self.table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.table.setSelectionMode(QAbstractItemView.SingleSelection)
        self.table.setTextElideMode(Qt.ElideMiddle)
        self.table.setHorizontalScrollBarPolicy(Qt.ScrollBarAsNeeded)
        self.table.header().setStretchLastSection(True)
        self.table.setColumnWidth(0, 85)
        self.table.setColumnWidth(1, 160)
        self.table.setColumnWidth(2, 115)
        self.table.setColumnWidth(3, 145)
        self.table.currentItemChanged.connect(self._on_row_change)
        self.table.setMinimumHeight(115)
        root.addWidget(self.table, 3)

        self.empty_label = QLabel("Chưa mở kho dữ liệu. Không có lần xử lý để hiển thị.", self)
        self.empty_label.setObjectName("processingEmpty")
        self.empty_label.setWordWrap(True)
        root.addWidget(self.empty_label)
        root.addWidget(self._separator("processingDetailSeparator"))

        detail_header = QWidget(self)
        detail_header.setObjectName("processingDetailHeader")
        detail_row = QHBoxLayout(detail_header)
        detail_row.setContentsMargins(13, 5, 13, 5)
        detail_title = QLabel("CHI TIẾT ĐƯỢC GHI NHẬN", detail_header)
        detail_title.setObjectName("processingDetailHeading")
        detail_row.addWidget(detail_title)
        detail_row.addStretch(1)
        root.addWidget(detail_header)

        self.details = QTreeWidget(self)
        self.details.setObjectName("processingRunDetails")
        self.details.setHeaderLabels(["Thuộc tính", "Giá trị"])
        self.details.setRootIsDecorated(False)
        self.details.setUniformRowHeights(True)
        self.details.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.details.setTextElideMode(Qt.ElideMiddle)
        self.details.setColumnWidth(0, 155)
        self.details.header().setStretchLastSection(True)
        self.details.setMinimumHeight(90)
        root.addWidget(self.details, 2)

        self.note = QLabel("Đầu ra là đường dẫn tham chiếu; chưa xác minh sự tồn tại hoặc chất lượng hình học.", self)
        self.note.setObjectName("processingSourceNote")
        self.note.setWordWrap(True)
        root.addWidget(self.note)
        self.setMinimumHeight(315)
        self._set_initial_filters()

    def _separator(self, name: str) -> QFrame:
        line = QFrame(self)
        line.setObjectName(name)
        line.setFixedHeight(1)
        return line

    def _set_initial_filters(self) -> None:
        self._updating = True
        try:
            self.project_filter.clear()
            self.project_filter.addItem("Tất cả dự án", None)
            self.state_filter.clear()
            self.state_filter.addItem("Tất cả", None)
        finally:
            self._updating = False

    def show_bundle(self, bundle) -> None:
        """Consume the *already validated* load bundle on the UI thread."""
        self._entries = flatten_processing_runs(bundle.trees)
        self._by_ref = {entry.ref: entry for entry in self._entries}
        self._selection = None
        self._updating = True
        try:
            self.project_filter.clear()
            self.project_filter.addItem("Tất cả dự án", None)
            for tree in bundle.trees:
                code = tree.project.storage.public_code or "Chưa cấp mã"
                self.project_filter.addItem(
                    f"{code} · {tree.project.name}", tree.project.project_id
                )
            self.state_filter.clear()
            self.state_filter.addItem("Tất cả", None)
            for state in sorted({entry.run.state for entry in self._entries}):
                self.state_filter.addItem(_state(state), state)
        finally:
            self._updating = False
        self.count_label.setText(f"{len(self._entries)} lần xử lý · SQLite v{bundle.info.schema_version}")
        self._rebuild_table()

    def reset(self) -> None:
        self._entries = ()
        self._by_ref.clear()
        self._selection = None
        self._set_initial_filters()
        self._updating = True
        try:
            self.table.clear()
            self.details.clear()
        finally:
            self._updating = False
        self.count_label.setText("Chưa mở kho")
        self.empty_label.setText("Chưa mở kho dữ liệu. Không có lần xử lý để hiển thị.")
        self.empty_label.show()

    def _rebuild_table(self, *_args) -> None:
        if self._updating:
            return
        project = self.project_filter.currentData()
        state = self.state_filter.currentData()
        self._updating = True
        try:
            self.table.clear()
            matches = [e for e in self._entries if
                       (project is None or e.project_ref.entity_id == project) and
                       (state is None or e.run.state == state)]
            for entry in matches:
                run = entry.run
                values = [run.storage.public_code or "Chưa cấp mã", run.stage,
                          _state(run.state), entry.session_name, run.created_at]
                item = QTreeWidgetItem(self.table, values)
                item.setData(0, Qt.UserRole, entry.ref)
                for i, value in enumerate(values):
                    item.setToolTip(i, value)
            self.empty_label.setText(
                "Không có ProcessingRun khớp bộ lọc." if self._entries else
                "Kho đã mở nhưng chưa ghi nhận lần xử lý nào."
            )
            self.empty_label.setVisible(not matches)
            self._show_details(None)
            if self._selection is not None:
                self._select_row(self._selection)
        finally:
            self._updating = False

    def _on_row_change(self, item: QTreeWidgetItem | None, _old) -> None:
        if self._updating:
            return
        ref = item.data(0, Qt.UserRole) if item is not None else None
        self._show_details(self._by_ref.get(ref))
        if ref is not None:
            self.selected.emit(ref)

    def _show_details(self, entry: ProcessingEntry | None) -> None:
        self.details.clear()
        if entry is None:
            return
        run = entry.run
        fields = (
            ("Mã", run.storage.public_code or "Chưa cấp mã"),
            ("ID", run.run_id),
            ("Dự án", entry.project_name),
            ("Vật mẫu", entry.specimen_name),
            ("Phiên quét", entry.session_name),
            ("Công đoạn", run.stage),
            ("Thuật toán", run.algorithm),
            ("Phiên bản", run.version),
            ("Trạng thái", _state(run.state)),
            ("Đầu vào (ID Capture)", ", ".join(run.input_capture_ids) or "Chưa có"),
            ("Đầu ra (tham chiếu)", ", ".join(run.output_files) or "Chưa có"),
            ("Tham số JSON", run.parameters_json),
            ("Tạo lúc (UTC)", run.created_at),
            ("Bắt đầu (UTC)", run.started_at or "Chưa có"),
            ("Kết thúc (UTC)", run.finished_at or "Chưa có"),
            ("Lỗi", run.error_message or "Không có"),
        )
        for title, value in fields:
            item = QTreeWidgetItem(self.details, [title, value])
            item.setToolTip(1, value)

    def _select_row(self, selection: SelectionRef | None) -> None:
        for i in range(self.table.topLevelItemCount()):
            row = self.table.topLevelItem(i)
            if row.data(0, Qt.UserRole) == selection:
                self.table.setCurrentItem(row)
                self._show_details(self._by_ref.get(selection))
                return
        self.table.setCurrentItem(None)
        self._show_details(None)

    def set_selection(self, selection: SelectionRef | None) -> None:
        """Sync from the authoritative Explorer without re-emitting selection."""
        self._selection = selection
        self._updating = True
        try:
            self._select_row(selection)
        finally:
            self._updating = False


class ProcessingWorkspacePresenter:
    """Wires existing controller signals; no early access to MainWindow aliases."""

    def __init__(self, view, controller) -> None:
        self.view = view
        self.controller = controller
        self.panel = ProcessingWorkspace()
        host = view.page_for(WorkspaceId.PROCESSING).findChild(QWidget, "workspaceScrollContent")
        if host is None:
            raise RuntimeError("Processing workspace host missing")
        host.layout().insertWidget(4, self.panel)
        legacy = host.findChild(QFrame, "workspacePanel")
        if legacy is not None:
            legacy.hide()  # retain legacy objectName and action for 07.9 regression
        self.panel.selected.connect(self._select_explorer)
        controller.project_loader.loaded.connect(self._on_loaded)
        controller.project_loader.failed.connect(self._on_failed)
        controller.project_loader.busy_changed.connect(self._on_busy)
        view.project_explorer.selection_changed.connect(self.panel.set_selection)

    def _on_loaded(self, bundle) -> None:
        self.panel.show_bundle(bundle)
        self.panel.set_selection(self.view.project_explorer.selection)

    def _on_failed(self, _message: str) -> None:
        self.panel.reset()

    def _on_busy(self, busy: bool) -> None:
        if busy:
            self.panel.reset()  # never show stale results from a prior store

    def _select_explorer(self, selection: SelectionRef) -> None:
        tree = self.view.project_explorer.tree
        def find(node):
            if node.data(0, Qt.UserRole) == selection:
                return node
            for i in range(node.childCount()):
                candidate = find(node.child(i))
                if candidate is not None:
                    return candidate
            return None
        for i in range(tree.topLevelItemCount()):
            target = find(tree.topLevelItem(i))
            if target is not None:
                tree.setCurrentItem(target)
                return
