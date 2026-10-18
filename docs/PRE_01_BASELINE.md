# PRE-01 — Baseline & repository hygiene (2026-10-18)

## Scope and provenance

- Repository: `https://github.com/vdtrong2051/sacntopath` (the spelling `sacntopath` is intentional: this is the user's repository).
- Source baseline / comparison point: `main` commit `f461628a9af85dc8ae24e1ff9d62a33bd0479acf`.
- This PRE-01 patch updates **only** `.gitignore`, `.vscode/settings.json`, README and documentation. It does **not** alter C++20, pybind11, Python application behavior, storage schemas or tests.
- User-approved **active deployment**: handheld Gemini 2, human-operated planned/guided trajectory, future live object recognition overlay. No current actuator, turntable, encoder, Pi/ESP32 or automated stage. Object detection, tracking, motion/pose estimation and guidance are **not yet coded**.

## Evidence already observed on the Windows workstation (before PRE-01)

| Test / observation | Evidence from user's console | Interpretation |
|---|---|---|
| Gemini 2 real native Python acquisition | `--once` exited `0`, `capture.valid=true` | One RAW RGB-D frameset accepted by native contract |
| RGB stream | `1920x1080`, MJPEG; 364379 encoded bytes in observed capture | Compressed Color packet, **not** aligned RGB array |
| Depth stream | `1280x800`, Y16 → owned NumPy `uint16` shape `(800,1280)` | Raw depth safely copied to Python |
| Depth scale | `0.001000000` m/unit | Scale confirmed for observed mode |
| Calibration | depth `fx=610.908264`; D2C `tx_mm=-13.787516` | Values exposed; no dimensional accuracy certification |
| Timing | timestamp delta `3308` μs for one frameset | Observation only; no sync/latency/accuracy guarantee |
| Lifetime | `buffer.copy_survived_close=true` | Python buffers remain after camera close |
| Python native self-test | `native.import=true`, `native.memory_ownership=true`, exit `0` | Module import + synthetic ownership check passes |
| Python regression | `7 passed in 0.24s` | Seven offline tests passed on user's PC |
| C++ regression | `ctest` `2/2 passed` | Two offline C++ smoke tests passed on user's PC |
| Real storage | `capture.saved=false` | **Real Capture Storage NOT implemented** |

These are **user-observed previous test results**, not tests repeated by PRE-01 in a Windows hardware environment. Re-run acceptance commands below after applying the patch before locking PRE-01.

## Known critical gaps (intentionally NOT fixed here)

1. v1 `FrameBundle`/`SessionStore` assumes color/depth share grid, and storage forces `rgb_registered_to_depth=True`; native capture contains **unaligned** Color MJPEG 1920×1080 and Depth Y16 1280×800. This is **PRE-02/PRE-03**.
2. No persistent color/depth intrinsic pair, distortion/extrinsics/frame timestamps in v1 Capture metadata. This is **PRE-02**.
3. `OrbbecSDKv2Source` Python adapter is a stub; native pybind11 exists but does not persist a real capture. This is **PRE-04**.
4. Project/Specimen/Session lifecycle, ProcessingRun persistence and logging are incomplete. This is **PRE-05**.
5. 3D viewer, PLY/PCD import, metric point picking, moving-camera pose, object recognition and trajectory guidance are future functional milestones, **not PRE-01**.

## Validated compiler workaround already present in source

In `cpp/CMakeLists.txt`, pybind11 Release import previously raised Windows access violation `0xC0000005` with MSVC 19.51 / VS 2026. The observed self-test became successful after the compatible build definition was added:

```cmake
pybind11_add_module(_scantopath_native MODULE NO_EXTRAS python/orbbec_bindings.cpp)
if(MSVC)
    target_compile_definitions(_scantopath_native PRIVATE _DISABLE_CONSTEXPR_MUTEX_CONSTRUCTOR)
endif()
```

Removing LTO alone (`NO_EXTRAS`) **did not** resolve the crash. The mutex compatibility define correlated with successful import on this machine; it must be revalidated after runtime/compiler upgrades. PRE-01 **does not change CMake**.

## PRE-01 post-apply acceptance on user's Windows PC

From `E:\1_BigProject\scantopath\scantopath-software` with existing `.venv` and `build-orbbec` configured:

```powershell
# 1. Show exactly what changed; only .gitignore, .vscode and docs should differ.
git status --short
git diff --stat

# 2. Regression: Python synthetic/storage tests
$pyExe = (Resolve-Path '.\.venv\Scripts\python.exe').Path
& $pyExe -m pytest -q .\tests
if ($LASTEXITCODE -ne 0) { throw 'Python regression failed' }

# 3. Regression: C++ offline tests
ctest --test-dir .\build-orbbec -C Release --output-on-failure
if ($LASTEXITCODE -ne 0) { throw 'C++ regression failed' }

# 4. Native import / memory ownership (SDK path may need adapting on other PCs)
$env:SCANTOPATH_ORBBEC_SDK_BIN = 'E:\1_BigProject\scantopath\_sdk\OrbbecSDK_v2.10.6\bin'
& $pyExe -u -X faulthandler -m scantopath.acquisition.native --self-test
if ($LASTEXITCODE -ne 0) { throw 'Native self-test failed' }

# 5. Optional hardware recheck: Gemini 2 connected, OrbbecViewer closed
& $pyExe -u -X faulthandler -m scantopath.acquisition.native --once
if ($LASTEXITCODE -ne 0) { throw 'Hardware once failed' }
```

**PRE-01 acceptance gate:** docs reflect the actual functional status and handheld-first scope, `.gitignore` is valid, CMake workaround is documented, no application/source files are modified, regressions pass on user's workstation, and the PRE-01 branch is reviewed/merged. The operator must confirm Windows test outputs; offline or historical results alone do not sign off post-patch acceptance.

## Next and not yet approved

PRE-02 is the **Raw RGB-D Capture Contract v2 design/implementation** and must be separately authorized. PRE-01 does not silently start PRE-02 or modify storage data.
