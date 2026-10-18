# Work sequence — map to previously agreed 20-session ScanToPath roadmap

Do not replace the user's accepted implementation roadmap. The following is a **dependency map**, not a replacement roadmap.

| Session | Agreed functional increment | Engineering acceptance gate | Status of this reference package |
|---|---|---|---|
| 01 | Project skeleton | MSVC CMake smoke + Python import + Qt app launch on target PC | Native smoke and Python smoke tested in sandbox; Qt/MSVC not tested |
| 02 | Project / Specimen | IDs, lifecycle and storage project schema | IDs in capture schema only, persistent project service TODO |
| 03 | ScanSession / Capture | schema & provenance, no guessed pose | `CaptureMetadata` + `CaptureSource` contracts implemented |
| 04 | Raw storage | raw RGB/depth + metadata reopen, incomplete captures ignored | implemented for fixture data |
| 05 | ProcessingRun / traceability | input IDs, algorithms, parameters, outputs | schema implemented; DB integration TODO |
| 06 | 3D core | mm/m discipline, projection & transforms verified | C++20 single-point math smoke implemented |
| 07 | VTK viewer | never block GUI on processing | UI placeholder only |
| 08 | coordinate frames / measurements | calibrated frame chain and fiducial measurement | frame convention documented; calibration TODO |
| 09 | RGB-D to cloud | device depth calibration and hardware replay parity | TODO |
| 10 | point cloud processing | voxel/outlier/ROI validation | TODO |
| 11 | multi-view registration/fusion | encoder pose + ICP + pose-drift error bounds | TODO |
| 12 | calibration/metric validation | gauge objects + scale/dimension error | TODO |
| 13 | quality/trust | measured/weak/inferred/missing provenance | contract foundation; algorithms TODO |
| 14 | feature extraction | plane/cylinder/hole/axis fit uncertainty | TODO |
| 15 | relations | geometry graph + uncertainty propagation | TODO |
| 16 | digital replica | as-is vs nominal candidate | TODO |
| 17 | technical export | standards + units + provenance | TODO |
| 18 | MVP-0 | offline 3D data → trusted geometry → basic replica | TODO |
| 19 | MVP-1 | integrated Gemini 2 / controllable stage acquisition | TODO |
| 20+ | advanced research | task-specific NBV, uncertainty-driven rescan | TODO |

## Immediate next implementation on user's Windows machine

1. Check existing ScanToPath repository HEAD/branch, tests and session implementation; merge this package at feature/module level only when compatible.
2. Build C++ smoke via MSVC x64 and run PySide6 shell. Preserve existing repo design rather than overwriting.
3. Install Orbbec SDK v2 matching Gemini 2 firmware; run official Color/Depth/PointCloud samples and save known raw data.
4. Replace `OrbbecSDKv2Source` stub with a native adapter that emits exactly the validated `FrameBundle`, including depth units, registration, device timestamps and firmware metadata.
5. Check known target (flat reference, cylinder) repeatability and dimensional bias **before** registration/fusion.
6. Reintroduce future Pi/ESP32 interface via adapter; don't bring real-time motion into desktop UI thread.

Hard no-go: no real hardware results claimed by this sandbox; no precision targets invented without specimen size, distance, ground truth and camera mode; no AI-generated mesh accepted as dimensional measurement.
