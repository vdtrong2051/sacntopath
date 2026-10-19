"""DDL explicitly installed by 07.2 migration, NEVER by GĐ0 MetadataStore.create_all.

Separate per-kind tables provide actual SQLite foreign keys to authoritative
GĐ0 entities. Parent ownership checks are additionally enforced by triggers.
"""
DDL = """
CREATE TABLE storage_projects (
 project_id TEXT PRIMARY KEY REFERENCES projects(project_id) ON DELETE RESTRICT,
 ordinal INTEGER NOT NULL UNIQUE CHECK(ordinal > 0),
 code TEXT NOT NULL UNIQUE,
 relative_path TEXT NOT NULL UNIQUE
);
CREATE TABLE storage_specimens (
 specimen_id TEXT PRIMARY KEY REFERENCES specimens(specimen_id) ON DELETE RESTRICT,
 project_id TEXT NOT NULL REFERENCES storage_projects(project_id) ON DELETE RESTRICT,
 ordinal INTEGER NOT NULL CHECK(ordinal > 0),
 code TEXT NOT NULL,
 relative_path TEXT NOT NULL UNIQUE,
 UNIQUE(project_id, ordinal), UNIQUE(project_id, code)
);
CREATE TABLE storage_sessions (
 session_id TEXT PRIMARY KEY REFERENCES scan_sessions(session_id) ON DELETE RESTRICT,
 specimen_id TEXT NOT NULL REFERENCES storage_specimens(specimen_id) ON DELETE RESTRICT,
 ordinal INTEGER NOT NULL CHECK(ordinal > 0),
 code TEXT NOT NULL,
 relative_path TEXT NOT NULL UNIQUE,
 UNIQUE(specimen_id, ordinal), UNIQUE(specimen_id, code)
);
CREATE TABLE storage_captures (
 capture_id TEXT PRIMARY KEY REFERENCES captures(capture_id) ON DELETE RESTRICT,
 session_id TEXT NOT NULL REFERENCES storage_sessions(session_id) ON DELETE RESTRICT,
 ordinal INTEGER NOT NULL CHECK(ordinal > 0),
 code TEXT NOT NULL,
 relative_path TEXT NOT NULL UNIQUE,
 layout_version INTEGER NOT NULL CHECK(layout_version IN (1, 2)),
 UNIQUE(session_id, ordinal), UNIQUE(session_id, code)
);
CREATE TABLE storage_runs (
 run_id TEXT PRIMARY KEY REFERENCES processing_runs(run_id) ON DELETE RESTRICT,
 session_id TEXT NOT NULL REFERENCES storage_sessions(session_id) ON DELETE RESTRICT,
 ordinal INTEGER NOT NULL CHECK(ordinal > 0),
 code TEXT NOT NULL,
 relative_path TEXT NOT NULL UNIQUE,
 UNIQUE(session_id, ordinal), UNIQUE(session_id, code)
);
CREATE TABLE storage_counters (
 entity_type TEXT NOT NULL CHECK(entity_type IN ('project','specimen','session','capture','run')),
 scope_key TEXT NOT NULL,
 next_ordinal INTEGER NOT NULL CHECK(next_ordinal > 0),
 PRIMARY KEY (entity_type, scope_key)
);
CREATE TABLE storage_capture_reservations (
 capture_id TEXT PRIMARY KEY,
 session_id TEXT NOT NULL REFERENCES storage_sessions(session_id) ON DELETE RESTRICT,
 ordinal INTEGER NOT NULL CHECK(ordinal > 0),
 code TEXT NOT NULL,
 relative_path TEXT NOT NULL UNIQUE,
 UNIQUE(session_id, ordinal), UNIQUE(session_id, code)
);
CREATE TRIGGER storage_specimen_parent BEFORE INSERT ON storage_specimens BEGIN
 SELECT CASE WHEN NOT EXISTS (SELECT 1 FROM specimens s WHERE s.specimen_id=NEW.specimen_id AND s.project_id=NEW.project_id)
 THEN RAISE(ABORT, 'storage specimen parent mismatch') END;
END;
CREATE TRIGGER storage_session_parent BEFORE INSERT ON storage_sessions BEGIN
 SELECT CASE WHEN NOT EXISTS (SELECT 1 FROM scan_sessions s WHERE s.session_id=NEW.session_id AND s.specimen_id=NEW.specimen_id)
 THEN RAISE(ABORT, 'storage session parent mismatch') END;
END;
CREATE TRIGGER storage_capture_parent BEFORE INSERT ON storage_captures BEGIN
 SELECT CASE WHEN NOT EXISTS (SELECT 1 FROM captures c WHERE c.capture_id=NEW.capture_id AND c.session_id=NEW.session_id AND c.relative_path=NEW.relative_path)
 THEN RAISE(ABORT, 'storage capture path/parent mismatch') END;
END;
CREATE TRIGGER storage_run_parent BEFORE INSERT ON storage_runs BEGIN
 SELECT CASE WHEN NOT EXISTS (SELECT 1 FROM processing_runs r WHERE r.run_id=NEW.run_id AND r.session_id=NEW.session_id)
 THEN RAISE(ABORT, 'storage run parent mismatch') END;
END;
CREATE TRIGGER storage_projects_immutable BEFORE UPDATE ON storage_projects BEGIN SELECT RAISE(ABORT,'storage project mapping immutable'); END;
CREATE TRIGGER storage_specimens_immutable BEFORE UPDATE ON storage_specimens BEGIN SELECT RAISE(ABORT,'storage specimen mapping immutable'); END;
CREATE TRIGGER storage_sessions_immutable BEFORE UPDATE ON storage_sessions BEGIN SELECT RAISE(ABORT,'storage session mapping immutable'); END;
CREATE TRIGGER storage_captures_immutable BEFORE UPDATE ON storage_captures BEGIN SELECT RAISE(ABORT,'storage capture mapping immutable'); END;
CREATE TRIGGER storage_runs_immutable BEFORE UPDATE ON storage_runs BEGIN SELECT RAISE(ABORT,'storage run mapping immutable'); END;
CREATE TRIGGER storage_reservations_immutable BEFORE UPDATE ON storage_capture_reservations BEGIN SELECT RAISE(ABORT,'storage reservation immutable'); END;
CREATE TRIGGER storage_specimens_reparent BEFORE UPDATE OF project_id ON specimens
 WHEN EXISTS (SELECT 1 FROM storage_specimens WHERE specimen_id=OLD.specimen_id)
 BEGIN SELECT RAISE(ABORT,'cannot reparent numbered specimen'); END;
CREATE TRIGGER storage_sessions_reparent BEFORE UPDATE OF specimen_id ON scan_sessions
 WHEN EXISTS (SELECT 1 FROM storage_sessions WHERE session_id=OLD.session_id)
 BEGIN SELECT RAISE(ABORT,'cannot reparent numbered session'); END;
CREATE TRIGGER storage_captures_move BEFORE UPDATE OF session_id,relative_path ON captures
 WHEN EXISTS (SELECT 1 FROM storage_captures WHERE capture_id=OLD.capture_id)
 BEGIN SELECT RAISE(ABORT,'cannot move numbered capture without migration'); END;
CREATE TRIGGER storage_runs_reparent BEFORE UPDATE OF session_id ON processing_runs
 WHEN EXISTS (SELECT 1 FROM storage_runs WHERE run_id=OLD.run_id)
 BEGIN SELECT RAISE(ABORT,'cannot reparent numbered run'); END;
"""
TABLES = ("storage_projects", "storage_specimens", "storage_sessions", "storage_captures", "storage_runs", "storage_counters", "storage_capture_reservations")
