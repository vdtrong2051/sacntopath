# GĐ1 / 08.01 — VTK + Qt Architecture Audit & Feature Boundary

**Status:** implementation gate; no production VTK integration in 08.01.
**Baseline:** `feat/gd1-desktop-ui` @ `9784012c34fa5527f86f36beb59171c056018fa6` (07.12 WIP repair committed).
**Source of truth:** `docs/ROADMAP.md` and `docs/architecture/07_10_MODULAR_MONOLITH_TARGET.md`; UI-first baseline, not full 3D reconstruction.

## 1. Verified inventory and constraints

- Existing Qt entry point `scantopath.ui.main.main`; `ScanToPathMainWindow` owns four existing workspace pages, including `WorkspaceId.INSPECT3D` placeholder in `ui/workspaces/pages.py`.
- `modules/project_workspace/{application,domain,infrastructure,presentation}` is implemented. Service/query/command/inspection facades and split metadata/numbered storage already accepted in 07.11–07.12.
- Shared `application.tasks.TaskManager` and `ui.tasks.QtTaskController` already exist; **do not make a second job manager**. Current Project load/write Qt QThreads are legacy-compatible and should not be moved in 08.01.
- `src/scantopath/metadata`, `storage`, `acquisition` are established shared infrastructure, not candidates for moving into a new feature. RAW/SQLite/Gemini2 and `cpp/` are frozen.
- `pyproject.toml` does not yet depend on VTK; no production `viewer3d` feature exists before 08.02.
- Windows 07.12 user acceptance: 393 passed, 2 documented symlink skips; CTest 2/2; hardware-free native self-test; manual HMI accepted.

### Recorded architecture debt (not repaired in 08.01)

1. `presentation/workflows/base.py` uses dynamic attribute forwarding to the shared ProjectWorkspaceController; reduces dependency visibility. Do not copy this pattern to Viewer.
2. `ui/projects/{controller,write_controller,inspection_controller}.py` still owns workers referenced by Project feature. A compatibility migration needs independent patch and tests, not folder moves here.
3. `ui/shell/main_window.py` has many compatibility delegates, but project operations are already delegated; Viewer must add **composition wiring only**, no PLY/VTK manipulation here.
4. Project service's documented lazy `application/service.py → infrastructure/sqlite_backend.py` compatibility exception remains exact and unchanged.
5. Static AST gates cannot prove SOLID, runtime dynamic imports, render-thread correctness or memory safety.

## 2. Architecture decision for 08.02–08.06

**Modular Monolith + feature-local MVC + SOLID:**

```text
ui/shell/main_window.py             composition root (minimal wiring)
        │
modules/viewer3d/
  presentation/                     Qt View + MVC Controller (signals, navigation, Inspector)
        │  typed commands / immutable DTOs
  application/                      Viewer use cases + narrow ports (no Qt/VTK)
        │
  domain/                           Pure coordinate / provenance models when actually needed
        ▲
  infrastructure/                   PLY reader + VTK renderer (no SQLite/camera)
```

Create only needed files on demand; **do not generate empty MVC folders for appearance**. A Qt widget that hosts `QVTKRenderWindowInteractor` belongs to Presentation. Pure VTK mapper/actors may live in infrastructure behind a rendering port, but must be operated from the Qt GUI thread. Qt host widget and rendering object must have a single clear owner/lifecycle.

**Dependency rules added in 08.01:** A feature may access another feature's *public typed contracts only* (`application.ports`, `.models`, `.contracts`, `domain.models`). Direct imports of a different feature's Presentation, Infrastructure or use-case implementation are forbidden. Feature Presentation may not import its *own* infrastructure implementation either: construction/injection belongs at a composition seam. Core Application/Domain must not import `vtkmodules`/`vtk`. The existing one-file Project bootstrap exception stays narrow.

**Limits:** A static import check does not prevent runtime imports through `importlib`, getattr, reflection or arbitrary plugin loading. Integration tests and code review still required.

## 3. Viewer contract design (design only, not Python implementation)

### Import/open a local PLY

- Command: `OpenLocalPly(path)` via Controller → Application service/loader port.
- Worker: validate file path and extension/format, read/parse vertices asynchronously, reject invalid/oversized data by an explicit policy in 08.03, check cancellation between stages. **No VTK Render() or QWidget operations inside worker.**
- Immutable transfer: `PointCloudSnapshot(source_path/identity, point_count, xyz_float, optional_rgb, bounds, coordinate_frame, units, provenance, status)`; large arrays should have explicit ownership and read-only semantics; use typed DTO metadata and an independently owned buffer reference rather than copying millions of Python tuples.
- Unit: PLY coordinates have **unknown unit by default**, unless accompanied by explicit trusted metadata. `point_count`, bounds, raw coordinate values are not metric validation.
- Statuses: empty, loading, loaded, unsupported, invalid, cancelled, failed. Distinguish fixture from measured and never imply calibrated physical dimensions.
- Ownership: file reading has no project DB writes, session creation or RAW modification; imported PLY is an external in-memory view source until a future separate artifact workflow.

### Render/picking

- `QVTKRenderWindowInteractor` sits in the existing `Inspect 3D` page, created only when that workspace/viewer is needed. `mainwindow` does not own VTK actors or point arrays.
- GUI thread owns render window, renderer, actor lifecycle, picking signals and camera interaction.
- Initial fixture (08.02): 5 deterministic points, axes and coordinates verified independently from rendering. 08.03: real PLY reader; 08.04: orbit/pan/zoom/reset; 08.05: Point ID and XYZ picking, selected point metadata.
- No transform to world frame. Preserve original PLY coordinate frame; no camera pose fabrication. ROI/cropping and geometry/metric computations belong to sessions 11+ and 14+.
- Cleanup: repeated enter/exit, file reload and app shutdown must remove actor references/finalize safely; Qt offscreen smoke does **not** replace Windows real-GPU interactive test.

### Compatibility target and decision gate

- Windows host: Python 3.12, PySide6 Qt Widgets (last user-installed PySide6 was 6.12.0), supported VTK Python wheel in isolated target; VTK selected Qt implementation must be `PySide6`.
- `scripts/probe_gd1_08_01_vtk_qt.py --mode import`: mandatory import/API/backend check.
- `--mode window`: opens a *fixture-only* 5-point VTK window for 8 seconds with real Qt event loop, renderer and OpenGL. Operator must visually confirm that the points appear, drag/scroll interaction works and close does not crash. A successful timer callback is not itself proof that the user saw the rendering.
- Probe `install-probe.ps1` uses project `.venv`'s Python and installs **only** VTK into this `_setup` package's `_probe_deps` via pip `--no-deps --target`; no changes to repository's `pyproject.toml` or main environment packages. The probe is temporary, not production integration.
- API references: https://docs.vtk.org/en/v9.6.1/api/python/vtkmodules/vtkmodules.qt.QVTKRenderWindowInteractor.html and https://github.com/Kitware/VTK/blob/master/Wrapping/Python/vtkmodules/qt/__init__.py.
- Production VTK version/dependency selection must happen in 08.02 based on **actual Windows probe results**, not assumption that Linux imports guarantee Windows/OpenGL compatibility.

## 4. Scope and acceptance of 08.01

**Changed inside repository:** the existing architecture import scanner; one focused tests file; one isolated VTK probe script; this design/audit document.
**NOT changed:** `src/scantopath/**`, `cpp/**`, `pyproject.toml`, `ui/main.py`, `ui/shell/main_window.py`, RAW, SQLite, device access or roadmap.

Mandatory gates: branch + exact baseline HEAD, clean worktree, checksum-pinned payload; new negative/positive feature-boundary tests; original boundary and quality gates; full Python/Qt suite with JUnit guard, CTest, `native.hardware_access=false`; VTK/PySide6 import probe and a manually accepted Windows VTK window probe; Git whitespace check and acceptance receipt; commit on feature branch only after user approves manual visual smoke. **08.01 does not declare the complete Viewer implemented.**

### Remaining work / handoff

- **08.02:** create minimal actual Viewer module, plug fixture render into existing workspace, test Qt lifecycle.
- **08.03:** typed PLY loader/validation/cancel, no RAW/SQLite writes.
- **08.04:** 3D navigation and coordinate axes.
- **08.05:** picking/Inspector/layers.
- **08.06:** performance/lifecycle/full UI MVP-A integration acceptance. Then and only then review merge GĐ1 to `main`.
