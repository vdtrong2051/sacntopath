"""Translate persistence records into immutable DTOs; no database I/O."""
from __future__ import annotations
import json
from scantopath.application.contracts import UiDataState
from .models import (StorageRef, ProjectSummary, SpecimenSummary, CaptureSummary, ProcessingRunSummary)

class ProjectRecordMapper:
    def __init__(self, context):
        self.context = context

    def storage(self, kind: str, internal_id: str, *, capture_relative: str | None = None,
                 verified: bool = False) -> StorageRef:
        if self.context.numbered is None:
            return StorageRef(None, None, capture_relative, 1 if capture_relative else None,
                              "verified" if verified and capture_relative else
                              "legacy_unmapped" if capture_relative else "unmapped")
        try:
            location = self.context.numbered.resolve_id(kind, internal_id, verify=verified)
        except LookupError:
            return StorageRef(None, None, capture_relative, 1 if capture_relative else None,
                              "verified" if verified and capture_relative else
                              "legacy_unmapped" if capture_relative else "unmapped")
        state = location.integrity_state
        return StorageRef(location.public_path.split("/")[-1], location.public_path,
                          location.relative_path, location.layout_version, state)

    def project(self, row: dict) -> ProjectSummary:
        return ProjectSummary(row["project_id"], row["name"], row["description"],
                              row["created_at"], row["updated_at"],
                              self.storage("project", row["project_id"]))

    def specimen(self, row: dict) -> SpecimenSummary:
        return SpecimenSummary(row["specimen_id"], row["project_id"], row["label"],
                               row["description"], row["created_at"], row["updated_at"],
                               self.storage("specimen", row["specimen_id"]))

    def capture(self, row: dict, *, verified: bool = False) -> CaptureSummary:
        return CaptureSummary(
            capture_id=row["capture_id"], session_id=row["session_id"],
            specimen_id=row["specimen_id"], schema_version=row["schema_version"],
            kind=row["kind"],
            data_state=(UiDataState.MEASURED if row["measured"] else UiDataState.FIXTURE),
            registered_at=row["registered_at"],
            storage=self.storage("capture", row["capture_id"],
                                  capture_relative=row["relative_path"], verified=verified),
        )

    def run(self, row: dict) -> ProcessingRunSummary:
        return ProcessingRunSummary(
            run_id=row["run_id"], session_id=row["session_id"],
            stage=row["stage"], algorithm=row["algorithm"], version=row["version"],
            state=row["state"], input_capture_ids=tuple(row["input_capture_ids"]),
            output_files=tuple(row["output_files"]),
            parameters_json=json.dumps(row["parameters"], ensure_ascii=False,
                                        sort_keys=True, allow_nan=False),
            error_message=row["error_message"], created_at=row["created_at"],
            started_at=row["started_at"], finished_at=row["finished_at"],
            storage=self.storage("run", row["run_id"]),
        )
