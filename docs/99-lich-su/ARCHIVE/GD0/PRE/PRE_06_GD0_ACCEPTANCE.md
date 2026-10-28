# PRE-06 — GĐ0 Software Skeleton: integrated acceptance dossier

**Target repo:** `https://github.com/vdtrong2051/sacntopath`  
**Existing development branch:** `feat/pre-02-raw-rgbd-contract`  
**Pre-patch audited HEAD:** `50d5828a0cf77b12a43deaf7b7e2051c5a2904dd` (PRE-05).  
**Date of user-supplied Windows acceptance evidence:** 2026-10-18.  
**Status:** **06.1–06.5 user-evidence verified; 06.6 requires applying this acceptance patch, Windows regression, commit/push, PR review and merge.** Do not claim GĐ0 merged/locked from this document alone.

## 1. Acceptance scope and boundaries

This is an acceptance package, **not** a new processing feature. The only new source artifact is `tests/test_pre06_gd0_acceptance.py`; this report is the other new file. Existing C++20/OrbbecSDK/pybind11, RAW contract/storage, Qt shell, SQLite schema, CLI and Python runtime code are untouched.

Acceptance covers:

1. Offline regression of synthetic v1 + RAW v2 contracts and filesystem storage.
2. Native C++/pybind11 offline regressions on the user's Windows workstation.
3. One physical handheld Orbbec Gemini 2 RAW capture, persistence, fresh read-back and SHA-256 verification.
4. SQLite Project → Specimen → ScanSession → Capture → ProcessingRun and durable audit trail.
5. Negative cases: same-size byte corruption, missing RAW file, incomplete `.partial`, unsuccessful SQLite registration and transaction rollback (latter two under automated synthetic tests).
6. Git history/documentation review and consolidated merge gate.

**Not accepted / not implemented in GĐ0:** metric reconstruction, depth/color alignment, pose estimation for a moving camera, validated frame synchronization or dimensional accuracy, multi-view fusion, point-cloud import/viewer, feature extraction, object detection/tracking, scan-trajectory guidance, live preview or actuators. `measured=true` records physical-sensor origin only. The current architecture is **handheld Gemini 2 without any stage, encoder or motion controller**.

## 2. User-observed Windows evidence — PRE-06.1 to PRE-06.5

The following results are from the user's PowerShell log; no source modification was performed by these commands. They do **not** imply an independent remote hardware test.

| Gate | Observed evidence | Status / interpretation |
|---|---|---|
| 06.1 baseline | `git branch --show-current` = `feat/pre-02-raw-rgbd-contract`; `git log -1 --oneline` = `50d5828`; `git status --short` empty | **PASS**: expected clean baseline. |
| 06.1 backup | SQLite backup via `sqlite3.Connection.backup()` executed without error; RAW capture directory copied to a timestamped backup outside repository | **PASS with caveat**: copy commands returned without error; separate backup-restore readback was not shown. Do not call this disaster-recovery certified. |
| 06.2 Python | `74 passed, 1 skipped in 18.18s`, exit code `0` | **PASS with documented skip**. |
| 06.2 skip | `tests/test_raw_storage.py:221: Creating symlinks requires Windows privilege` | **Exception**: symlink-rejection test was NOT executed on this Windows user account. No assertion of Windows symlink gate completeness. |
| 06.2 C++ | `core_smoke` and `rgbd_contract_smoke`: `2/2 passed`, exit code `0` | **PASS**. |
| 06.2 native binding | `native.import=true`, `native.memory_ownership=true`, `native.hardware_access=false`, exit code `0` | **PASS** for module import/buffer lifetime; the self-test does not open hardware. |
| 06.3 historical RAW | `capture_id=2c15ecedf3544822874a7c015e4a4dc1`, RAW v2, `kind=orbbec`, `saved=true`, `checksum_verified=true` | **PASS**: historical capture reopened. |
| 06.3 registry | `show-capture --verify` returned the same historic ID and relative path, `tree --project project-001` retained metadata relationship | **PASS**. |
| 06.3 SQLite | `PRAGMA integrity_check` → `ok`; `PRAGMA foreign_key_check` → `[]` | **PASS** at time of inspection. |
| 06.4 new physical capture | Session `pre06-20261018214659`, new capture `03f92f2102b746188dd5956a4ed3bb04`, `CaptureExitCode=0` | **PASS** for one physical one-shot capture. |
| 06.4 new RAW | Color MJPEG **1920×1080**, 358275 bytes; Depth Y16 **1280×800**, 2048000 bytes; scale `0.001` m/unit; `saved=true`, `checksum_verified=true` | **PASS** for unaligned RAW and persistent byte integrity. |
| 06.4 timestamps | Color `501819198` µs; Depth `501806207` µs; delta `12991` µs; `camera_pose_known=false`, `alignment_mode=disabled` | **DIAGNOSTIC ONLY**, not sync accuracy or camera trajectory proof. |
| 06.4 replay/DB | Independent `--verify` output reports `checksum_verified=true`; `register-capture` returned the same Capture ID and correct session/specimen ID | **PASS**. |
| 06.4 ProcessingRun | `pre06-run-20261018214742` transitioned `pending → running → succeeded`; `show-run` and project tree preserved linkage | **PASS** for metadata lifecycle. The `sha256-readback` check was executed **before** the run record was started; the run represents an operator-recorded prior check, not an automatically orchestrated processing job. |
| 06.4 closure/audit | Session reported `state=closed`; latest audit event ID `10` with creation/registration/run/start/finish/close events | **PASS** for metadata/audit persistence in successive CLI invocations. |
| 06.5 corruption | Changed one byte in `color.mjpg` of a **copied** Capture; `ValueError: RAW checksum mismatch: color.mjpg`, `CorruptCaptureExitCode=1` | **EXPECTED REJECTION = PASS**. |
| 06.5 missing file | Removed `depth.y16` from copied Capture; `ValueError: RAW capture files are incomplete or unexpected`, `MissingFileExitCode=1` | **EXPECTED REJECTION = PASS**. |
| 06.5 original unaffected | `show-capture --verify` on original new Capture succeeded again | **PASS**: destructive faults were confined to test copy. |

**Evidence limitations:** The pasted log does not demonstrate recovery from abrupt power loss, atomicity across RAW filesystem and SQLite (which is not provided), a physically measured synchronized exposure time, a calibrated 3D measurement, an actual external symlink attack on Windows, or automatic RAW-to-SQLite registration. `ProcessingRun` indicates recorded state rather than algorithm execution. The event trail is SQLite metadata, not an independently tamper-proof audit log.

## 3. PRE-06 automated acceptance tests

`tests/test_pre06_gd0_acceptance.py` adds **6 isolated synthetic tests**; they never open hardware and never use the user's `scantopath-data/` folder:

1. v1 and v2 captures registered together; ProcessingRun lifecycle, audit, SQLite integrity, reopen and RAW byte immutability.
2. RAW committed while metadata registration initially fails due to missing Session; safe re-registration after creating the hierarchy.
3. Registered RAW file corrupted after registration: `verify_raw=True` detects error, registry remains intact and verification succeeds after restoring the test byte.
4. An interrupted `.partial` directory is not listed as committed and is rejected by the metadata registry.
5. Injected failure while logging a Capture registration rolls back database changes and leaves RAW retryable; successful retry creates one event.
6. SQLite backup API produces a reopenable metadata file while leaving the source usable.

**Independent offline check** using the local PRE-05 source tree on Linux/Python 3.13: **81 passed** (75 pre-existing + 6 new), no skipped tests in that environment. The previous Windows baseline was **74 passed, 1 skipped** out of 75; after installing these tests, **expected Windows outcome is 80 passed, 1 skipped** if the same symlink privilege limitation persists. Do not label the new Windows test run passed before receiving its output.

## 4. Run on Windows — existing branch, no new branch

Preflight must report the same branch and exact HEAD `50d5828a0cf77b12a43deaf7b7e2051c5a2904dd` and no tracked/untracked changes **before patch**. Apply `apply.ps1` from the PRE-06 ZIP; it refuses a dirty repo or unexpected ref and **does not commit/push/merge**.

```powershell
cd E:\1_BigProject\scantopath\scantopath-software
$pyExe = (Resolve-Path '.\.venv\Scripts\python.exe').Path

# New PRE-06 tests first: 6 must pass.
& $pyExe -m pytest -q -rs .\tests\test_pre06_gd0_acceptance.py
if ($LASTEXITCODE -ne 0) { throw 'PRE-06 acceptance tests failed' }

# Full suite; Windows may skip exactly one symlink test.
& $pyExe -m pytest -q -rs .\tests
if ($LASTEXITCODE -ne 0) { throw 'Python regression failed' }

ctest --test-dir .\build-orbbec -C Release --output-on-failure
if ($LASTEXITCODE -ne 0) { throw 'C++ regression failed' }

$env:SCANTOPATH_ORBBEC_SDK_BIN = 'E:\1_BigProject\scantopath\_sdk\OrbbecSDK_v2.10.6\bin'
& $pyExe -u -X faulthandler -m scantopath.acquisition.native --self-test
if ($LASTEXITCODE -ne 0) { throw 'Native binding regression failed' }

git diff --check
git status --short
```

The **physical** PRE-06.4 and fault-injection PRE-06.5 were already performed and shared by the operator; do not repeat destructive steps on live data. No new camera shot is necessary merely to verify this documentation/test-only patch.

## 5. Consolidated merge gate (PRE-06.6)

**Before recording GĐ0 as locked**, obtain all of the following:

- [x] PRE-06.1 clean baseline and pre-test backup command success recorded.
- [x] PRE-06.2 Windows regression on PRE-05 baseline recorded (`74 passed, 1 skipped`; CTest `2/2`; native self-test exit `0`).
- [x] PRE-06.3 previous Gemini2 capture rechecked and SQLite integrity verified.
- [x] PRE-06.4 second real Gemini2 capture was committed, reloaded, registered, and the ProcessingRun/session/audit lifecycle recorded.
- [x] PRE-06.5 controlled corruption and missing-file faults rejected; original Capture still valid.
- [ ] PRE-06 6 new offline acceptance tests re-run on operator's Windows PC and full **81-case suite** reported.
- [ ] Review new test source and this dossier; commit/push **only** these two PRE-06 files on the existing branch.
- [ ] Open/review consolidated Pull Request to `main`; merge once all required checks and review succeed.
- [ ] On `main`, `git pull --ff-only` and run final smoke/regression; record final merge commit and GĐ0 lock.

**Decision:** PRE-06.1–06.5 = **PASS WITH DOCUMENTED LIMITATION**; PRE-06.6 = **PENDING**, until these checkboxes are done. Do not assert that GĐ0 is fully locked/merged earlier.

## 6. Traceability and handoff to GĐ1

- `docs/PRE_01_BASELINE.md` — hardware-first baseline, handheld scope, known gaps.
- `docs/PRE_02_RAW_RGBD_CONTRACT.md` — RAW stream/calibration/unknown-pose schema v2.
- `docs/PRE_03_RAW_STORAGE.md` — byte-preserving storage, SHA-256 and v1 coexistence.
- `docs/PRE_04_GEMINI2_STORAGE_INTEGRATION.md` — real one-shot Gemini 2 capture and CLI replay.
- `docs/PRE_05_GD0_METADATA_PERSISTENCE.md` — Project/Specimen/Session/Capture/ProcessingRun + SQLite and audit.
- `docs/ROADMAP.md` — accepted functional roadmap; **GĐ1 = 3D Core** (sessions 06–08), not another iteration of acquisition. Preserve the original session plan.

No actuator/turntable/encoder assumption is introduced. Actual moving-camera pose and interactive trajectory guidance remain future milestones. GĐ1 should start only after the consolidated PRE-06 gate is closed and accepted.
