"""07.11: giao diện dịch vụ Project ổn định trên các nhóm tác vụ nhỏ.

Chỉ khi khởi tạo tường minh mới kiểm tra kho SQLite hiện có; thao tác import
không tự mở Qt, camera, kết nối SQLite hay dữ liệu RAW. Mỗi nhóm tác vụ có
trách nhiệm riêng, còn triển khai mặc định nằm ở tầng infrastructure.
"""
from __future__ import annotations
from pathlib import Path
from typing import Callable
from .context import WorkspaceContext
from .records import ProjectRecordMapper
from .queries import ProjectQueries
from .commands import ProjectCommands
from .inspection import CaptureIntegrityChecker
from .errors import StoreNotOpenError, NumberedSchemaRequiredError, NumberingPendingError
from .models import (AuditEventSummary, CaptureInspection, CaptureSummary, CodeAssignmentSummary,
                     ProcessingRunSummary, ProjectSummary, ProjectTree, SessionSummary,
                     SpecimenSummary, StorageRef, StoreInfo)


class ProjectWorkspaceService:
    """Legacy-compatible entry point; delegates reads, commands and inspection."""

    def __init__(self, root: str | Path, *,
                 metadata_factory: Callable[[Path], object] | None = None,
                 registry_factory: Callable[[Path], object] | None = None) -> None:
        # Điểm ghép tương thích: phần triển khai adapter được cung cấp ở lớp ghép ứng dụng.
        # Không nạp hoặc khởi tạo kho dữ liệu chỉ vì giao diện Qt khởi động.
        from ..infrastructure.sqlite_backend import (
            default_factories, probe_existing, safe_raw_path,
        )
        default_metadata, default_registry = default_factories()
        self._metadata_factory = metadata_factory or default_metadata
        self._registry_factory = registry_factory or default_registry
        root, version = probe_existing(root, self._metadata_factory)
        numbered = self._registry_factory(root) if version == 2 else None
        self._root = root
        self._schema_version = version
        self._numbered = numbered
        self._context = WorkspaceContext(root, version, self._metadata_factory,
                                         numbered, safe_raw_path)
        self._mapper = ProjectRecordMapper(self._context)
        self._queries = ProjectQueries(self._context, self._mapper)
        self._commands = ProjectCommands(self._context, self._mapper)
        self._inspection = CaptureIntegrityChecker(self._context, self._queries)

    @property
    def info(self) -> StoreInfo:
        return self._context.info

    def list_projects(self) -> tuple[ProjectSummary, ...]:
        return self._queries.list_projects()

    def get_project_tree(self, project_id: str) -> ProjectTree:
        return self._queries.get_project_tree(project_id)

    def get_capture(self, capture_id: str, *, verify_raw: bool = False) -> CaptureSummary:
        return self._queries.get_capture(capture_id, verify_raw=verify_raw)

    def get_processing_run(self, run_id: str) -> ProcessingRunSummary:
        return self._queries.get_processing_run(run_id)

    def list_events(self, *, limit: int = 100) -> tuple[AuditEventSummary, ...]:
        return self._queries.list_events(limit=limit)

    def assign_code(self, entity_type: str, internal_id: str) -> StorageRef:
        return self._commands.assign_code(entity_type, internal_id)

    def assign_existing_codes(self) -> CodeAssignmentSummary:
        return self._commands.assign_existing_codes()

    def create_project(self, name: str, description: str = "", *,
                       project_id: str | None = None) -> ProjectSummary:
        return self._commands.create_project(name, description, project_id=project_id)

    def update_project(self, project_id: str, *, name: str | None = None,
                       description: str | None = None) -> ProjectSummary:
        return self._commands.update_project(project_id, name=name, description=description)

    def create_specimen(self, project_id: str, label: str, description: str = "", *,
                        specimen_id: str | None = None) -> SpecimenSummary:
        return self._commands.create_specimen(project_id, label, description, specimen_id=specimen_id)

    def update_specimen(self, project_id: str, specimen_id: str, *,
                        label: str | None = None, description: str | None = None) -> SpecimenSummary:
        return self._commands.update_specimen(project_id, specimen_id, label=label, description=description)

    def create_session(self, specimen_id: str, label: str = "Scan", *,
                       session_id: str | None = None) -> SessionSummary:
        return self._commands.create_session(specimen_id, label, session_id=session_id)

    def update_session(self, specimen_id: str, session_id: str, *, label: str) -> SessionSummary:
        return self._commands.update_session(specimen_id, session_id, label=label)

    def close_session(self, specimen_id: str, session_id: str) -> SessionSummary:
        return self._commands.close_session(specimen_id, session_id)

    def delete_empty_entity(self, entity_type: str, internal_id: str,
                            parent_id: str | None = None) -> str:
        return self._commands.delete_empty_entity(entity_type, internal_id, parent_id)

    def inspect_capture(self, capture_id: str) -> CaptureInspection:
        return self._inspection.inspect_capture(capture_id)
