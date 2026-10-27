# R5.2 - Tich hop khung nhin 3D lien tuc trong ScanToPath

**Baseline:** `feat/gd1-desktop-ui@1019127` (R5.1 accepted). **Status:** Windows native verification pending; no GĐ1 final freeze.

## Pham vi

- Qt `LiveViewer3DController` extends the existing Viewer3DController, preserving all legacy objectNames and the explicit PNG safe-preview option.
- The composition root injects `CoalescingRenderSession` (R4.3/R5.1); presentation NEVER imports VTK or feature infrastructure.
- A lazy 640x480 RGB24 frame stream is copied+ACKed in the worker and copied into a Qt-owned QImage, vertically mirrored for correct VTK origin.
- `mouseMoveEvent` dispatches incremental orbit/pan during dragging, right/middle drag pans, scroll zooms; camera commands are coalesced off the UI thread. No PLY reread per gesture.
- Scene switches invalidate prior scene/frame and selected point; each switch retires the previous render process asynchronously, then launches one new session. Monotonic scene, frame and input revision checks reject stale frames.
- Unexpected host exit raises a Vietnamese user error with `Thử lại`. Operator can choose `Xem trước an toàn` (legacy PNG, PLY-only).
- Qt window close is deferred until native child cleanup completes. No synchronous thread join/VTK render/file hash in GUI event handlers.
- Open PLY points, PLY polygon mesh and OBJ through verified R5.1 source scene contracts. No geometry calibration or SQLite/RAW edits.

## Scope exclusions and honest status

- Native point/face picking, Inspector bridge and actual layer visibility remain **R5.3**. The existing layer button is disabled in live mode, not faked.
- Display-present/pointer-to-photon timing, GPU VRAM, sustained physical-screen FPS and driver-wide stability remain **NOT_MEASURED**; R4.4 render completion Hz is not UI FPS.
- The automated controlled host kill test **is not a real native C++ crash**. Close while genuinely blocked in native VTK must be proven using a repeatable Windows fault-injection/busy trace before production acceptance. A successful racing-close alone cannot close AR-03.
- 640x480 frame transport scales within the QLabel; display pixel mapping and full 100/125/150% DPI checks remain R6 hard gates.
- The explicit PNG fallback does not support OBJ or mesh. It remains solely a compatibility path.

## Windows gate

1. `apply.ps1`: branch+HEAD, clean tree, original `main_window.py` Git blob pinned, all new payload hashes validated.
2. `verify.ps1`: focused tests without unapproved skips, 07.11 architecture, 07.12 quality, full pytest, CTest 2/2, Windows real-Qt native probe.
3. HMI operator: confirm drag updates **before** mouse release; 20+ second orbit/pan/zoom; PLY and OBJ; source switch; 100k and 1M scenes; real Windows graphics and no orphan PID. Document driver/OS.
4. Busy-close and GPU/HMI residual risks are explicitly recorded. **R5.2 code can be committed but final production promotion remains blocked** until R6 verifies AR-03 and DPI.
5. Preserve `_setup` failure attempts for R7 journal; no rewriting a failed run to PASS.

## Test hooks

- `viewer3dPreview` preserved; `viewer3dOpenPlyButton` preserved while label becomes `Mở mô hình…`.
- New `viewer3dSafePreviewButton`, `viewer3dRetryButton` are stable.
- `render_initialized` returns live readiness, legacy mode preserves old contract.
- Do not enable picking or actor layers until R5.3 implements their actual behavior.
