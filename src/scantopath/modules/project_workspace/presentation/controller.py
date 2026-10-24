"""Project Workspace QObject façade. Owns signals and view lifecycle only.

Read, write and RAW inspection workflows are separate collaborators.
Old Window/controller call sites remain supported.
"""
from __future__ import annotations
from PySide6.QtCore import QObject
from .forms_contract import ProjectEditCommand
from .workflows import (_ProjectReadCoordinator, _ProjectWriteCoordinator,
                           _CaptureReviewCoordinator)

class ProjectWorkspaceController(QObject):
    def __init__(self, view) -> None:
        super().__init__(view)
        self.view = view
        self._reads = _ProjectReadCoordinator(self)
        self._writes = _ProjectWriteCoordinator(self)
        self._captures = _CaptureReviewCoordinator(self)
        self._install_project_loader()
        self._install_project_writer()
        self._install_capture_checker()

    def _install_project_loader(self) -> None:
        return self._reads._install_project_loader()

    def _install_project_writer(self) -> None:
        return self._writes._install_project_writer()

    def _install_capture_checker(self) -> None:
        return self._captures._install_capture_checker()

    def _verify_selected_capture(self) -> None:
        return self._captures._verify_selected_capture()

    def _on_capture_checked(self, result: object) -> None:
        return self._captures._on_capture_checked(result)

    def _on_capture_check_failed(self, message: str) -> None:
        return self._captures._on_capture_check_failed(message)

    def _on_capture_busy(self, busy: bool) -> None:
        return self._captures._on_capture_busy(busy)

    def _can_write_project(self) -> bool:
        return self._writes._can_write_project()

    def _update_project_actions(self) -> None:
        return self._writes._update_project_actions()

    def _dialog_command(self, kind: str, *, create: bool, initial: object | None=None, target_id: str | None=None, parent_id: str | None=None, project_id: str | None=None) -> None:
        return self._writes._dialog_command(kind, create=create, initial=initial, target_id=target_id, parent_id=parent_id, project_id=project_id)

    def _create_project(self) -> None:
        return self._writes._create_project()

    def _create_specimen(self) -> None:
        return self._writes._create_specimen()

    def _create_session(self) -> None:
        return self._writes._create_session()

    def _edit_selected_metadata(self) -> None:
        return self._writes._edit_selected_metadata()

    def _close_selected_session(self) -> None:
        return self._writes._close_selected_session()

    def _submit_project_write(self, command: ProjectEditCommand) -> None:
        return self._writes._submit_project_write(command)

    def _on_project_written(self, result: object) -> None:
        return self._writes._on_project_written(result)

    def _on_project_write_failed(self, message: str) -> None:
        return self._writes._on_project_write_failed(message)

    def _on_project_write_busy(self, busy: bool) -> None:
        return self._writes._on_project_write_busy(busy)

    def _choose_project_store(self) -> None:
        return self._reads._choose_project_store()

    def _reload_project_store(self) -> None:
        return self._reads._reload_project_store()

    def _begin_project_load(self, root: str) -> None:
        return self._reads._begin_project_load(root)

    def _on_project_busy(self, busy: bool) -> None:
        return self._reads._on_project_busy(busy)

    def _on_project_loaded(self, bundle: object) -> None:
        return self._reads._on_project_loaded(bundle)

    def _on_project_failed(self, message: str) -> None:
        return self._reads._on_project_failed(message)

    def _on_explorer_selection(self, selection: object) -> None:
        return self._reads._on_explorer_selection(selection)
