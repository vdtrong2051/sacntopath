"""Lớp giao diện metadata ổn định, phân quyền xử lý cho các repository.

Giữ hợp đồng công khai, phiên bản schema v1/v2 và ranh giới giao dịch SQLite;
không âm thầm nâng cấp cơ sở dữ liệu đã có.
"""
from __future__ import annotations
from pathlib import Path
from typing import Any
from sqlalchemy import create_engine, event, select, text
from sqlalchemy.engine import URL
from sqlalchemy.orm import Session
from .schema import (_Base,_Project,_Specimen,_ScanSession,_Capture,_ProcessingRun,
                     _RunInput,_AuditEvent,_utc,_safe_id,_label,_plain,_must,_log)
from .repos import (_ProjectRepository,_CaptureRepository,_ProcessingRepository,_AuditRepository)

class MetadataStore:
    """Backward-compatible metadata store; schema migrations are never implicit."""
    SCHEMA_VERSION = 1
    SUPPORTED_SCHEMA_VERSIONS = (1, 2)

    def __init__(self, root: str | Path):
        self.root = Path(root).resolve()
        self.root.mkdir(parents=True, exist_ok=True)
        self.db_path = self.root / "metadata.sqlite3"
        url = URL.create("sqlite+pysqlite", database=str(self.db_path))
        self.engine = create_engine(url, connect_args={"timeout": 10})

        @event.listens_for(self.engine, "connect")
        def _sqlite_foreign_keys(dbapi_conn, _):
            cursor = dbapi_conn.cursor()
            cursor.execute("PRAGMA foreign_keys=ON")
            cursor.execute("PRAGMA busy_timeout=10000")
            cursor.close()

        try:
            with self.engine.begin() as conn:
                version = int(conn.execute(text("PRAGMA user_version")).scalar_one())
                if version not in (0, *self.SUPPORTED_SCHEMA_VERSIONS):
                    raise RuntimeError(f"Unsupported metadata schema version {version}")
                if version == 0:
                    # Từ chối chiếm quyền quản lý cơ sở dữ liệu đã có nhưng chưa xác định schema.
                    existing = conn.exec_driver_sql(
                        "SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%'"
                    ).scalars().all()
                    if existing:
                        raise RuntimeError("Unversioned database with existing tables: refusing to migrate")
                    _Base.metadata.create_all(conn)
                    conn.exec_driver_sql(f"PRAGMA user_version={self.SCHEMA_VERSION}")
                else:
                    # create_all không nâng cấp schema cũ; phải xác thực đúng phiên bản trước khi dùng.
                    expected = set(_Base.metadata.tables)
                    existing = set(conn.exec_driver_sql(
                        "SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%'"
                    ).scalars())
                    if version == 2:
                        from scantopath.storage.numbered_schema import TABLES
                        expected.update(TABLES)
                    if not expected.issubset(existing):
                        raise RuntimeError("Metadata database is incomplete; manual recovery required")
        except BaseException:
            self.engine.dispose()
            raise
        self._projects = _ProjectRepository(self.engine, self.root)
        self._captures = _CaptureRepository(self.engine, self.root)
        self._runs = _ProcessingRepository(self.engine, self.root)
        self._audit = _AuditRepository(self.engine, self.root)

    def close(self) -> None:
        self.engine.dispose()

    def __enter__(self) -> "MetadataStore":
        return self

    def __exit__(self, *_: object) -> None:
        self.close()

    def create_project(self, project_id: str, name: str, description: str='') -> dict:
        return self._projects.create_project(project_id, name, description)

    def update_project(self, project_id: str, *, name: str | None=None, description: str | None=None) -> dict:
        return self._projects.update_project(project_id, name=name, description=description)

    def get_project(self, project_id: str) -> dict:
        return self._projects.get_project(project_id)

    def list_projects(self) -> list[dict]:
        return self._projects.list_projects()

    def create_specimen(self, specimen_id: str, project_id: str, label: str, description: str='') -> dict:
        return self._projects.create_specimen(specimen_id, project_id, label, description)

    def update_specimen(self, specimen_id: str, *, label: str | None=None, description: str | None=None) -> dict:
        return self._projects.update_specimen(specimen_id, label=label, description=description)

    def create_scan_session(self, session_id: str, specimen_id: str, label: str='Scan') -> dict:
        return self._projects.create_scan_session(session_id, specimen_id, label)

    def update_scan_session(self, session_id: str, *, label: str) -> dict:
        return self._projects.update_scan_session(session_id, label=label)

    def close_scan_session(self, session_id: str) -> dict:
        return self._projects.close_scan_session(session_id)

    def register_capture(self, capture_path: str | Path) -> dict:
        return self._captures.register_capture(capture_path)

    def get_capture(self, capture_id: str, *, verify_raw: bool=False) -> dict:
        return self._captures.get_capture(capture_id, verify_raw=verify_raw)

    def create_processing_run(self, *, run_id: str | None=None, session_id: str, stage: str, algorithm: str, version: str, input_capture_ids: list[str], parameters: dict[str, int | float | str | bool] | None=None) -> dict:
        return self._runs.create_processing_run(run_id=run_id, session_id=session_id, stage=stage, algorithm=algorithm, version=version, input_capture_ids=input_capture_ids, parameters=parameters)

    def start_processing_run(self, run_id: str) -> dict:
        return self._runs.start_processing_run(run_id)

    def finish_processing_run(self, run_id: str, *, state: str, output_files: list[str] | None=None, error_message: str | None=None) -> dict:
        return self._runs.finish_processing_run(run_id, state=state, output_files=output_files, error_message=error_message)

    @staticmethod
    def _run_dict(db: Session, obj: _ProcessingRun) -> dict:
        inputs = db.scalars(select(_RunInput).where(_RunInput.run_id == obj.run_id)
                            .order_by(_RunInput.ordinal)).all()
        # Có thể cần flush bản ghi chờ trước khi truy vấn được _RunInput.
        return {**_plain(obj), "input_capture_ids": [item.capture_id for item in inputs]}

    def get_processing_run(self, run_id: str) -> dict:
        return self._runs.get_processing_run(run_id)

    def get_project_tree(self, project_id: str) -> dict:
        return self._projects.get_project_tree(project_id)

    def record_event(self, *, level: str, action: str, entity_type: str, entity_id: str, details: dict[str, Any] | None=None) -> dict:
        return self._audit.record_event(level=level, action=action, entity_type=entity_type, entity_id=entity_id, details=details)

    def list_events(self, *, limit: int=100) -> list[dict]:
        return self._audit.list_events(limit=limit)
