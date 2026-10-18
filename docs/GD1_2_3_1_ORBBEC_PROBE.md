# GĐ1.2.3.1 — Gemini 2 SDK C++ probe (Windows x64)

**Status:** Source prepared; SDK-dependent build and camera execution MUST be validated on user's Windows/Gemini 2. Offline v0.1.0 is not changed.

## Baseline recorded from user's OrbbecViewer

- Gemini 2 (non-XL), firmware **1.4.98**, OrbbecSDK **2.10.6**, USB **3.0**.
- Color **1920×1080 @30 FPS MJPG**; RAW Depth **1280×800 @30 FPS Y16**.
- For this probe, **alignment disabled**. It must not infer a transform from aligned data.
- Raw INI reference: Depth K fx=fy=610.908264, cx=640.787842, cy=397.602814, width=1280, height=800. Depth→Color translation (mm) about (-13.787516,-0.104090,-1.982521), with rotation close to identity. Compare reported SDK values, DO NOT hardcode into runtime.
- Distortion parameters and calibration model are **not yet used** to undistort frames. Geometry correctness is not validated by this probe.

## 1. SDK developer package

OrbbecViewer `.exe` already runs on this machine, but **the CMake project additionally needs OrbbecSDK's development `include`, `lib` and CMake config**. If these are missing from the installer directory, download the matching **Windows x64 ZIP SDK developer package (`OrbbecSDK_v2.10.6_202609291804_575347c_win_x64.zip`)** from the official release, extract e.g. `E:\SDKs\OrbbecSDK_v2.10.6_win64`. Do not assume the `.exe` creates a development package.

Official release: https://github.com/orbbec/OrbbecSDK_v2/releases/tag/v2.10.6

Locate `OrbbecSDKConfig.cmake` or `orbbecsdk-config.cmake` in the extracted SDK. Supply the **directory containing that config file** to CMake's `OrbbecSDK_DIR`. The official imported target should be `ob::OrbbecSDK`. Do not use old OrbbecSDK v1 libraries.

PowerShell to locate a CMake config in the extracted SDK (modify path):

```powershell
Get-ChildItem 'E:\SDKs\OrbbecSDK_v2.10.6_win64' -Recurse -File -Include '*OrbbecSDK*Config.cmake','orbbecsdk-config.cmake' | Select-Object -ExpandProperty FullName
```

## 2. Build without touching the accepted offline build

From `E:\1_BigProject\scantopath\scantopath-software` in PowerShell (after applying the patch):

```powershell
cmake -S cpp -B build-orbbec -DSCANTOPATH_BUILD_ORBBEC_PROBE=ON -DBUILD_TESTING=ON -DOrbbecSDK_DIR="<FOLDER_CONTAINING_OrbbecSDKConfig.cmake>"
cmake --build build-orbbec --config Release
ctest --test-dir build-orbbec -C Release --output-on-failure
```

Replace the placeholder above with the **actual folder path**. CMake config should find and link the SDK (MSVC x64). The optional probe is **OFF** by default, so earlier `cmake -S cpp -B build` stays valid.

## 3. Run probe

**Completely exit OrbbecViewer** first: it can hold the camera/device resources. Keep Gemini 2 connected directly to USB 3.0.

`OrbbecSDK.dll` and SDK `extensions` must be discoverable by the process. Prefer vendor SDK package's `bin` directory / documented deployment layout. If DLL is not found, use a temporary PATH in the *same terminal*, pointing to the directory that actually contains `OrbbecSDK.dll`, **not a guessed location**:

```powershell
$env:PATH = "<FOLDER_CONTAINING_OrbbecSDK.dll>;" + $env:PATH
```

The Orbbec SDK may require its extensions to be deployed beside the executable; follow the vendor package layout if an extension-load error appears.

```powershell
.\build-orbbec\Release\scantopath_orbbec_probe.exe --info
.\build-orbbec\Release\scantopath_orbbec_probe.exe --capture 2>&1 | Tee-Object .\gemini2-probe.txt
```

Send `gemini2-probe.txt` and any build error. Device serial is intentionally omitted from probe output, but SDK logs may still include it; inspect before public sharing.

## 4. Gate

- `--info`: Gemini 2 detected and compatible profiles listed.
- `--capture`: one **unregistered** RGB/Depth frameset received, exactly 1920x1080 MJPG and 1280x800 Y16, positive scale in **meters per unit**, positive timestamps, extrinsic and intrinsic output.
- Compare intrinsics/extrinsics to the RAW `.ini` from Viewer; investigate differences, do not overwrite either record.
- `FrameSync` enabled does not prove timestamps are correct; Windows UVC metadata registration must be checked separately: https://github.com/orbbec/OrbbecSDK_v2/blob/main/scripts/env_setup/obsensor_metadata_win10.md
- Successful SDK probe is **NOT** approval of metric precision, SDK-to-Python binding, raw storage, D2C alignment, or UI integration.

SDK source API used: https://github.com/orbbec/OrbbecSDK_v2/tree/main/examples/0.basic.enumerate , https://github.com/orbbec/OrbbecSDK_v2/tree/main/examples/3.advanced.sync_align , https://github.com/orbbec/OrbbecSDK_v2/blob/main/include/libobsensor/hpp/Frame.hpp
