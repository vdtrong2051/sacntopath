# PRE-05 — GĐ0 Project/Specimen/ScanSession/ProcessingRun/Logging persistence

**Status:** Implementation patch, requires Windows acceptance before committing.
**Source baseline:** `feat/pre-02-raw-rgbd-contract` commit `08c9b17c19ddbbf9696ce268a9a52581fe2c7083` (PRE-04 complete). No new Git branch and no merge into `main`.

## 1. Change boundary

New code is an independent, opt-in `scantopath.metadata` module:

- `src/scantopath/metadata/__init__.py`
- `src/scantopath/metadata/store.py` — SQLite/SQLAlchemy 2.x schema and transactions.
- `src/scantopath/metadata/cli.py` — CLI to exercise the metadata lifecycle.
- `tests/test_pre05_metadata_store.py` — offline unit + separate-process integration checks.
- `docs/PRE_05_GD0_METADATA_PERSISTENCE.md` — this guide.
- `pyproject.toml` — **only existing file changed**: adds `SQLAlchemy>=2.0,<3` as a Python runtime dependency.

**Unchanged:** PRE-02 RAW v2 models, PRE-03 `SessionStore`, PRE-04 Orbbec adapter/CLI, C++, pybind11, CMake, PySide6. PRE-05 does not open the camera, synthesize a scan, modify RAW files or run 3D algorithms. Existing PRE-04 `--once` records RAW to the filesystem but does not auto-create Project/Specimen rows: the operator explicitly registers the capture in this phase.

## 2. Schema / truth boundaries

```
metadata.sqlite3
  projects(project_id)
     └── specimens(specimen_id, project_id FK)
            └── scan_sessions(session_id, specimen_id FK)
                  ├── captures(capture_id, session_id FK, schema_version, relative_path)
                  └── processing_runs(run_id, session_id FK, stage, algorithm, parameters, state, ...)
                         └── processing_run_inputs(run_id FK, capture_id FK, ordinal)
  audit_events(event_id, UTC timestamp, level, action, entity_type, entity_id, details)

sessions/<session-id>/captures/<capture-id>/...   # PRE-03 filesystem RAW v1/v2
```

- SQLite stores **metadata and a relative path**, not JPEG, Y16 or NumPy arrays. RAW files stay where PRE-03 placed them. Database path is `<store-root>/metadata.sqlite3`.
- `PRAGMA foreign_keys=ON` on every SQLAlchemy connection. Mutations to metadata and associated audit events share a **single SQLite transaction**; an exception rolls back the transaction. IDs are constrained to 1–128 safe ASCII letters/digits/`_`/`-`.
- Schema version is `PRAGMA user_version=1`. This phase can initialize a new database or reopen a version-1 database. It **refuses** an unknown/newer schema, unversioned existing tables or an incomplete version-1 schema. It does not auto-migrate or drop the user's tables. Back up the SQLite file before future schema upgrades.
- UTC ISO-8601 strings with explicit timezone offset are used for metadata timestamps. SDK frame timestamps stay in the original immutable RAW metadata, not in Project or Session time fields.
- `register_capture(path)` calls PRE-03's `read_capture()`: RAW v2 verifies its SHA-256 manifest, v1 validates the committed NPY arrays. Directory IDs, session/specimen relation and committed status are checked. Neither RAW nor original camera provenance is changed. Registering a Capture is an explicit, *separate* operation after the filesystem commit.
- The two persistence systems are **not an atomic distributed transaction**. If RAW was committed but registration failed, the RAW directory still exists; correct the metadata and re-register. Deleting/moving RAW files later can create dangling metadata references; call `get_capture(..., verify_raw=True)` to detect them. No background repair service is implied.
- The `measured` field only preserves whether a packet was sensor-sourced. It is **not** dimensional metrology validation. No encoder/camera pose is inferred.
- Audit events are structured records (`INFO`, `WARNING`, `ERROR`). Metadata mutations log automatically. `record_event` / `log-event` allow other code to append sanitized, bounded diagnostics manually; **the PRE-04 camera source is not automatically wired into the SQLite event logger**.
- `ProcessingRun` state transitions: `pending → running → succeeded|failed` (terminal). The registry stores references, input IDs, algorithm metadata and outputs. Changing state does **not** execute an algorithm or establish result validity. Output files are names/metadata only; the service does not create or check them.
- ScanSession state: `open → closed`. Closed sessions cannot receive new registered captures. Immutable Project/Specimen/Session IDs and parent relationships preserve provenance. Project/Specimen titles/descriptions may be updated; delete/cascade APIs are intentionally omitted.

## 3. Setup on Windows (same repository, same branch)

```powershell
cd E:\1_BigProject\scantopath\scantopath-software
$pyExe = (Resolve-Path '.\.venv\Scripts\python.exe').Path
& $pyExe -m pip install -e .
& $pyExe -m pytest -q .\tests
ctest --test-dir .\build-orbbec -C Release --output-on-failure
$env:SCANTOPATH_ORBBEC_SDK_BIN = 'E:\1_BigProject\scantopath\_sdk\OrbbecSDK_v2.10.6\bin'
& $pyExe -u -X faulthandler -m scantopath.acquisition.native --self-test
```

Expected Python suite: **75 test cases**, of which Windows may **skip one symlink-permission test** from PRE-03 (so `74 passed, 1 skipped` is acceptable with reason confirmed). No camera is required for PRE-05 Python tests. CTest should remain `2/2` on the existing Orbbec-configured Windows build.

## 4. Exercise the full metadata lifecycle against existing real Gemini 2 RAW

A PRE-04 capture already observed on the user's Windows machine:

- `capture_id=2c15ecedf3544822874a7c015e4a4dc1`
- `session_id=handheld-001`, `specimen_id=sample-001`
- `schema_version=2`, `kind=orbbec`, `checksum_verified=true` on the previous replay.

The following commands reuse those existing IDs. If the user already created the exact IDs in this database, do **not** rerun create commands: inspect the tree first.

```powershell
$pyExe = (Resolve-Path '.\.venv\Scripts\python.exe').Path
$metaRoot = '.\scantopath-data'

# A. Project → Specimen → ScanSession (only metadata, no camera)
& $pyExe -m scantopath.metadata.cli --root $metaRoot create-project `
  --id project-001 --name 'ScanToPath Handheld'
& $pyExe -m scantopath.metadata.cli --root $metaRoot create-specimen `
  --id sample-001 --project project-001 --label 'Mechanical sample'
& $pyExe -m scantopath.metadata.cli --root $metaRoot create-session `
  --id handheld-001 --specimen sample-001 --label 'First manual scan'

# B. Register PRE-04 RAW already verified in filesystem; no new capture is taken.
$captureDir = '.\scantopath-data\sessions\handheld-001\captures\2c15ecedf3544822874a7c015e4a4dc1'
& $pyExe -m scantopath.metadata.cli --root $metaRoot register-capture --path $captureDir
& $pyExe -m scantopath.metadata.cli --root $metaRoot show-capture `
  --id 2c15ecedf3544822874a7c015e4a4dc1 --verify

# C. Create metadata-only ProcessingRun; no 3D algorithm runs.
& $pyExe -m scantopath.metadata.cli --root $metaRoot create-run `
  --id run-001 --session handheld-001 --stage raw-verification `
  --algorithm manifest-check-only --version pre-05 `
  --input 2c15ecedf3544822874a7c015e4a4dc1 `
  --parameters '{"dry_run":true}'

# D. Show full tree and persisted events.
& $pyExe -m scantopath.metadata.cli --root $metaRoot tree --project project-001
& $pyExe -m scantopath.metadata.cli --root $metaRoot events --limit 20
```

**PowerShell JSON note:** Windows PowerShell 5.1 may pass embedded quotes differently to native executables. The `--parameters` flag is optional; if argument quoting causes a JSON parse error, omit the `--parameters` option rather than attempting an unsafe modification. Run can be created without parameters.

For a full state lifecycle, *only after a real action has actually occurred*, use `start-run --id run-001`, then `finish-run --id run-001 --state succeeded` (or `failed`). Do not mark success for an algorithm that has not run.

**Persistence test:** close and reopen PowerShell; run `tree --project project-001` using the same `--root`. SQLite should preserve all metadata links, run states and audit events. RAW storage remains byte-identical. For no-camera verification, `show-capture --verify` checks the linked RAW capture again.

## 5. Acceptance checklist

1. Python regression: all runnable cases pass (75 total; symlink may skip one on Windows).
2. Existing C++ tests remain successful (2/2 on Windows); native self-test exit code 0.
3. CLI creates Project/Specimen/Session and registers a previously committed `orbbec` RAW v2 with matching specimen/session IDs.
4. Metadata survives a fresh process, and `show-capture --verify` rejects corrupted/missing RAW files.
5. ProcessingRun input references are enforceably limited to the same session, with transactional states and a persisted event trail.
6. SQLite foreign keys enabled, duplicate/invalid paths rejected, version guard works, and PRE-03 RAW bytes are unchanged.
7. Branch remains `feat/pre-02-raw-rgbd-contract`; no merge into `main` before PRE-06.

## 6. Limitations / next milestone

This is GĐ0 foundation only; neither a Qt Project workspace, a VTK point-cloud viewer, registration, guided handheld trajectory nor live object recognition is present. A separate PRE-06 end-to-end acceptance pass should test failure injection (including missing RAW/DB state, interrupted registrations and recovery), metadata lifecycle through a fresh process and the real Gemini2 capture pathway. PRE-06 is the gate to enter functional GĐ1 3D Core.
