"""07.10: ProjectWorkspace presentation controller (MVC coordination).

Owns read/write/integrity workers, selection state and UI event orchestration.
Does not open SQLite on import or on creation: persistence remains lazy/opt-in.
UI shell composes this controller; it only owns navigation, docking and lifetime.
"""
from __future__ import annotations

from PySide6.QtCore import QObject, Qt
from PySide6.QtWidgets import QDialog, QMessageBox

from scantopath.ui.components import ExplorerNode
from scantopath.ui.projects.controller import ProjectLoadController
from scantopath.ui.projects.write_controller import ProjectWriteController
from scantopath.ui.projects.inspection_controller import CaptureInspectionController
from .forms_contract import ProjectEditCommand
from .edit_dialog import ProjectEditDialog


class ProjectWorkspaceController(QObject):
    """Feature controller; View is the supplied main window composition context."""

    def __init__(self, view) -> None:
        super().__init__(view)
        self.view = view
        self._install_project_loader()
        self._install_project_writer()
        self._install_capture_checker()

    def _install_project_loader(self) -> None:
        """Qt-main-thread bridge for explicitly chosen, existing SQLite stores."""
        self.project_loader = ProjectLoadController(self)
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

    def _install_project_writer(self) -> None:
        self.project_writer = ProjectWriteController(self)
        self.project_writer.completed.connect(self._on_project_written)
        self.project_writer.failed.connect(self._on_project_write_failed)
        self.project_writer.busy_changed.connect(self._on_project_write_busy)
        self.project_writer.stopped.connect(self.view.close)
        self.view.project_explorer.create_project_requested.connect(self._create_project)
        self.view.project_explorer.create_specimen_requested.connect(self._create_specimen)
        self.view.project_explorer.create_session_requested.connect(self._create_session)
        self.view.property_inspector.edit_requested.connect(self._edit_selected_metadata)
        self.view.property_inspector.close_session_requested.connect(self._close_selected_session)

    def _install_capture_checker(self) -> None:
        self.capture_checker = CaptureInspectionController(self)
        self.capture_checker.checked.connect(self._on_capture_checked)
        self.capture_checker.failed.connect(self._on_capture_check_failed)
        self.capture_checker.busy_changed.connect(self._on_capture_busy)
        self.capture_checker.stopped.connect(self.view.close)
        self.view.property_inspector.verify_capture_requested.connect(self._verify_selected_capture)

    def _verify_selected_capture(self) -> None:
        selection = self.view.project_explorer.selection
        if (selection is None or selection.entity_type != "capture" or
                selection not in self._project_fields or self._project_root is None or
                self.project_loader.busy or self.project_writer.busy or
                self.capture_checker.busy or self._project_closing):
            return
        if self.capture_checker.inspect(self._project_root, selection.entity_id):
            self.view._set_status("Đang kiểm tra RAW trong luồng nền…")

    def _on_capture_checked(self, result: object) -> None:
        selection = self.view.project_explorer.selection
        if selection is None or selection.entity_type != "capture" or selection.entity_id != result.capture_id:
            return
        self.view.property_inspector.set_capture_inspection(result.status, result.message)
        self.view._set_status(result.message)
        self.view.task_event_panel.add_ui_event("Kiểm tra RAW theo yêu cầu: " + result.status)

    def _on_capture_check_failed(self, message: str) -> None:
        self.view._set_status(message)
        self.view.task_event_panel.add_ui_event(message)

    def _on_capture_busy(self, busy: bool) -> None:
        self._update_project_actions()
        self.view.project_explorer.open_button.setEnabled(
            not busy and not self.project_loader.busy and not self.project_writer.busy)
        self.view.project_explorer.refresh_button.setEnabled(
            not busy and not self.project_loader.busy and not self.project_writer.busy
            and self._project_root is not None)

    def _can_write_project(self) -> bool:
        return (self._project_root is not None and self._project_schema == 2
                and not self.project_loader.busy and not self.project_writer.busy
                and not self._project_closing and not self.capture_checker.busy)

    def _update_project_actions(self) -> None:
        chosen = self.view.project_explorer.selection
        can = self._can_write_project()
        kind = chosen.entity_type if chosen is not None and chosen in self._project_entities else None
        self.view.project_explorer.set_write_capabilities(can, kind)
        entity = self._project_entities.get(chosen)
        self.view.property_inspector.set_actions(
            can_edit=can and kind in ("project", "specimen", "scan_session"),
            can_close_session=can and kind == "scan_session" and entity is not None
                and entity.state == "open",
        )
        self.view.property_inspector.set_verify_capability(
            chosen is not None and chosen.entity_type == "capture"
            and chosen in self._project_fields and self._project_root is not None
            and not self.project_loader.busy and not self.project_writer.busy
            and not self.capture_checker.busy and not self._project_closing
        )

    def _dialog_command(self, kind: str, *, create: bool, initial: object | None = None,
                        target_id: str | None = None, parent_id: str | None = None,
                        project_id: str | None = None) -> None:
        if not self._can_write_project():
            self.view._set_status("Chỉ được ghi khi đã mở kho SQLite v2 và không có tác vụ đang chạy.")
            return
        current_name = "" if initial is None else (
            initial.name if kind == "project" else initial.label
        )
        current_description = "" if initial is None or kind == "session" else initial.description
        dialog = ProjectEditDialog(kind=kind, create=create, name=current_name,
                                   description=current_description, parent=self.view)
        if dialog.exec() != QDialog.Accepted:
            return
        name, description = dialog.values()
        command = ProjectEditCommand(
            action=f"{kind}.{'create' if create else 'update'}",
            name=name, description=description, target_id=target_id,
            parent_id=parent_id, project_id=project_id,
        )
        self._submit_project_write(command)

    def _create_project(self) -> None:
        self._dialog_command("project", create=True)

    def _create_specimen(self) -> None:
        selection = self.view.project_explorer.selection
        if selection is None or selection.entity_type != "project" or selection not in self._project_entities:
            return
        self._dialog_command("specimen", create=True, parent_id=selection.entity_id)

    def _create_session(self) -> None:
        selection = self.view.project_explorer.selection
        if selection is None or selection.entity_type != "specimen" or selection not in self._project_entities:
            return
        self._dialog_command("session", create=True, parent_id=selection.entity_id)

    def _edit_selected_metadata(self) -> None:
        selection = self.view.project_explorer.selection
        if selection is None or selection not in self._project_entities:
            return
        kind = "session" if selection.entity_type == "scan_session" else selection.entity_type
        if kind not in ("project", "specimen", "session"):
            return
        parent_id = self._project_owners.get(selection)
        self._dialog_command(
            kind, create=False, initial=self._project_entities[selection],
            target_id=selection.entity_id, parent_id=parent_id if kind == "session" else (
                parent_id if kind == "specimen" else None),
            project_id=parent_id if kind == "specimen" else None,
        )

    def _close_selected_session(self) -> None:
        selection = self.view.project_explorer.selection
        if selection is None or selection.entity_type != "scan_session":
            return
        entity = self._project_entities.get(selection)
        if not self._can_write_project() or entity is None or entity.state != "open":
            return
        if QMessageBox.question(
            self.view, "Đóng phiên quét", "Đóng phiên quét đã chọn? Sau khi đóng, không thể đăng ký bản thu mới vào phiên này.",
            QMessageBox.Yes | QMessageBox.No, QMessageBox.No,
        ) != QMessageBox.Yes:
            return
        self._submit_project_write(ProjectEditCommand(
            action="session.close", target_id=selection.entity_id,
            parent_id=self._project_owners[selection],
        ))

    def _submit_project_write(self, command: ProjectEditCommand) -> None:
        if not self._can_write_project():
            self.view._set_status("Kho chưa sẵn sàng ghi dữ liệu.")
            return
        if not self.project_writer.submit(self._project_root, command):
            self.view._set_status("Đang có thao tác khác trên kho dự án.")

    def _on_project_written(self, result: object) -> None:
        from scantopath.application.contracts import SelectionRef
        self._pending_selection = SelectionRef(result.entity_type, result.entity_id)
        self._write_refresh_pending = True
        if result.numbering_pending:
            self.view._set_status(
                f"Metadata đã lưu với ID {result.entity_id}, nhưng cấp mã chưa xong. "
                "KHÔNG tạo lại; dùng chức năng cấp mã 07.2 để khôi phục."
            )
            self.view.task_event_panel.add_ui_event("Lưu metadata thành công nhưng cấp mã đang chờ khôi phục.")
        else:
            self.view._set_status(f"Đã lưu metadata: {result.public_code or result.entity_id}")
            self.view.task_event_panel.add_ui_event("Đã cập nhật metadata của kho dự án.")

    def _on_project_write_failed(self, message: str) -> None:
        self._write_refresh_pending = True  # May have committed a partial state.
        self._pending_selection = None
        self.view._set_status(message)
        self.view.task_event_panel.add_ui_event(message)

    def _on_project_write_busy(self, busy: bool) -> None:
        self._update_project_actions()
        # A reader and writer must never run against the same store concurrently.
        self.view.project_explorer.open_button.setEnabled(
            not busy and not self.project_loader.busy and not self.capture_checker.busy)
        self.view.project_explorer.refresh_button.setEnabled(
            not busy and not self.project_loader.busy and not self.capture_checker.busy
            and self._project_root is not None
        )
        if not busy and self._write_refresh_pending and not self._project_closing:
            self._write_refresh_pending = False
            self._reload_project_store()

    def _choose_project_store(self) -> None:
        if self.project_loader.busy or self.project_writer.busy or self.capture_checker.busy:
            return
        root = self.view._select_project_store(self._project_root)
        if root:
            self._begin_project_load(root)

    def _reload_project_store(self) -> None:
        if (self._project_root is not None and not self.project_writer.busy
                and not self.capture_checker.busy):
            self._begin_project_load(self._project_root)

    def _begin_project_load(self, root: str) -> None:
        if (self.project_loader.busy or self.project_writer.busy or
                self.capture_checker.busy or self._project_closing):
            return
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
        from .presenter import project_rows
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

        self.view.project_explorer.set_nodes(tuple(convert(r) for r in rows))
        for index in range(self.view.project_explorer.tree.topLevelItemCount()):
            self.view.project_explorer.tree.topLevelItem(index).setExpanded(True)
        self.view.project_explorer.show_store(bundle.info.root, schema_version=bundle.info.schema_version)
        if self._pending_selection is not None:
            wanted = self._pending_selection
            self._pending_selection = None
            def find(items, selection):
                for entry in items:
                    if entry.data(0, Qt.UserRole) == selection:
                        return entry
                    found = find((entry.child(i) for i in range(entry.childCount())), selection)
                    if found is not None:
                        return found
                return None
            node = find((self.view.project_explorer.tree.topLevelItem(i)
                         for i in range(self.view.project_explorer.tree.topLevelItemCount())), wanted)
            if node is not None:
                self.view.project_explorer.tree.setCurrentItem(node)
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
