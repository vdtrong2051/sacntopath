# ScanToPath — GD2-09.09.5 Final Acceptance Protocol

**Stage:** Acceptance in progress until the operator-run evidence gates pass.
**Scope:** GD2-09.09.1–09.09.4 and older existing regression tests.
**Target branch:** `feat/gd2-mvpb-20261104`.
**Data safety:** Offline E2E test uses ONLY `pytest`'s `tmp_path/scantopath-data`. The actual `<repo>/scantopath-data` is inspected in **read-only** mode. It is NEVER reinitialized, migrated, overwritten, or used by the E2E fixture.

## Traceable acceptance matrix

| Layer | Acceptance evidence | Risk covered |
|---|---|---|
| Project bootstrap | Explicit `initialize_empty_data_workspace` into an empty temporary folder, SQLite schema v2 | No implicit database initialization or migration |
| CRUD | Project, Specimen and Session created and updated through `ProjectWorkspaceService` | Parent/child correctness; persistence |
| Synthetic acquisition | `CapturePipelineService` with a labelled SYNTHETIC keyframe-port fake, not Gemini 2 | Preflight, ordered frame indices and unique Capture IDs |
| Persistence | `CaptureCommitService` and `NumberedCapturePersistenceAdapter` | Real RAW/SQLite commit, numbered folders, non-overwrite |
| Integrity | Manifest SHA-256 and `PRAGMA integrity_check`, FK check, zero pending reservations | Payload corruption and orphaned reservations |
| Replay/Decode | `RawReplayService`, `RawReaderAdapter`, `RgbdDecoder`, Pillow | RGB JPEG and native Y16 read back faithfully |
| Session lifecycle | Closing Session rejects new capture while preserving offline replay | Immutable history and lifecycle guard |
| Qt integration | Real MainWindow, Project Tree, Capture selection, automatic RAW Replay and two tabs | Selection-to-replay wiring and stale UI |
| Activity | Operational timeline remains distinct from SQLite Audit | No fake TaskManager progress or fake audit |
| Reopen | New `ProjectWorkspaceService` reads saved Project/Session/Captures | Persistence across service instance lifetimes |
| Negative path | Tamper with RAW in a *second temporary store*, require Replay rejection | Integrity failure is detectable |
| Whole repo | `python -m pytest -q -ra tests` | **All** collected existing Python tests (including viewer/native/performance) |
| Architecture | `scripts/check_architecture_boundaries.py` | Import-boundary contract |
| Syntax | `compileall` over source/tests/scripts | Parse errors |
| Real existing store | `scripts.gd2_09_09_1_inspect_store` | Read-only SQLite integrity and zero reservations |
| C++ CTest | Auto-runs if a configured CTest build directory exists | C++ tests only when present and configured |

## Required operator command

```powershell
$repo = 'E:\1_BigProject\scantopath\scantopath-software'
Set-Location $repo
& .\.venv\Scripts\python.exe -u -X utf8 -m scripts.gd2_09_09_5_acceptance `
    --repo $repo --require-store --ctest auto
$LASTEXITCODE
```

The script writes a versioned evidence directory **outside the repo** at
`E:\1_BigProject\scantopath\_setup\GD2_09_09_5_RESULTS\<UTC timestamp>`:

- `e2e.xml`, `offline_e2e.log`
- `all_pytest.xml`, `all_pytest.log`
- `architecture.log`, `compileall.log`, `operator_store_read_only.log`
- `ctest.log` when configured
- `summary.json`, `ACCEPTANCE_REPORT.md`

`PASS_OFFLINE_SOFTWARE` means all required Python/E2E/architecture/syntax/store gates passed. It does **not** claim Gemini 2 hardware, manual GUI quality, or a C++ CTest suite that was never configured. The XML `skipped` count must be reviewed before final sign-off.

## Manual closeout (not automatically proven)

1. Confirm the window has four workspaces and the Capture page has two tabs.
2. Verify no horizontal scrolling or clipped controls at approximately 940×620, 1366×768 and 1920×1080, adjusting for DPI and available docks.
3. Reopen the **existing** store, select C0001 in the Project Tree, replay RGB/Depth, open the activity timeline and inspect the separate SQLite audit page.
4. Confirm the closed Session T0001 cannot accept a new Capture, while the old Capture can still be replayed.
5. If physical Gemini 2 acceptance is in scope, perform a **separate explicit hardware run**; do not mistake the synthetic E2E for a camera run.
6. Check Git diff/working tree, attach the generated report, then commit only the three added source/test/doc files after reviewing results.

## Non-goals

No changes to SDK, schema, existing RAW, VTK 3D processing, AI geometry, or production camera capture. No silent migration, creation of a new operator Session, Git push/merge or background automation.
