"""Single Project Workspace view workflow; QObject lifecycle owned by feature controller."""
from __future__ import annotations
from PySide6.QtWidgets import QDialog, QMessageBox
from scantopath.ui.projects.write_controller import ProjectWriteController
from ..forms_contract import ProjectEditCommand
from ..edit_dialog import ProjectEditDialog
from .base import _Coordinator

class _ProjectWriteCoordinator(_Coordinator):
    def _install_project_writer(self) -> None:
        self.project_writer = ProjectWriteController(self._owner)
        self.project_writer.completed.connect(self._on_project_written)
        self.project_writer.failed.connect(self._on_project_write_failed)
        self.project_writer.busy_changed.connect(self._on_project_write_busy)
        self.project_writer.stopped.connect(self.view.close)
        self.view.project_explorer.create_project_requested.connect(self._create_project)
        self.view.project_explorer.create_specimen_requested.connect(self._create_specimen)
        self.view.project_explorer.create_session_requested.connect(self._create_session)
        self.view.project_explorer.delete_empty_requested.connect(self._delete_selected_empty)
        self.view.property_inspector.edit_requested.connect(self._edit_selected_metadata)
        self.view.property_inspector.close_session_requested.connect(self._close_selected_session)

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

    def _delete_selected_empty(self) -> None:
        selection = self.view.project_explorer.selection
        if not self._can_write_project() or selection not in self._project_entities:
            return
        kind = selection.entity_type
        if kind not in ("project", "specimen", "scan_session"):
            return
        if QMessageBox.question(
            self.view, "Xóa đối tượng trống",
            "Chỉ xóa metadata của đối tượng KHÔNG có dữ liệu con và không có thư mục vật lý. "
            "Không xóa Capture/RAW. Bạn có muốn tiếp tục?",
            QMessageBox.Yes | QMessageBox.No, QMessageBox.No,
        ) != QMessageBox.Yes:
            return
        self._submit_project_write(ProjectEditCommand(
            action=("session.delete" if kind == "scan_session" else kind + ".delete"),
            target_id=selection.entity_id,
            parent_id=self._project_owners.get(selection),
        ))

    def _submit_project_write(self, command: ProjectEditCommand) -> None:
        if not self._can_write_project():
            self.view._set_status("Kho chưa sẵn sàng ghi dữ liệu.")
            return
        if not self.project_writer.submit(self._project_root, command):
            self.view._set_status("Đang có thao tác khác trên kho dự án.")

    def _on_project_written(self, result: object) -> None:
        from scantopath.application.contracts import SelectionRef
        self._pending_selection = (None if result.action.endswith(".delete")
                                   else SelectionRef(result.entity_type, result.entity_id))
        self._write_refresh_pending = True
        if result.numbering_pending:
            self.view._set_status(
                f"Metadata đã lưu với ID {result.entity_id}, nhưng cấp mã chưa xong. "
                "KHÔNG tạo lại; dùng chức năng cấp mã 07.2 để khôi phục."
            )
            self.view.task_event_panel.add_ui_event("Lưu metadata thành công nhưng cấp mã đang chờ khôi phục.")
        else:
            self.view._set_status(
                f"Đã xóa metadata trống: {result.entity_id}" if result.action.endswith(".delete")
                else f"Đã lưu metadata: {result.public_code or result.entity_id}"
            )
            self.view.task_event_panel.add_ui_event(
                "Đã xóa đối tượng trống có kiểm soát." if result.action.endswith(".delete")
                else "Đã cập nhật metadata của kho dự án."
            )

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
