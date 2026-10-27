# GĐ1.2.3.2.2 — pybind11 native bridge

## Scope (strict)

- Imports the previously validated `OrbbecCameraSource` from C++20 into Python 3.12.
- Returns owned `bytes` (MJPG) and owned NumPy `uint16` depth arrays. Copies remain valid after `close()`.
- Exposes camera identity, stream metadata, depth scale (m/unit), intrinsics, distortion model ID, D2C extrinsics (translation **mm**), and time delta (µs).
- Native module never auto-opens camera upon import. `SCANTOPATH_BUILD_PYTHON_BINDINGS=OFF` by default.
- Does NOT save capture to disk, create a point cloud, integrate UI, or claim measured synchronization accuracy.

## Prerequisites

- Existing 1.2.3.2.1 patch already installed; Windows OrbbecSDK v2.10.6 `lib/OrbbecSDKConfig.cmake` available.
- Python **3.12 x64** `.venv` already configured; do not use MSYS2 `python`.
- Close OrbbecViewer for the `--once` hardware test.

From `E:\1_BigProject\scantopath` in PowerShell:

```powershell
$pyExe = (Resolve-Path '.\scantopath-software\.venv\Scripts\python.exe').Path
& $pyExe -m pip install 'pybind11>=2.13,<4'
$pybindDir = & $pyExe -m pybind11 --cmakedir

cmake -S .\scantopath-software\cpp -B .\scantopath-software\build-orbbec `
  -DBUILD_TESTING=ON `
  -DSCANTOPATH_BUILD_ORBBEC_PROBE=ON `
  -DSCANTOPATH_BUILD_ORBBEC_SOURCE=ON `
  -DSCANTOPATH_BUILD_PYTHON_BINDINGS=ON `
  '-DOrbbecSDK_DIR=E:/1_BigProject/scantopath/_sdk/OrbbecSDK_v2.10.6/lib' `
  "-DPython3_EXECUTABLE=$pyExe" `
  "-Dpybind11_DIR=$pybindDir"

cmake --build .\scantopath-software\build-orbbec --config Release
ctest --test-dir .\scantopath-software\build-orbbec -C Release --output-on-failure

# Python 3.8+ uses secure DLL search for .pyd extensions; PATH alone is insufficient.
$env:SCANTOPATH_ORBBEC_SDK_BIN = 'E:\1_BigProject\scantopath\_sdk\OrbbecSDK_v2.10.6\bin'
& $pyExe -m scantopath.acquisition.native --self-test
# Only with Gemini 2 USB3 connected, and OrbbecViewer CLOSED:
& $pyExe -m scantopath.acquisition.native --once
& $pyExe -m pytest -q
```

## Expected diagnostic output

Offline self-test: `native.import=true`, `native.memory_ownership=true`, `native.hardware_access=false`.

Hardware: `capture.valid=true`, `buffer.copy_survived_close=true`, `depth.numpy.owns_data=True`, `capture.saved=false`.

CMake writes `_scantopath_native*.pyd` into `src/scantopath/` (editable-source location); do not commit binaries into Git. No pip build/installer is modified.

## Contract and limitations

- Color remains **MJPG compressed**, NOT unpacked RGB888.
- Depth remains Y16 raw (1280 × 800), with `.depth_u16()` allocating an independent NumPy array.
- Pixel depth in meters = value × `depth_scale_m_per_unit`; pixel `0` indicates invalid/no depth.
- Matrix rotation is row-major; SDK D2C translation is in **millimeters**, not meters.
- Device timestamps are compared only if both use the same device clock domain; a single delta is NOT sync validation.
- Acquisition class is not thread-safe; this CLI uses it sequentially on one thread. Qt worker integration is deferred.
- One camera, expected profiles (Gemini 2 non-L/XL; RGB MJPG 1920×1080@30; Depth Y16 1280×800@30), alignment OFF.
- `BUILD_TESTING=ON` exports `_test_copy_y16` diagnostic method with synthetic data; never treat that data as measured.

## Common errors

- `ModuleNotFoundError: pybind11` → run pip install using `.venv\Scripts\python.exe`.
- `Could not find pybind11Config.cmake` → supply `-Dpybind11_DIR` from the same interpreter (`python -m pybind11 --cmakedir`).
- `Python3 version/ABI mismatch` → wipe ONLY build-orbbec cache or choose new build directory; verify `Python3_EXECUTABLE` is Python 3.12 x64.
- `DLL load failed` → set `SCANTOPATH_ORBBEC_SDK_BIN` to the folder containing `OrbbecSDK.dll`; use `os.add_dll_directory` via wrapper (not just PATH).
- `Device busy` → close OrbbecViewer first.
- `Depth not Y16` → verify SDK profile selection; do not reinterpret other formats as `uint16`.

## Acceptance

1. CMake + MSVC Release build succeeds, CTest regressions pass.
2. Python `--self-test` imports `.pyd`, checks no-camera use, and verifies NumPy owns copied depth after native buffer release.
3. Python `--once` reads a real Gemini 2 pair and validates format/scale/calibration and ownership after close.
4. Python original 5 tests plus added offline tests pass.

**Never claim acceptance before the user's Windows output confirms it.**

## Kết quả người dùng xác nhận và tương thích MSVC (18/10/2026)

Trên Windows 11/MSVC 19.51 (VS 2026), module `.pyd` có thể `ctypes.WinDLL()` thành công nhưng Python `import` gặp Access Violation `0xC0000005`. **Tắt LTO bằng `NO_EXTRAS` đơn độc không khắc phục lỗi.** Sau khi thêm `_DISABLE_CONSTEXPR_MUTEX_CONSTRUCTOR` cho đúng target pybind11, `--self-test` thành công và trả mã `0`.

Cấu hình hiện hành đã nằm trong `cpp/CMakeLists.txt` và được giữ nguyên trong PRE-01:

```cmake
pybind11_add_module(_scantopath_native MODULE NO_EXTRAS python/orbbec_bindings.cpp)
if(MSVC)
    target_compile_definitions(_scantopath_native PRIVATE _DISABLE_CONSTEXPR_MUTEX_CONSTRUCTOR)
endif()
```

Người dùng đã chạy `--once` với Gemini 2, nhận Color 1920×1080 MJPG + Depth 1280×800 Y16, `depth.numpy.owns_data=True`, `capture.valid=true`, `buffer.copy_survived_close=true`, `capture.saved=false`; `CaptureExitCode=0`. CTest `2/2`, pytest `7/7` trên máy người dùng. Các kết quả này xác nhận **chỉ** native acquisition/binding và regression ở thời điểm đã thử; chưa có lưu RAW, 3D reconstruction, phân tích sai số hay chức năng quỹ đạo cầm tay.

**PRE-01 thay đổi tài liệu, không sửa mã CMake/pybind11.** Kiểm thử hậu áp dụng phải được chạy lại trên Windows trước khi khóa mốc. Khi cập nhật MSVC/STL/pybind11, cần kiểm thử lại workaround, không gỡ bỏ chỉ dựa trên build thành công.
