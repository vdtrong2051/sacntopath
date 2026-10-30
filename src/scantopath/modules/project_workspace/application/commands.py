"""Explicit v2-only metadata mutations; preserve post-commit code recovery."""
from __future__ import annotations
from uuid import uuid4
from .errors import NumberingPendingError
from .models import (StorageRef, CodeAssignmentSummary, ProjectSummary, SpecimenSummary, SessionSummary)

class ProjectCommands:
    def __init__(self, context, mapper):
        self.context = context
        self.mapper = mapper

    def assign_code(self, entity_type: str, internal_id: str) -> StorageRef:
        """Explicitly issue or recover a public code for an EXISTING entity."""
        registry = self.context.require_numbered()
        location = registry.assign(entity_type, internal_id)
        return StorageRef(location.public_path.split("/")[-1], location.public_path,
                          location.relative_path, location.layout_version, location.integrity_state)

    def assign_existing_codes(self) -> CodeAssignmentSummary:
        """Explicit mutation: map all existing legacy IDs without moving RAW."""
        return CodeAssignmentSummary(tuple(self.context.require_numbered().assign_all().items()))

    def _assign_after_create(self, entity_type: str, internal_id: str) -> None:
        try:
            self.context.require_numbered().assign(entity_type, internal_id)
        except Exception as exc:
            raise NumberingPendingError(entity_type, internal_id) from exc

    def create_project(self, name: str, description: str = "", *,
                       project_id: str | None = None) -> ProjectSummary:
        self.context.require_numbered()  # Must fail before touching v1 or absent database.
        identity = project_id if project_id is not None else uuid4().hex
        with self.context.metadata_factory(self.context.root) as store:
            store.create_project(identity, name, description)
        self._assign_after_create("project", identity)
        with self.context.metadata_factory(self.context.root) as store:
            row = store.get_project(identity)
        return self.mapper.project(row)

    def update_project(self, project_id: str, *, name: str | None = None,
                       description: str | None = None) -> ProjectSummary:
        self.context.require_numbered()
        with self.context.metadata_factory(self.context.root) as store:
            row = store.update_project(project_id, name=name, description=description)
        return self.mapper.project(row)

    def create_specimen(self, project_id: str, label: str, description: str = "", *,
                        specimen_id: str | None = None) -> SpecimenSummary:
        self.context.require_numbered()
        identity = specimen_id if specimen_id is not None else uuid4().hex
        with self.context.metadata_factory(self.context.root) as store:
            store.create_specimen(identity, project_id, label, description)
        self._assign_after_create("specimen", identity)
        with self.context.metadata_factory(self.context.root) as store:
            tree = store.get_project_tree(project_id)
        row = next(row for row in tree["specimens"] if row["specimen_id"] == identity)
        return self.mapper.specimen(row)

    def update_specimen(self, project_id: str, specimen_id: str, *,
                        label: str | None = None, description: str | None = None) -> SpecimenSummary:
        self.context.require_numbered()
        with self.context.metadata_factory(self.context.root) as store:
            tree = store.get_project_tree(project_id)
            if not any(s["specimen_id"] == specimen_id for s in tree["specimens"]):
                raise LookupError("Specimen does not belong to the selected project")
            row = store.update_specimen(specimen_id, label=label, description=description)
        return self.mapper.specimen(row)

    def create_session(self, specimen_id: str, label: str = "Scan", *,
                       session_id: str | None = None) -> SessionSummary:
        self.context.require_numbered()
        identity = session_id if session_id is not None else uuid4().hex
        with self.context.metadata_factory(self.context.root) as store:
            store.create_scan_session(identity, specimen_id, label)
        self._assign_after_create("session", identity)
        return self._session_from_store(specimen_id, identity)

    def update_session(self, specimen_id: str, session_id: str, *, label: str) -> SessionSummary:
        """Rename a session without changing its parent, state, RAW or immutable ID."""
        self.context.require_numbered()
        with self.context.metadata_factory(self.context.root) as store:
            project_id = self._project_for_specimen(store, specimen_id)
            tree = store.get_project_tree(project_id)
            owned = any(
                session["session_id"] == session_id
                for specimen in tree["specimens"] if specimen["specimen_id"] == specimen_id
                for session in specimen["sessions"]
            )
            if not owned:
                raise LookupError("Session does not belong to selected specimen")
            store.update_scan_session(session_id, label=label)
        return self._session_from_store(specimen_id, session_id)

    def close_session(self, specimen_id: str, session_id: str) -> SessionSummary:
        self.context.require_numbered()
        # Read parent ownership before performing a durable state transition.
        with self.context.metadata_factory(self.context.root) as store:
            row = store.get_project_tree(self._project_for_specimen(store, specimen_id))
            target = next((s for n in row["specimens"] if n["specimen_id"] == specimen_id
                           for s in n["sessions"] if s["session_id"] == session_id), None)
            if target is None:
                raise LookupError("Session does not belong to the selected specimen")
            store.close_scan_session(session_id)
        return self._session_from_store(specimen_id, session_id)

    def delete_empty_entity(self, entity_type: str, internal_id: str,
                            parent_id: str | None = None) -> str:
        """Remove only an empty, non-materialized Project/Specimen/Session.

        Never delete Captures, ProcessingRuns, RAW paths or audit history.
        """
        return self.context.require_numbered().delete_empty_entity(
            entity_type, internal_id, parent_id
        )

    def _project_for_specimen(self, store: MetadataStore, specimen_id: str) -> str:
        # GĐ0 intentionally has no direct get_specimen(); explicit trees only.
        for project in store.list_projects():
            tree = store.get_project_tree(project["project_id"])
            if any(s["specimen_id"] == specimen_id for s in tree["specimens"]):
                return project["project_id"]
        raise LookupError("Specimen not found")

    def _session_from_store(self, specimen_id: str, session_id: str) -> SessionSummary:
        with self.context.metadata_factory(self.context.root) as store:
            project_id = self._project_for_specimen(store, specimen_id)
            tree = store.get_project_tree(project_id)
        node = next(s for p in tree["specimens"] if p["specimen_id"] == specimen_id
                    for s in p["sessions"] if s["session_id"] == session_id)
        return SessionSummary(node["session_id"], node["specimen_id"], node["label"],
                              node["state"], node["created_at"], node["closed_at"],
                              self.mapper.storage("session", session_id),
                              tuple(self.mapper.capture(c) for c in node["captures"]),
                              tuple(self.mapper.run(r) for r in node["processing_runs"]))
