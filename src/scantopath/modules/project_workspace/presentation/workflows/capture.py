"""Single Project Workspace view workflow; QObject lifecycle owned by feature controller."""
from __future__ import annotations
from scantopath.ui.projects.inspection_controller import CaptureInspectionController
from .base import _Coordinator

class _CaptureReviewCoordinator(_Coordinator):
    def _install_capture_checker(self) -> None:
        self.capture_checker = CaptureInspectionController(self._owner)
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
