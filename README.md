# ScanToPath 2026 — Software Foundation & Gemini 2 Acquisition

**Baseline:** commit `f461628a9af85dc8ae24e1ff9d62a33bd0479acf` (before PRE-01), validated on user's Windows PC on 2026-10-18; see [`docs/PRE_01_BASELINE.md`](docs/PRE_01_BASELINE.md). PRE-01 changes documentation and repository hygiene only; it does not implement new processing features.

## Product scope — handheld first

The **current software mode** uses an **Orbbec Gemini 2 held and moved by a person**. Scanning is intended to follow a **planned/guided handheld trajectory** and eventually show live object recognition/tracking overlays. **Trajectory guidance and object perception are requirements for later increments, not existing features.** The present build does not estimate a moving camera's pose or reconstruct a multi-view 3D object.

**No actuator is integrated:** no turntable, motor, encoder, motion controller, Raspberry Pi or ESP32 is required for today's software. A motorized rig is a potential future integration, not an assumption in current pose/data contracts. A *planned* path is never proof of *measured* camera poses.

## What works today

- Offline synthetic `FrameBundle`, validated v1 capture metadata, per-capture staging/commit, reload/verification and CLI fixture demo.
- C++20 scalar depth-point unprojection/transforms and vendor-neutral RAW RGB-D packet validation.
- Gemini 2 native acquisition via OrbbecSDK v2.10.6 and C++ `OrbbecCameraSource`, bridged to Python 3.12 by pybind11. Windows camera/SDK tests were performed by the user (firmware 1.4.98).
- Real RAW acquisition was user-tested: RGB **1920 × 1080 MJPG**, Depth **1280 × 800 Y16**, **unaligned**, depth scale **0.001 m/unit** for the tested mode; independent NumPy-owned depth memory after source close.
- Minimal PySide6 tab shell (placeholder; no 3D viewer or camera panel).

**Important boundary:** native `--once` captures one real RGB-D pair **in memory only** (`capture.saved=false`). The existing `SessionStore` accepts **aligned-looking synthetic** `rgb: uint8[H,W,3]` plus `depth: uint16[H,W]`; it **must not** be used as-is to store the native unaligned MJPEG/Y16 pair. That mismatch is addressed by PRE-02/03/04, not PRE-01.

## What is NOT implemented

Project/Specimen lifecycle persistence, durable ProcessingRun service, real camera RAW capture storage/replay, depth-to-color alignment, moving-camera pose estimation, scan-path guidance, live object recognition/tracking/segmentation, point-cloud import/viewer, registration, fusion, metric-accuracy validation, and actuator control.

## Python fixture setup (Windows, repository root)

```powershell
.\.venv\Scripts\python.exe -m pip install -e '.[test,ui]'
.\.venv\Scripts\python.exe -m pytest -q .\tests
.\.venv\Scripts\python.exe -m scantopath.cli demo --output .\scantopath-data
.\.venv\Scripts\python.exe -m scantopath.cli verify --output .\scantopath-data
.\.venv\Scripts\python.exe -m scantopath.ui.main
```

The PySide6 shell is optional and must be launched on a desktop session.

## C++ offline regression

```powershell
cmake -S cpp -B build -DBUILD_TESTING=ON
cmake --build build --config Release
ctest --test-dir build -C Release --output-on-failure
```

The offline build does not require Gemini 2 or its SDK.

## Gemini 2 Windows acquisition (opt-in)

Requirements: Windows x64, MSVC, Python 3.12 x64 in `.venv`, pybind11, OrbbecSDK v2.10.6 developer package and its runtime DLL, and the camera connected over USB 3.0. Close OrbbecViewer before testing.

See [`docs/GD1_2_3_2_2_PYBIND11.md`](docs/GD1_2_3_2_2_PYBIND11.md) for the complete CMake SDK/binding configuration. The existing CMake includes the **MSVC 2026 compatibility workaround** `_DISABLE_CONSTEXPR_MUTEX_CONSTRUCTOR` and pybind11 `NO_EXTRAS`; do not remove them without regression tests.

```powershell
$env:SCANTOPATH_ORBBEC_SDK_BIN = 'E:\1_BigProject\scantopath\_sdk\OrbbecSDK_v2.10.6\bin'
.\.venv\Scripts\python.exe -u -X faulthandler -m scantopath.acquisition.native --self-test
# Close OrbbecViewer; real hardware required:
.\.venv\Scripts\python.exe -u -X faulthandler -m scantopath.acquisition.native --once
```

Confirm `$LASTEXITCODE -eq 0` after each command. The SDK path above is **the validated local machine path**, not a portable installation location.

## Data safeguards and roadmap

- Synthetic data: `measured=false`; real Orbbec provenance does **not** imply calibrated metric accuracy.
- RAW Color MJPEG and Depth Y16 have **different pixel grids**, with alignment disabled; do not invent registered RGB/depth or camera pose.
- Depth units: raw integer × `depth_scale_m_per_unit` = meters. SDK depth-to-color translation is exported in **millimeters**.
- `COMMITTED` indicates a completed local per-capture write, not guaranteed power-loss durability on every filesystem.
- The accepted 20-session roadmap remains unchanged. PRE-01–06 are an **explicit preparatory overlay** before functional GĐ1 (3D Core), not a renumbering of those sessions. See [`docs/ROADMAP.md`](docs/ROADMAP.md).

See [`docs/ARCHITECTURE.md`](docs/ARCHITECTURE.md), [`docs/PRE_01_BASELINE.md`](docs/PRE_01_BASELINE.md), [`docs/GEMINI2_VALIDATION.md`](docs/GEMINI2_VALIDATION.md).
