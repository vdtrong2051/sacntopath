"""Legacy ProjectWorkspace delegates extracted from the Qt composition root.

Keep the 07.10 compatibility methods available through ordinary Python MRO;
project ownership and persistence remain in ProjectWorkspaceController.
"""
from __future__ import annotations
from PySide6.QtWidgets import QFileDialog

class ProjectDelegatesMixin:
    # 07.10 compatibility delegates for pre-existing test/UI calls.
    # All project state and workflow logic live in ProjectWorkspaceController.
    def _verify_selected_capture(self, *args, **kwargs):
        return self.project_workspace._verify_selected_capture(*args, **kwargs)

    def _on_capture_checked(self, *args, **kwargs):
        return self.project_workspace._on_capture_checked(*args, **kwargs)

    def _on_capture_check_failed(self, *args, **kwargs):
        return self.project_workspace._on_capture_check_failed(*args, **kwargs)

    def _on_capture_busy(self, *args, **kwargs):
        return self.project_workspace._on_capture_busy(*args, **kwargs)

    def _can_write_project(self, *args, **kwargs):
        return self.project_workspace._can_write_project(*args, **kwargs)

    def _update_project_actions(self, *args, **kwargs):
        return self.project_workspace._update_project_actions(*args, **kwargs)

    def _dialog_command(self, *args, **kwargs):
        return self.project_workspace._dialog_command(*args, **kwargs)

    def _create_project(self, *args, **kwargs):
        return self.project_workspace._create_project(*args, **kwargs)

    def _create_specimen(self, *args, **kwargs):
        return self.project_workspace._create_specimen(*args, **kwargs)

    def _create_session(self, *args, **kwargs):
        return self.project_workspace._create_session(*args, **kwargs)

    def _edit_selected_metadata(self, *args, **kwargs):
        return self.project_workspace._edit_selected_metadata(*args, **kwargs)

    def _close_selected_session(self, *args, **kwargs):
        return self.project_workspace._close_selected_session(*args, **kwargs)

    def _submit_project_write(self, *args, **kwargs):
        return self.project_workspace._submit_project_write(*args, **kwargs)

    def _on_project_written(self, *args, **kwargs):
        return self.project_workspace._on_project_written(*args, **kwargs)

    def _on_project_write_failed(self, *args, **kwargs):
        return self.project_workspace._on_project_write_failed(*args, **kwargs)

    def _on_project_write_busy(self, *args, **kwargs):
        return self.project_workspace._on_project_write_busy(*args, **kwargs)

    def _choose_project_store(self, *args, **kwargs):
        return self.project_workspace._choose_project_store(*args, **kwargs)

    def _reload_project_store(self, *args, **kwargs):
        return self.project_workspace._reload_project_store(*args, **kwargs)

    def _begin_project_load(self, *args, **kwargs):
        return self.project_workspace._begin_project_load(*args, **kwargs)

    def _on_project_busy(self, *args, **kwargs):
        return self.project_workspace._on_project_busy(*args, **kwargs)

    def _on_project_loaded(self, *args, **kwargs):
        return self.project_workspace._on_project_loaded(*args, **kwargs)

    def _on_project_failed(self, *args, **kwargs):
        return self.project_workspace._on_project_failed(*args, **kwargs)

    def _on_explorer_selection(self, *args, **kwargs):
        return self.project_workspace._on_explorer_selection(*args, **kwargs)

    @property
    def _project_root(self):
        return self.project_workspace._project_root

    @property
    def _project_fields(self):
        return self.project_workspace._project_fields

    @property
    def _project_entities(self):
        return self.project_workspace._project_entities

    @property
    def _project_owners(self):
        return self.project_workspace._project_owners

    @property
    def _project_schema(self):
        return self.project_workspace._project_schema

    @property
    def _pending_selection(self):
        return self.project_workspace._pending_selection

    @property
    def _write_refresh_pending(self):
        return self.project_workspace._write_refresh_pending

    @property
    def _project_closing(self):
        return self.project_workspace._project_closing

    @_project_closing.setter
    def _project_closing(self, value):
        self.project_workspace._project_closing = bool(value)

    def _select_project_store(self, last_root):
        return QFileDialog.getExistingDirectory(
            self, "Chọn thư mục kho ScanToPath", last_root or "")
