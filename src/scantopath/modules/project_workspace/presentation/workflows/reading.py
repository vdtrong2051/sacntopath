"""Single Project Workspace view workflow; QObject lifecycle owned by feature controller."""
from __future__ import annotations
from PySide6.QtCore import Qt
from scantopath.ui.components import ExplorerNode
from scantopath.ui.projects.controller import ProjectLoadController
from .base import _Coordinator

class _ProjectReadCoordinator(_Coordinator):
    def _install_project_loader(self) -> None:
        """Qt-main-thread bridge for explicitly chosen, existing SQLite stores."""
        self.project_loader = ProjectLoadController(self._owner)
        self._project_root: str | None = None
        self._project_fields: dict[object, tuple[tuple[str, str], ...]] = {}
        self._project_entities: dict[object, object] = {}
        self._project_owners: dict[object, str] = {}
        self._project_schema: int | None = None
        self._pending_selection = None
        self._write_refresh_pending = False
        self._project_closing = False
        self.view.project_explorer.open_requested.connect(self._choose_project_store)
        self.view.project_explorer.refresh_requested.connect(self._reload_project_store)
        self.project_loader.loaded.connect(self._on_project_loaded)
        self.project_loader.failed.connect(self._on_project_failed)
        self.project_loader.busy_changed.connect(self._on_project_busy)
        self.project_loader.stopped.connect(self.view.close)

    def _choose_project_store(self) -> None:
        if self.project_loader.busy or self.project_writer.busy or self.capture_checker.busy:
            return
        root = self.view._select_project_store(self._project_root)
        if root:
            self._begin_project_load(root)

    def _reload_project_store(self) -> None:
        if (self._project_root is not None and not self.project_writer.busy
                and not self.capture_checker.busy):
            # Keep pending selections from writes; otherwise restore any node.
            if self._pending_selection is None:
                selected = self.view.project_explorer.selection
                if selected is not None:
                    self._pending_selection = selected
            self._begin_project_load(self._project_root)

    def _begin_project_load(self, root: str) -> None:
        if (self.project_loader.busy or self.project_writer.busy or
                self.capture_checker.busy or self._project_closing):
            return
        # Save a previously rendered RAW identity BEFORE set_nodes clears
        # the Explorer and invalidates the CapturePreview selection.
        capture_preview = getattr(self.view, "capture_preview", None)
        if capture_preview is not None:
            capture_preview.prepare_store_reload(root)
        if hasattr(self.view, "workflow_context"):
            self.view.workflow_context.begin_store_load(root)
        # Do not carry a Capture selection across DIFFERENT stores.
        if self._project_root is not None and root != self._project_root:
            self._pending_selection = None
        # Do not display stale objects from a previously selected data root.
        self.view.project_explorer.set_nodes(())
        self._project_fields.clear()
        self.view.task_event_panel.set_audit_events(())
        self._project_entities.clear()
        self._project_owners.clear()
        self._project_schema = None
        self.view.property_inspector.set_selection(None)
        self.view.project_explorer.clear_selection()
        self._project_root = None
        self.view.project_explorer.show_store(None)
        self._update_project_actions()
        self.view.data_status.setText("Dữ liệu: Đang tải")
        if not self.project_loader.load(root):
            self._on_project_failed("Đang có thao tác tải kho dữ liệu khác.")

    def _on_project_busy(self, busy: bool) -> None:
        self.view.project_explorer.set_busy(busy)
        self._update_project_actions()

    def _on_project_loaded(self, bundle: object) -> None:
        """Called in GUI thread; the worker only passes immutable DTO records."""
        # Lazy import: startup/import UI must not load metadata/SQLite modules.
        from ..presenter import project_rows
        self._project_root = bundle.info.root
        self._project_schema = bundle.info.schema_version
        rows = project_rows(bundle.trees)
        self.view.task_event_panel.set_audit_events(bundle.audit_events)
        self._project_fields.clear()
        self._project_entities.clear()
        self._project_owners.clear()
        from scantopath.application.contracts import SelectionRef
        for tree in bundle.trees:
            self._project_entities[SelectionRef("project", tree.project.project_id)] = tree.project
            for specimen_node in tree.specimens:
                specimen = specimen_node.specimen
                spec_ref = SelectionRef("specimen", specimen.specimen_id)
                self._project_entities[spec_ref] = specimen
                self._project_owners[spec_ref] = specimen.project_id
                for session in specimen_node.sessions:
                    session_ref = SelectionRef("scan_session", session.session_id)
                    self._project_entities[session_ref] = session
                    self._project_owners[session_ref] = specimen.specimen_id

        def convert(row) -> ExplorerNode:
            self._project_fields[row.selection] = row.fields
            return ExplorerNode(row.title, row.selection, tuple(convert(c) for c in row.children))

        if self._pending_selection is None and hasattr(self.view, "workflow_context"):
            self._pending_selection = self.view.workflow_context.restore_candidate(bundle.info.root)
        self.view.project_explorer.set_nodes(tuple(convert(r) for r in rows))
        for index in range(self.view.project_explorer.tree.topLevelItemCount()):
            self.view.project_explorer.tree.topLevelItem(index).setExpanded(True)
        self.view.project_explorer.show_store(bundle.info.root, schema_version=bundle.info.schema_version)
        if self._pending_selection is not None:
            wanted = self._pending_selection
            self._pending_selection = None
            self.view.project_explorer.select_ref(wanted)
        self._update_project_actions()
        if not rows:
            self.view.project_explorer.show_message("Kho SQLite hợp lệ nhưng chưa có dự án.")
        self.view.data_status.setText(f"Dữ liệu: {len(rows)} dự án · SQLite v{bundle.info.schema_version}")
        self.view._set_status(f"Đã tải {len(rows)} dự án từ kho SQLite đã chọn.")
        self.view.task_event_panel.add_ui_event("Đã tải cây dự án từ kho SQLite được chọn.")

    def _on_project_failed(self, message: str) -> None:
        self._project_root = None
        self._project_schema = None
        self._project_fields.clear()
        self.view.task_event_panel.set_audit_events(())
        self._project_entities.clear()
        self._project_owners.clear()
        self._pending_selection = None
        self.view.project_explorer.set_nodes(())
        self.view.project_explorer.show_store(None)
        self.view.project_explorer.show_message(message)
        self.view.property_inspector.set_selection(None)
        self.view.data_status.setText("Dữ liệu: Chưa tải")
        self.view._set_status(message)
        self._update_project_actions()

    def _on_explorer_selection(self, selection: object) -> None:
        """SelectionRef là tham chiếu, không phải phép đo hoặc metadata đã nạp."""
        self.view.navigation.select_entity(selection)
        self.view.property_inspector.set_selection(selection)
        if selection is not None and selection in self._project_fields:
            self.view.property_inspector.set_store_fields(self._project_fields[selection])
        self._update_project_actions()
        if selection is not None:
            self.view._set_status(f"Đã chọn đối tượng: {selection.entity_id}")
