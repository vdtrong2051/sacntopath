# GĐ1 — 08.04 Camera & Navigation (isolation-preserving implementation)

**Baseline:** `feat/gd1-desktop-ui` at `ef6a8517be3e839c7fb6c7788ac9a2d1b676f43e`, after accepted 08.03 TC-05 repair. **No VTK installation, RAW/SQLite schema, camera, C++ or previous-session modification.**

## User-visible scope

- `Inspect 3D` reuses the approved 08.02/08.03 static VTK PNG-based preview, **not** an embedded `QVTKRenderWindowInteractor` (the latter crashed the Qt application on the operator's Windows machine).
- **Orbit:** left-drag completed gesture or left/right/up/down buttons. **Pan:** right-drag completed gesture. **Zoom:** mouse wheel or +/− buttons. **Reset:** restores default camera framing while preserving the axes toggle. **XYZ:** optional reference axes displayed near the minimum XYZ dataset bounds.
- Each completed action submits **one QProcess offscreen render job**. While a job is in progress, all viewer actions are disabled. The GUI accepts the new camera state **only after** a valid PNG is returned with the success marker. Timeout (60s), malformed/corrupt PNG, child crash or altered PLY leave the last accepted camera state intact and report an error in UI; only child is killed.
- Commands and camera view are immutable typed Python DTOs under `viewer3d/application/navigation.py`, independent of Qt, VTK, SQLite or point-cloud pose. The child-only `camera_scene.py` applies an orbit, pan/zoom and optional reference axes without changing input XYZ.
- `render_navigation.py` is a distinct native subprocess entrypoint, rendering either the 08.02 synthetic fixture or a previously imported 08.03 PLY. It checks SHA-256 before and after the PLY render to reject an altered local file. Existing `render_ply.py` and `render_preview.py` default invocation remains backward compatible with optional `view_state=None`.

## Important limits — not a false claim of smooth interaction

- VTK is **process-isolated frame-by-frame**, not a persistent embedded 3D viewport. Mouse drag updates the image **on release**, wheel/buttons after each accepted input. It does not claim fluid real-time 60 FPS orbit. Latency is hardware- and point-count-dependent, measured as part of 08.06.
- UI axes are **display orientation references**, anchored at minimum XYZ data bounds. They are not a calibrated sensor/world frame, stage pose, surface normal or measured geometry. PLY units and frame stay `unknown`.
- No point picking, ROI, crop, geometric filtering, RGB-D projection, calibration, metric validation, database mutation or PLY export (other sessions). No direct Qt `vtkmodules` import.

## Test/acceptance gates

1. Exact Git branch, HEAD, original Git blob hashes and clean working tree before apply. Patch touches only 4 existing Viewer files + 3 new navigation modules + 2 tests + this document. No manual edits to repair guard/manifest. If HEAD differs, regenerate/rebase patch; **never reset/checkout**.
2. Verify Python package dependencies already installed; no pip install. Focused `08.04` DTO/native renderer/Qt tests (no missing/skip), `08.03`+`08.02` regression and complete Python/Qt suite; architecture/quality gates, CTest 2/2, native self-test hardware-free; hash-bound acceptance receipt.
3. Windows HMI: open fixture → orbit left/right → elevation → pan via right drag → wheel/+/− → reset → toggle XYZ; open the approved ASCII RGB PLY and binary PLY and repeat. Check actual PNG changes, point counts and bounds unchanged, source PLY bytes unchanged, switching tabs works, close/reopen stable. Invalid PLY TC-05 still shows short RED error without stale geometry or traceback.
4. Child failure test: invalid/removed/changed PLY or forced subprocess error does **not** terminate desktop; GUI visibly reports the rejected action and remains interactive. Verify no freeze during repeated jobs.
5. Only after operator HMI and automatic receipt both PASS may publish precisely the scoped files to `feat/gd1-desktop-ui`. Never auto-merge `main`; **do not start 08.05** until 08.04 accepted.

## Regression protections against prior 08.02/08.03 mistakes

- No inline PowerShell `python -c` with nested quoting; Python scripts are files.
- No pytest global `sys.modules` assertions for lazy Qt imports. Qt tests are offscreen contracts, not GPU compatibility proof. Native renders are performed in **real subprocesses**.
- Test fixtures have fixed XYZ, so camera updates can be tested by **comparing output PNG hashes**, not only by whether a status label claims success.
- No stale camera commit when VTK subprocess exits abnormally. Release guard requires evidence and exact scoped Git hashes; no silent bypass of errors.
