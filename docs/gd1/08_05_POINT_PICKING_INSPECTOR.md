# ScanToPath — GĐ1 / 08.05 Point Picking & Inspector

**Baseline:** `feat/gd1-desktop-ui @ ccd13abbe513c19d0c230fb2637f972c45fd3007` (08.04 accepted by operator). **Status:** implementation candidate; not accepted until Windows verify/HMI and push. **Architecture:** Modular Monolith + MVC per feature + SOLID. No installation of VTK/PySide6 by this package.

## Vertical slice, responsibility and contracts

- `modules/viewer3d/application/picking.py`: immutable, Qt/VTK-free `PickResult` with exact JSON field validation; `image_click_uv()` maps a centered, KeepAspectRatio Qt preview to normalized VTK pixel coordinates (VTK origin bottom-left). A click outside letterboxing is not a pick. No measure or calibration assertion.
- `modules/viewer3d/infrastructure/pick_point.py`: *only* child-process VTK reader, renderer and `vtkPointPicker`. Render reconstruction uses the accepted 1000×620 viewport, same `CameraView` and `configure_scene()` as 08.04. Restrict picker to the point actor; XYZ reference axes cannot be selected. A point is a hit only within 12 source PNG pixels of the projected vertex; background clicks return `hit=false` with all data cleared. Point ID corresponds to the VTK reader order; 0-based indexing. Read-only PLY and SHA-256 check before and after selection; no SQLite, RAW, camera, or file mutation.
- `modules/viewer3d/presentation/view.py`: Qt View draws a small selection ring at the *projected* pixel of the chosen point, displays Point ID, raw XYZ and optional RGB in a **viewer-local Inspector điểm**; no interference with Project Workspace's global Property Inspector. A single currently loaded point-cloud layer can be hidden/shown locally; no fake multi-layer stack. Left **click** selects, left **drag** orbits, right drag pans, wheel zooms (preserve 08.04). Reset/navigation clears selected point only when camera update succeeds. No VTK import in GUI.
- `modules/viewer3d/presentation/controller.py`: `QProcess` supervisor for isolated `picking`, in addition to existing fixture/PLY/navigation jobs. Exact result contract, size limit, source match, point-count bounds and controlled failure handling. The image and camera remain intact after a missing point, timeout or child crash; old selection is removed. Each pick runs after one click, not at 60 FPS. Existing 60-second max child deadline applies.

## State rules

- **No active image / during loading / hidden layer:** selection disabled.
- **Valid hit:** Point ID / `(X,Y,Z)` raw file/fixture coordinates / RGB if VTK returns supported RGB. UI retains `units=unknown`, `coordinate_frame=unknown`; no dimensional accuracy claim.
- **Background click:** clear selection marker + Inspector values, preserve scene and camera.
- **New PLY or accepted navigation:** clear selection (stale screen projection forbidden). An unsuccessful camera change leaves camera/PNG intact.
- **Changed source SHA / untrusted JSON / child crash / timeout:** short user-visible error, no stale selection, Qt survives. Native logs stay in terminal.
- **Layer toggle:** only hides/shows the *single current preview layer*; no stored image/PLY mutation. When hidden, picking disabled and selection cleared. Rendering of axes together with point cloud remains a future multipass/layer capability, not claimed here.

## Native integration caveats

- Point picking **rebuilds the scene in a disposable child** and is therefore not as fast as an embedded interactive viewport. The default preview must have been successfully rendered with the same camera; a PLY changed on disk is rejected. VTK's picked source vertex number is 0-based, not a stable UUID across processed/filtered versions of the cloud.
- Dataset bounds/point count stay from 08.03. Do not convert unknown units to meters/millimeters, do not pretend `Point ID` is a metric feature.
- Point picking and layer toggle are not ROI, crop, filtering, point modification, registration, measurement or surface reconstruction.
- Do not embed `QVTKRenderWindowInteractor` in MainWindow: 08.02 Windows crash is a hard regression constraint.

## Mandatory verification and HMI

1. Guard check: HEAD exact, branch correct, clean worktree, 7-file scope SHA and no external edits. No Git reset, silent rebaseline or auto-merge main.
2. Headless native tests: five known fixture Point IDs and coordinate triples, RGB PLY point, empty background, malformed result rejection, changed fingerprint blocked, child CLI protocol and source non-mutation.
3. Windows Qt offscreen: View/Controller signal routing, initial disabled state, success + missing point + native failure, toggling one layer, preservation of Project Workspace Inspector; 08.02–08.04 tests remain valid. NO claims from offscreen tests about Windows OpenGL.
4. Full pytest including Qt with only two previously documented Windows symlink-privilege skips, AST architecture guard, 07.12 quality gate, Qt acceptance parser, compileall, CTest 2/2, no-camera native self-test.
5. Real Windows HMI, with VTK and PySide6 **already installed**: load 08.02 fixture and click all five known points; click dark background (Inspector clears); orbit and select point again; import ASCII RGB 4-point PLY and binary 3-point PLY, verify 0-based IDs and XYZ; toggle `Hiện lớp điểm`; switch Projects/Inspect; retry malformed PLY TC05; close/reopen multiple times; no crash, hang, hidden stale selection or false metric units. Make screenshots of hit, miss, RGB, hidden-layer, and post-orbit scenarios.
6. Publish only with current machine receipt and user-confirmed HMI; commit exact scoped files to `feat/gd1-desktop-ui`, do not merge `main`. GĐ1/08.06 remains pending.
