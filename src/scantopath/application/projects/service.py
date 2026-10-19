"""07.3: opt-in Project Workspace application service, no UI dependencies.

Reading never allocates public codes, migrates SQLite, reads camera, or changes
RAW. Changes to GĐ0 metadata use its existing validated APIs. Numbered codes
are explicitly allocated via the 07.2 registry after a successful create.
"""
from __future__ import annotations

import json
from pathlib import Path
import sqlite3
from uuid import uuid4

from scantopath.application.contracts import UiDataState
from scantopath.metadata.store import MetadataStore
from scantopath.storage.numbered import NumberedStorageRegistry

from .models import (
    AuditEventSummary, CaptureSummary, CodeAssignmentSummary, ProcessingRunSummary,
    ProjectSummary, ProjectTree, SessionSummary, SpecimenNode, SpecimenSummary,
    StorageRef, StoreInfo,
)


class StoreNotOpenError(RuntimeError):
    """The application has not explicitly selected an existing SQLite store."""


class NumberedSchemaRequiredError(RuntimeError):
    """Writes requiring numbered codes need explicit 07.2 SQLite migration."""


class NumberingPendingError(RuntimeError):
    """Metadata committed, code allocation failed; DO NOT repeat create().

    Use assign_code(entity_type, internal_id) to repair the missing alias.
    """

    def __init__(self, entity_type: str, internal_id: str):
        self.entity_type = entity_type
        self.internal_id = internal_id
        super().__init__(f"Metadata committed for {entity_type} {internal_id}; "
                         "numbering pending; retry assign_code(), NOT create().")


class ProjectWorkspaceService:
    """Explicitly opened store; only pure DTOs cross the service/UI boundary.

    No SQLite connection is held between calls. A UI should call these methods
    from its application/worker layer, not from a QWidget's internal ORM code.
    """

    def __init__(self, root: str | Path) -> None:
        if not isinstance(root, (str, Path)) or not str(root).strip():
            raise ValueError("Storage root must be a nonempty local path")
        supplied = Path(root).absolute()
        if (supplied.is_symlink() or
                (hasattr(supplied, "is_junction") and supplied.is_junction())):
            raise ValueError("Storage root must not be a symbolic link or junction")
        if not supplied.is_dir():
            raise StoreNotOpenError("Storage folder does not exist; choose an existing store")
        database = supplied / "metadata.sqlite3"
        if not database.is_file() or database.is_symlink():
            raise StoreNotOpenError("No metadata.sqlite3 in selected folder")
        self._root = supplied.resolve(strict=True)
        # Open only an EXISTING database; sqlite URI with mode=ro never creates one.
        uri = database.resolve(strict=True).as_uri() + "?mode=ro"
        with sqlite3.connect(uri, uri=True) as conn:
            version = conn.execute("PRAGMA user_version").fetchone()[0]
        if version not in (1, 2):
            raise RuntimeError(f"Unsupported SQLite schema version: {version}")
        # Keep schema guards from GĐ0/07.2 rather than accepting a partial DB.
        with MetadataStore(self._root):
            pass
        self._schema_version = version
        self._numbered = NumberedStorageRegistry(self._root) if version == 2 else None

    @property
    def info(self) -> StoreInfo:
        return StoreInfo(str(self._root), self._schema_version,
                         self._numbered is not None, self._numbered is not None)

    def _require_numbered(self) -> NumberedStorageRegistry:
        if self._numbered is None:
            raise NumberedSchemaRequiredError(
                "SQLite schema v1 is readable, but numbering requires an explicit "
                "v1-to-v2 migration using the 07.2 tool; no implicit migration is performed."
            )
        return self._numbered

    def _storage(self, kind: str, internal_id: str, *, capture_relative: str | None = None,
                 verified: bool = False) -> StorageRef:
        if self._numbered is None:
            return StorageRef(None, None, capture_relative, 1 if capture_relative else None,
                              "verified" if verified and capture_relative else
                              "legacy_unmapped" if capture_relative else "unmapped")
        try:
            location = self._numbered.resolve_id(kind, internal_id, verify=verified)
        except LookupError:
            return StorageRef(None, None, capture_relative, 1 if capture_relative else None,
                              "verified" if verified and capture_relative else
                              "legacy_unmapped" if capture_relative else "unmapped")
        state = location.integrity_state
        return StorageRef(location.public_path.split("/")[-1], location.public_path,
                          location.relative_path, location.layout_version, state)

    def _project(self, row: dict) -> ProjectSummary:
        return ProjectSummary(row["project_id"], row["name"], row["description"],
                              row["created_at"], row["updated_at"],
                              self._storage("project", row["project_id"]))

    def _specimen(self, row: dict) -> SpecimenSummary:
        return SpecimenSummary(row["specimen_id"], row["project_id"], row["label"],
                               row["description"], row["created_at"], row["updated_at"],
                               self._storage("specimen", row["specimen_id"]))

    def _capture(self, row: dict, *, verified: bool = False) -> CaptureSummary:
        return CaptureSummary(
            capture_id=row["capture_id"], session_id=row["session_id"],
            specimen_id=row["specimen_id"], schema_version=row["schema_version"],
            kind=row["kind"],
            data_state=(UiDataState.MEASURED if row["measured"] else UiDataState.FIXTURE),
            registered_at=row["registered_at"],
            storage=self._storage("capture", row["capture_id"],
                                  capture_relative=row["relative_path"], verified=verified),
        )

    def _run(self, row: dict) -> ProcessingRunSummary:
        return ProcessingRunSummary(
            run_id=row["run_id"], session_id=row["session_id"],
            stage=row["stage"], algorithm=row["algorithm"], version=row["version"],
            state=row["state"], input_capture_ids=tuple(row["input_capture_ids"]),
            output_files=tuple(row["output_files"]),
            parameters_json=json.dumps(row["parameters"], ensure_ascii=False,
                                        sort_keys=True, allow_nan=False),
            error_message=row["error_message"], created_at=row["created_at"],
            started_at=row["started_at"], finished_at=row["finished_at"],
            storage=self._storage("run", row["run_id"]),
        )

    def list_projects(self) -> tuple[ProjectSummary, ...]:
        """Read-only, including when the SQLite schema is still v1."""
        with MetadataStore(self._root) as store:
            records = store.list_projects()
        return tuple(self._project(row) for row in records)

    def get_project_tree(self, project_id: str) -> ProjectTree:
        with MetadataStore(self._root) as store:
            raw = store.get_project_tree(project_id)
        nodes = []
        for specimen in raw["specimens"]:
            sessions = []
            for session in specimen["sessions"]:
                sessions.append(SessionSummary(
                    session_id=session["session_id"], specimen_id=session["specimen_id"],
                    label=session["label"], state=session["state"],
                    created_at=session["created_at"], closed_at=session["closed_at"],
                    storage=self._storage("session", session["session_id"]),
                    captures=tuple(self._capture(c) for c in session["captures"]),
                    processing_runs=tuple(self._run(r) for r in session["processing_runs"]),
                ))
            nodes.append(SpecimenNode(self._specimen(specimen), tuple(sessions)))
        return ProjectTree(self._project(raw), tuple(nodes))

    def get_capture(self, capture_id: str, *, verify_raw: bool = False) -> CaptureSummary:
        """Optional checksum check; never interprets it as metric validation."""
        with MetadataStore(self._root) as store:
            record = store.get_capture(capture_id, verify_raw=verify_raw)
        return self._capture(record, verified=verify_raw)

    def get_processing_run(self, run_id: str) -> ProcessingRunSummary:
        with MetadataStore(self._root) as store:
            row = store.get_processing_run(run_id)
        return self._run(row)

    def list_events(self, *, limit: int = 100) -> tuple[AuditEventSummary, ...]:
        with MetadataStore(self._root) as store:
            rows = store.list_events(limit=limit)
        return tuple(AuditEventSummary(
            event_id=row["event_id"], occurred_at=row["occurred_at"],
            action=row["action"], level=row["level"],
            entity_type=row["entity_type"], entity_id=row["entity_id"],
            details_json=json.dumps(row["details"], ensure_ascii=False,
                                     sort_keys=True, allow_nan=False),
        ) for row in rows)

    def assign_code(self, entity_type: str, internal_id: str) -> StorageRef:
        """Explicitly issue or recover a public code for an EXISTING entity."""
        registry = self._require_numbered()
        location = registry.assign(entity_type, internal_id)
        return StorageRef(location.public_path.split("/")[-1], location.public_path,
                          location.relative_path, location.layout_version, location.integrity_state)

    def assign_existing_codes(self) -> CodeAssignmentSummary:
        """Explicit mutation: map all existing legacy IDs without moving RAW."""
        return CodeAssignmentSummary(tuple(self._require_numbered().assign_all().items()))

    def _assign_after_create(self, entity_type: str, internal_id: str) -> None:
        try:
            self._require_numbered().assign(entity_type, internal_id)
        except Exception as exc:
            raise NumberingPendingError(entity_type, internal_id) from exc

    def create_project(self, name: str, description: str = "", *,
                       project_id: str | None = None) -> ProjectSummary:
        self._require_numbered()  # Must fail before touching v1 or absent database.
        identity = project_id if project_id is not None else uuid4().hex
        with MetadataStore(self._root) as store:
            store.create_project(identity, name, description)
        self._assign_after_create("project", identity)
        with MetadataStore(self._root) as store:
            row = store.get_project(identity)
        return self._project(row)

    def update_project(self, project_id: str, *, name: str | None = None,
                       description: str | None = None) -> ProjectSummary:
        self._require_numbered()
        with MetadataStore(self._root) as store:
            row = store.update_project(project_id, name=name, description=description)
        return self._project(row)

    def create_specimen(self, project_id: str, label: str, description: str = "", *,
                        specimen_id: str | None = None) -> SpecimenSummary:
        self._require_numbered()
        identity = specimen_id if specimen_id is not None else uuid4().hex
        with MetadataStore(self._root) as store:
            store.create_specimen(identity, project_id, label, description)
        self._assign_after_create("specimen", identity)
        with MetadataStore(self._root) as store:
            tree = store.get_project_tree(project_id)
        row = next(row for row in tree["specimens"] if row["specimen_id"] == identity)
        return self._specimen(row)

    def update_specimen(self, project_id: str, specimen_id: str, *,
                        label: str | None = None, description: str | None = None) -> SpecimenSummary:
        self._require_numbered()
        with MetadataStore(self._root) as store:
            tree = store.get_project_tree(project_id)
            if not any(s["specimen_id"] == specimen_id for s in tree["specimens"]):
                raise LookupError("Specimen does not belong to the selected project")
            row = store.update_specimen(specimen_id, label=label, description=description)
        return self._specimen(row)

    def create_session(self, specimen_id: str, label: str = "Scan", *,
                       session_id: str | None = None) -> SessionSummary:
        self._require_numbered()
        identity = session_id if session_id is not None else uuid4().hex
        with MetadataStore(self._root) as store:
            store.create_scan_session(identity, specimen_id, label)
        self._assign_after_create("session", identity)
        return self._session_from_store(specimen_id, identity)

    def close_session(self, specimen_id: str, session_id: str) -> SessionSummary:
        self._require_numbered()
        # Read parent ownership before performing a durable state transition.
        with MetadataStore(self._root) as store:
            row = store.get_project_tree(self._project_for_specimen(store, specimen_id))
            target = next((s for n in row["specimens"] if n["specimen_id"] == specimen_id
                           for s in n["sessions"] if s["session_id"] == session_id), None)
            if target is None:
                raise LookupError("Session does not belong to the selected specimen")
            store.close_scan_session(session_id)
        return self._session_from_store(specimen_id, session_id)

    def _project_for_specimen(self, store: MetadataStore, specimen_id: str) -> str:
        # GĐ0 intentionally has no direct get_specimen(); explicit trees only.
        for project in store.list_projects():
            tree = store.get_project_tree(project["project_id"])
            if any(s["specimen_id"] == specimen_id for s in tree["specimens"]):
                return project["project_id"]
        raise LookupError("Specimen not found")

    def _session_from_store(self, specimen_id: str, session_id: str) -> SessionSummary:
        with MetadataStore(self._root) as store:
            project_id = self._project_for_specimen(store, specimen_id)
            tree = store.get_project_tree(project_id)
        node = next(s for p in tree["specimens"] if p["specimen_id"] == specimen_id
                    for s in p["sessions"] if s["session_id"] == session_id)
        return SessionSummary(node["session_id"], node["specimen_id"], node["label"],
                              node["state"], node["created_at"], node["closed_at"],
                              self._storage("session", session_id),
                              tuple(self._capture(c) for c in node["captures"]),
                              tuple(self._run(r) for r in node["processing_runs"]))
