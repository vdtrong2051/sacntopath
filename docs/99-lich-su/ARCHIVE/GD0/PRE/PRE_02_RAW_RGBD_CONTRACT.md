# PRE-02 — RAW RGB-D Capture Contract v2

Status: **source patch ready; Windows user acceptance pending**. Based on main HEAD `4944afefa8e94e9b235a35828c2dc81369037a09` after PRE-01 merge.

## Scope and unchanged components

New **additive** files only:

- `src/scantopath/domain/raw_rgbd.py` — Pydantic v2 metadata contract.
- `src/scantopath/acquisition/raw_rgbd.py` — immutable bytes payload contract.
- `tests/test_raw_rgbd_contract.py` — synthetic offline tests.
- `docs/PRE_02_RAW_RGBD_CONTRACT.md` — this document.

**Unchanged:** existing `CaptureMetadata` schema v1, `FrameBundle`, `SyntheticSource`, `SessionStore`, native `OrbbecCameraSource`, pybind11, CMake, CLI, PySide6. **NO raw disk writes** in PRE-02; PRE-03 implements persistence, and PRE-04 the native adapter.

## Payload and metadata semantics

| Field | Requirement |
|---|---|
| `schema_version` | `2`, distinct from v1 |
| `color` | compressed **MJPEG** as immutable bytes; independent width/height/frame index/timestamp (us)/payload length |
| `depth` | little-endian **Y16**, immutable bytes of exactly `width × height × 2`; independent timestamp/frame index |
| `color_intrinsics`, `depth_intrinsics` | distinct width/height/fx/fy/cx/cy, finite, dimensions agree with their respective frames |
| `color_distortion`, `depth_distortion` | SDK model ID and eight coefficients ordered `k1,k2,k3,k4,k5,k6,p1,p2`; do not reinterpret the SDK model |
| `depth_to_color` | SDK row-major 3×3 rotation and translation in **mm**, not meters |
| `depth_scale_m_per_unit` | strictly positive finite; raw depth × scale = meters |
| `alignment_mode` | **`disabled`** (only accepted value in this RAW v2 contract) |
| `frame_sync_requested` | whether SDK requested synchronization, not proof of simultaneous exposure |
| `timestamp_domain` | `sdk_reported_unverified`; delta only diagnostic unless clock-domain parity established |
| `camera_pose` | `None`: unknown for current handheld mode; no encoder/stage assumption |
| `kind`, `measured` | synthetic fixture must be `synthetic/false`; real sensor `orbbec/true` means *sensor-sourced*, **not** validated geometric accuracy |
| `captured_at` | timezone-aware host datetime; distinct from SDK timestamps |

The byte-level contract uses a JPEG SOI prefix check, exact buffer sizes and immutable `bytes`; it does **not** decode JPEG, perform color-to-depth alignment, estimate camera pose, assess sync quality, or check dimensional accuracy. `depth_u16_copy()` explicitly allocates a separate NumPy `uint16[H,W]` copy for diagnostics. The synthetic unit test payload starts with JPEG SOI but is **not an imaging-quality JPEG fixture**; tests validate the contract, not image decoders.

`CaptureKind.REPLAY` is deliberately not accepted as a new RAW measurement source in this version: replay of a previously persisted real capture should **preserve original provenance** and be recorded separately by the future read/processing operation. PRE-03 can record replay actions without forging a second hardware measurement.

## Deferred work and boundary

PRE-03 will define raw files, checksum manifests, atomic commit/read and v1 compatibility. PRE-04 will map the real pybind11 `RgbdCapture` and device info to v2 values (and record SDK version only when known), saving a frame from a real Gemini 2. Object detection, tracking, segmentation, trajectory guidance, moving-camera pose estimation, point-cloud processing and actuator control are out of scope.

## Validation commands (Windows project root)

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

No hardware capture required for PRE-02: it cannot persist real frames yet. The PRE-01 native `--once` result remains a prior acceptance observation, not a new claim made by this patch.

## PRE-02 acceptance gate

1. New standalone RAW v2 model and payload validate independent image grids, calibration, timestamps, scale, explicit lack of alignment/pose and sensor provenance.
2. Reject malformed depth length, payload length mismatches, non-finite calibration, invalid IDs, fake alignment/pose and synthetic measurement flag.
3. Schema v2 survives JSON serialization/deserialization; bytes payload remains immutable and depth `uint16` roundtrips without reinterpretation.
4. Previous 7 Python tests and 2 C++ CTests pass unchanged on Windows.
5. PRE-02 does not write raw data to disk, start a camera, modify v1 storage, or introduce an actuator dependency.

Commit and merge **only after** Windows regression approval. Then separately authorize PRE-03.
