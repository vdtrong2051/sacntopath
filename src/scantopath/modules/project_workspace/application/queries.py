"""Read-only project/RAW metadata queries. No code allocation on reads."""
from __future__ import annotations
import json
from .models import (AuditEventSummary, ProjectSummary, ProjectTree, SpecimenNode,
                     SessionSummary, CaptureSummary, ProcessingRunSummary)

class ProjectQueries:
    def __init__(self, context, mapper):
        self.context = context
        self.mapper = mapper

    def list_projects(self) -> tuple[ProjectSummary, ...]:
        """Read-only, including when the SQLite schema is still v1."""
        with self.context.metadata_factory(self.context.root) as store:
            records = store.list_projects()
        return tuple(self.mapper.project(row) for row in records)

    def get_project_tree(self, project_id: str) -> ProjectTree:
        with self.context.metadata_factory(self.context.root) as store:
            raw = store.get_project_tree(project_id)
        nodes = []
        for specimen in raw["specimens"]:
            sessions = []
            for session in specimen["sessions"]:
                sessions.append(SessionSummary(
                    session_id=session["session_id"], specimen_id=session["specimen_id"],
                    label=session["label"], state=session["state"],
                    created_at=session["created_at"], closed_at=session["closed_at"],
                    storage=self.mapper.storage("session", session["session_id"]),
                    captures=tuple(self.mapper.capture(c) for c in session["captures"]),
                    processing_runs=tuple(self.mapper.run(r) for r in session["processing_runs"]),
                ))
            nodes.append(SpecimenNode(self.mapper.specimen(specimen), tuple(sessions)))
        return ProjectTree(self.mapper.project(raw), tuple(nodes))

    def get_capture(self, capture_id: str, *, verify_raw: bool = False) -> CaptureSummary:
        """Optional checksum check; never interprets it as metric validation."""
        with self.context.metadata_factory(self.context.root) as store:
            record = store.get_capture(capture_id, verify_raw=verify_raw)
        return self.mapper.capture(record, verified=verify_raw)

    def get_processing_run(self, run_id: str) -> ProcessingRunSummary:
        with self.context.metadata_factory(self.context.root) as store:
            row = store.get_processing_run(run_id)
        return self.mapper.run(row)

    def list_events(self, *, limit: int = 100) -> tuple[AuditEventSummary, ...]:
        with self.context.metadata_factory(self.context.root) as store:
            rows = store.list_events(limit=limit)
        return tuple(AuditEventSummary(
            event_id=row["event_id"], occurred_at=row["occurred_at"],
            action=row["action"], level=row["level"],
            entity_type=row["entity_type"], entity_id=row["entity_id"],
            details_json=json.dumps(row["details"], ensure_ascii=False,
                                     sort_keys=True, allow_nan=False),
        ) for row in rows)
