# PRE-04 — Gemini 2 one-shot RAW acquisition → Storage v2

**Implementation scope:** Python integration only. The PRE-03 branch baseline is `92086786f44fc57e08a57572a39e35cdc37dccec` on `feat/pre-02-raw-rgbd-contract` (PRE-03 accepted/pushed). No code is changed in native C++, CMake, pybind11, PRE-02 schema or PRE-03 storage.

## Pipeline and responsibilities

```text
Orbbec Gemini 2 USB3 (handheld, no actuator)
  -> C++20 OrbbecCameraSource (unchanged)
  -> pybind11 RgbdCapture (unchanged; independently owned bytes)
  -> close native camera
  -> Python orbbec_adapter.raw_capture_from_native
  -> RawRgbdCaptureMetadataV2 + immutable MJPEG/Y16 bytes (PRE-02)
  -> SessionStore.commit_raw (PRE-03)
  -> SessionStore.read_raw (SHA-256 verified)
  -> separate-process --verify (hardware not required)
```

**New files only:**

1. `src/scantopath/acquisition/orbbec_adapter.py` — maps the existing pybind11 packet to the strict PRE-02 schema; one-shot source with `try/finally` to close the camera.
2. `src/scantopath/acquisition/capture_once.py` — standalone CLI for `--once` or `--verify`; does not modify existing synthetic CLI.
3. `tests/test_pre04_orbbec_adapter.py` — mocked-native, offline integration and subprocess replay tests, including full-resolution Y16 fixture.
4. `docs/PRE_04_GEMINI2_STORAGE_INTEGRATION.md` — this document.

### Invariants

- Color MJPEG is stored exactly as returned by `.color.bytes`; Depth Y16 exactly as `.depth.bytes`, with no JPEG decode, color registration, interpolation, resizing, depth conversion, or byte-order reinterpretation.
- Color 1920x1080 and Depth 1280x800 are allowed independent pixel grids.
- Metadata includes both intrinsics, both distortion models (SDK coefficient order), Depth-to-Color row-major rotation, translation **in millimeters**, and depth scale **meters per unit**.
- Each stream retains its SDK-reported frame index and timestamp in microseconds. A requested frame sync and one observed delta **are not proof** of synchronization quality.
- `camera_pose=None`: moving handheld camera pose is **not estimated**. No stage/turntable/encoder/actuator controller is involved.
- `measured=True` denotes sensor-sourced data, **not validated geometric precision**.
- `sdk_version=None` and `serial=None` remain unknown because the existing native packet does not expose them; do not fabricate these values.
- The native camera is always closed on read errors and after receiving one frameset. The raw conversion intentionally happens **after close**, relying on the proven owned native buffers. A storage failure cannot leave the camera open.
- `SessionStore.commit_raw()` writes compressed color and Y16 bytes plus metadata, SHA-256 manifest and `COMMITTED` marker; `read_raw()` verifies every file. This does **not** guarantee complete power-loss durability or authenticate a malicious writer who can alter the manifest.
- No live preview, detection, trajectory guidance, GUI integration, point cloud processing, registration, fusion or actuator control in PRE-04.

## Windows test commands

In `E:\1_BigProject\scantopath\scantopath-software`, on the already-established Python 3.12 `.venv`:

```powershell
$pyExe = (Resolve-Path '.\.venv\Scripts\python.exe').Path
& $pyExe -m pytest -q .\tests
Write-Host "PythonExitCode=$LASTEXITCODE"
ctest --test-dir .\build-orbbec -C Release --output-on-failure
Write-Host "CTestExitCode=$LASTEXITCODE"
$env:SCANTOPATH_ORBBEC_SDK_BIN = 'E:\1_BigProject\scantopath\_sdk\OrbbecSDK_v2.10.6\bin'
& $pyExe -u -X faulthandler -m scantopath.acquisition.native --self-test
Write-Host "SelfTestExitCode=$LASTEXITCODE"
```

The offline tests use mocked native objects only. With the same Windows symlink restrictions observed during PRE-03, **52 passed / 1 skipped** out of 53 tests is an acceptable expectation; with symlink privileges available, **53 passed** is expected. A skip in a different test must be investigated. The C++ baseline remains two tests.

## One real Gemini 2 capture on Windows

**Preconditions:** Connect Gemini 2 via USB3, close OrbbecViewer, ensure the native `.pyd` is compiled and `SCANTOPATH_ORBBEC_SDK_BIN` points at the correct SDK `bin` directory.

```powershell
& $pyExe -u -X faulthandler -m scantopath.acquisition.capture_once `
  --once --output '.\scantopath-data' --session 'handheld-001' --specimen 'sample-001'
Write-Host "CaptureExitCode=$LASTEXITCODE"
```

Expected JSON includes `"saved": true`, `"checksum_verified": true`, `"alignment_mode": "disabled"`, `"camera_pose_known": false`, MJPEG and Y16 stream fields, device timestamps and `capture_path`. **The real data stays in the ignored `scantopath-data/` folder; never commit it to a public repository.**

Close that terminal/process, open a **new PowerShell process** with `.venv` activated, and paste the exact `capture_path` printed by the first command:

```powershell
$pyExe = (Resolve-Path '.\.venv\Scripts\python.exe').Path
& $pyExe -m scantopath.acquisition.capture_once `
  --verify 'PASTE_EXACT_CAPTURE_PATH_HERE' --output '.\scantopath-data'
Write-Host "ReplayExitCode=$LASTEXITCODE"
```

The second command **never loads the native SDK or opens the camera**; it checks the existing storage manifest and schema. If it raises a checksum/metadata error, PRE-04 is **not accepted**. Compare both commands' `capture_id`, dimensions, timestamps and data lengths. Do not share device serial numbers or local SDK logs publicly.

## PRE-04 acceptance gate

1. Full Python regression passes, including new tests for mapping, provenance, calibration, timestamps, alignment/unknown handheld pose, camera lifecycle, corrupted storage, separate-process replay and realistic 1280x800 Y16 bytes.
2. CTest `2/2` and native `--self-test` both pass on Windows.
3. Physical Gemini 2 one-shot CLI saves one RAW capture, exits with `0` and reports `saved=true`, `checksum_verified=true`; camera closes even on failures.
4. A fresh Python process with `--verify` reopens the same capture and verifies bytes and metadata via SHA-256 manifest.
5. No existing C++/pybind11, v1 capture, metadata schema or Storage API was changed, and no actuator dependency was introduced.
6. Only after the user shares passing Windows outputs: commit/push on the **existing** `feat/pre-02-raw-rgbd-contract` branch, without merging into `main` until the agreed consolidated PRE-06 gate.
