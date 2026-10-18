# Work sequence — map to previously agreed 20-session ScanToPath roadmap

Do not replace the user's accepted implementation roadmap. The following is a **dependency map**, not a replacement roadmap. Session numbering and agreed functional increments (01–20+) remain unchanged.

## PRE-01 snapshot — 2026-10-18

**Two independent axes must not be confused:** (A) functional roadmap GĐ0 = Software Skeleton (sessions 01–05), GĐ1 = 3D Core (06–08), GĐ2 = Scan Pipeline (09–11), etc.; and (B) supplementary *Gemini 2 native acquisition* work, previously labeled `GĐ1.2.3.1` / `GĐ1.2.3.2.x`. Those historic labels remain in document filenames for traceability **but do not mean that functional GĐ1 is complete**.

**Active hardware model:** handheld Gemini 2, no actuator/turntable/encoder/Pi/ESP32 in the current build. Planned/guided handheld trajectory and live object recognition/tracking overlay are **required for a future scanning workflow**, but neither is implemented. Camera pose changes with time and is currently unknown; a nominal trajectory is not observed camera pose.

**Validated on user's Windows PC before PRE-01:** Gemini 2 native C++/pybind11 one-frame read, owned RAW buffers, pybind11 self-test (`0`), CTest `2/2`, pytest `7/7`. **Not validated/implemented:** real RAW storage, 3D Viewer, 3D reconstruction, Project CRUD, meaningful ProcessingRun persistence. See `docs/PRE_01_BASELINE.md`.

**PRE-01 → PRE-06 (preparatory overlay, not new functional sessions):**

| Gate | Focus | Limit |
|---|---|---|
| PRE-01 | Repository cleanup, documentation, test evidence | **Docs/config only**; user verifies Windows regressions |
| PRE-02 | Raw Capture v2 contract | MJPG/Y16 independent grids, dual calibration, timestamps, unknown pose; preserve v1 |
| PRE-03 | Raw storage/read-back, manifest/checksum, v1 compatibility | No reconstruction or live viewer |
| PRE-04 | Gemini 2 pybind11 → real RAW storage adapter + hardware roundtrip | One-shot capture; no UI/controller |
| PRE-05 | Finish GĐ0 Project/Specimen/Session/ProcessingRun/logging metadata lifecycle | No 3D algorithms |
| PRE-06 | Integrated regression and acceptance; lock GĐ0 | Only afterward enter functional GĐ1 |


| Session | Agreed functional increment | Engineering acceptance gate | Status as of PRE-01 |
|---|---|---|---|
| 01 | Project skeleton | MSVC CMake smoke + Python import + Qt app launch on target PC | Windows C++/Python smoke and PySide6 shell user-verified; broader Project lifecycle pending |
| 02 | Project / Specimen | IDs, lifecycle and storage project schema | IDs in Capture metadata only; persistent project/specimen CRUD TODO (PRE-05) |
| 03 | ScanSession / Capture | schema & provenance, no guessed pose | Synthetic capture schema/source implemented; RAW v2 TODO (PRE-02) |
| 04 | Raw storage | raw RGB/depth + metadata reopen, incomplete captures ignored | Synthetic v1 local storage/reopen tested; real RAW storage TODO (PRE-03/04) |
| 05 | ProcessingRun / traceability | input IDs, algorithms, parameters, outputs | ProcessingRun Pydantic schema only; persistent service TODO (PRE-05) |
| 06 | 3D core | mm/m discipline, projection & transforms verified | Single-point C++ geometry math smoke only; full cloud core TODO |
| 07 | VTK viewer | never block GUI on processing | PySide6 tab placeholder only; VTK viewer TODO |
| 08 | coordinate frames / measurements | calibrated frame chain and fiducial measurement | Basic frame convention documented; moving-camera pose/measurements TODO |
| 09 | RGB-D to cloud | device depth calibration and hardware replay parity | Native Gemini 2 RGB-D acquisition works; depth-to-cloud processing TODO |
| 10 | point cloud processing | voxel/outlier/ROI validation | TODO |
| 11 | multi-view registration/fusion | encoder pose + ICP + pose-drift error bounds | TODO |
| 12 | calibration/metric validation | gauge objects + scale/dimension error | TODO |
| 13 | quality/trust | measured/weak/inferred/missing provenance | Provenance schema foundation only; trust algorithms TODO |
| 14 | feature extraction | plane/cylinder/hole/axis fit uncertainty | TODO |
| 15 | relations | geometry graph + uncertainty propagation | TODO |
| 16 | digital replica | as-is vs nominal candidate | TODO |
| 17 | technical export | standards + units + provenance | TODO |
| 18 | MVP-0 | offline 3D data → trusted geometry → basic replica | TODO |
| 19 | MVP-1 | integrated Gemini 2 / controllable stage acquisition | Gemini 2 desktop RAW native capture verified; no stage/actuator or full MVP-1 |
| 20+ | advanced research | task-specific NBV, uncertainty-driven rescan | TODO |

## Next executable work

**Historical gates mentioning encoder/stage (sessions 11 and 19) are not prerequisites for the current handheld-only implementation.** Keep those original 20-session rows for traceability; any future actuator scope needs a separately approved roadmap change. Current handheld registration needs an independently estimated actual camera pose, not a fictional encoder.

PRE-01 is the only currently authorized change: repository/docs normalization with **no C++/Python source edits**. Once the Windows user confirms post-apply regression, commit/merge and request separate approval to start PRE-02 (RAW Capture Contract v2). Future object perception, handheld trajectory planning, actual pose estimation and multi-view processing are **not** part of PRE-01–06 by default; plan their functional sessions separately without modifying the agreed 20-session sequence.

**Hard no-go:** do not label RAW unaligned 1920×1080 MJPG as RGB registered to 1280×800 Y16; do not imply real Capture Storage exists; do not mark `measured=true` as proven accuracy; do not invent stage encoders or fixed-camera transforms in handheld mode.
