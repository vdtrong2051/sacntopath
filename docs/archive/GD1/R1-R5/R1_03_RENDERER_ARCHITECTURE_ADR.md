# R1.3 — ADR: Resident interactive VTK renderer, Windows crash isolation and 3D data fidelity

**Decision state:** PROPOSED for R4 proof-of-concept; not production validated. **Reviewed baseline:** `359e0156a6f11154a416c9ea6888c2840d343a0f`. R1 changes neither Qt runtime nor rendering binaries. Historical user environment: Windows 11 / Python 3.12.10 / VTK 9.7.1; do not reinstall these dependencies as part of R1.

## Existing observed behavior

`Viewer3DPage` is a `QLabel` rendering a PNG. Only `mouseReleaseEvent` dispatches a complete `orbit` or `pan`; wheel dispatches zoom. `Viewer3DController` creates a new `QProcess` for each load/navigation/pick, and the renderer restarts VTK, reads geometry, renders then writes PNG. `render_ply.py` reads `vtkPLYReader` and forces data through `vtkVertexGlyphFilter`: mesh faces are ignored. UI supports `.ply` but not `.obj`. Windows benchmark: ~1–3 seconds per operation, 1M-point point cloud tested; later corrected memory measure roughly 190–258MiB per VTK child. HMI A observed 14 child PIDs and no surviving PIDs on normal exit; close while busy (AR-03) NOT TESTED due waiver. Historical 08.02 in-process Qt+VTK crash is a serious A/B gate, not an excuse to keep slow UX forever.

## Core decision

**Prefer Option B as the engineering target, but only promote after R4 Windows PoC.** Option B is **one persistent VTK process per active scene**, with camera and geometry resident, IPC for input/events, and bounded display frame delivery. It retains native-crash isolation while removing per-click process startups. Option A (Qt-in-process QVTKRenderWindowInteractor) remains a separately isolated experiment and can only be selected after disproving/reproducing earlier Windows crash. Option C (independent child 3D window with controlled OS window presentation) is a last-resort compatibility fallback, not automatic HWND reparenting into Qt.

### Candidate A — Qt in-process VTK

- `PySide6` + `QVTKRenderWindowInteractor`, renderer and native OpenGL lifecycle shared with GUI.
- Advantages: input/render directly in one window, low IPC overhead, native picking.
- Risk: prior Windows native crash; may terminate full desktop with SQLite or RAW UI open. Qt GUI-thread affinity, GL context teardown, event loop interactions need native reproduction and driver matrix.
- Gate: standalone PoC only; no embedding into application until Windows 100+ create/close cycles, scene switch and forced renderer error containment strategy. If an unrecoverable native crash remains, reject A regardless of FPS.

### Candidate B — Persistent isolated process (recommended to prototype first)

```text
Qt Shell/QWidget (render target + input capture; NEVER owns vtk objects)
      │   bounded IPC commands/events, monotonic request IDs
      ▼
Native Render Host Process [persist while scene active]
 ├─ Reader (.ply vertex OR face, .obj polygons)
 ├─ SceneGraph (actors + mapper buffers cached)
 ├─ Camera (orbit/pan/dolly updates per pointer move)
 ├─ Picker (vertex/cell, stable ID mapping)
 ├─ RenderWindow/OpenGL owner (host process)
 └─ Frame transport (shared-memory double/triple buffer + sequence ID)
      │   shared image frames (no PNG compression during interaction)
      ▼
Qt view compositor displays latest completed frame, not a static click-then-restart PNG
```

Essential semantics: `OpenSource(path,fingerprint)` **once** → validate/read/create actor once → accept continuous camera commands from `mouseMoveEvent`; `Pick(uv,view_revision)` emits immutable `SelectedPoint/SelectedFace DTO`; `Reset`, `Fit`, `Axes`, `Visibility`; `CloseScene`, `Shutdown`, timeout; all commands are cancellable/coalesced and typed. **No file read/hash per orbit, pan, zoom, pick**; read-only source integrity is pinned at load, and changes trigger explicit reload/invalidation. A high-frequency frame compositor can still show 2D pixel buffers, but the user manipulates an actual 3D camera and polygonal scene continuously. Do not confuse this with a native Qt OpenGL widget or claim 60FPS without evidence.

IPC specification candidate: protobuf/JSON length-delimited command messages under size caps and request UUID, strict session IDs; monotonically numbered scene/camera/frame revisions, only current response applied; shared-memory buffers with ready/ack ownership and explicit invalidation. Keep CPU/GPU memory budgets and child restarts observable; forbid stale frames, path traversal, command injection, unbounded queues; coalesce mouse deltas but preserve final camera state. Frame queue target latest-wins; independent pipeline for low-rate inspector metadata. Never send raw unvalidated pointers to GUI. Prefer reusable typed commands rather than bespoke UI string state.

### Candidate C — External native window (recovery only)

A persistent VTK native window may be used as a companion to the Qt shell, with coordinated open/close. Windows `HWND` reparenting and high-DPI/Win32 focus forwarding are unsupported assumptions until a PoC proves stable; never claim the result is a well-behaved dock just because a handle can be embedded.

## Geometry dispatch and data truth

| Input | Required rendering primitive | Picker | Caveats |
|---|---|---|---|
| PLY vertex-only | `vtkPolyData` vertices/vertex glyph actors | point ID + XYZ, RGB if present | unit/frame unknown unless source metadata trusted |
| PLY with polygon faces | surface mesh triangles/polygons, correct normals if computed | cell/point ID and native coordinates | no surface repair/measurement validity claim |
| OBJ | polygonal surface using appropriate VTK reader | cell/point ID when supported | MTL/texture optional with explicit support status; no material promise |
| Invalid/oversized/untrusted | refusal/visible error | none | bounded parsing, path safety and source fingerprint always |

**No synthesized pose, dimensions, CAD topology, watertightness or metric validity** from arbitrary input. Color/depth RAW remains GĐ0 source, not automatically associated with imported 3D files. Format detection must distinguish `.ply` with faces vs vertices, not infer mesh from extension alone. Scene actor count/point count provenance and `geometry_kind` are first-class DTO fields for R5.

## Crash/memory/lifecycle state machine

```text
STOPPED → STARTING → READY → LOADING → INTERACTIVE → CLOSING → STOPPED
              └──────── FAILED / RESTARTABLE ───────────────────────┘
```

- Resident render process starts lazily when opening the Viewer or first file; no VTK import at app startup.
- Crash/driver failure: Qt main process stays alive, collects bounded logs, clears invalid scene selection, shows `Renderer unavailable` and `Retry`/`Switch fallback` when safe.
- Closing busy: immediately stop accepting UI commands, send `Cancel`, wait bounded grace, terminate process only as a last resort; verify all descendants reaped; do not block GUI event loop with unbounded wait.
- Active camera: send high-frequency input events without full source read. On crash, old frame may temporarily be marked `stale`; never present it as up-to-date state.
- RAM measured as Qt + render host peak and working set separately, additionally process-tree and, if available, VRAM. Existing 08.06.3 memory correction must be retained in monitor.

## R4 A/B PoC matrix: numbers first, commitment later

Test each viable prototype on actual Windows, same fixture/driver/Qt/Python; cold and warm paths separated. Minimum datasets: vertex-only 1k/100k/1M; PLY face mesh 100k vertices and known faces; OBJ 1+ mesh fixture with source known; invalid PLY; stale file; repeated reopen. Operations: continuous orbit 30 s, pan 30 s, zoom 100 events, pick 100 varied points/faces, open/close 20 times, close while LOADING, forced native crash. Warm and cold latency, p50/p95/p99 pointer→frame, actual updated-frame rate (frame version increment), CPU, Qt/render-host RSS, cleanup. Record OS build and GPU/driver. All outcomes are evidence-bearing, not default `PASS`.

Initial **design targets, not established acceptance thresholds**: no >1-second redraw for routine 100k-point orbit; visibly continuous updates during a drag; strive for p95 <200ms input→fresh frame at 100k and <500ms at 1M on measured Windows configuration. Final objective thresholds must be frozen from actual PoC before R5 acceptance and must include a tolerated degraded mode for 1M scenes. Safety (no full-app native crash, close/reopen while busy) is a hard gate; if neither A nor B passes, R5 cannot replace renderer merely to appear 3D.

## Decision log

- **Primary:** persistent crash-isolated VTK process + shared-frame viewport (R4 PoC B).
- **Comparator:** embedded Qt VTK (R4 PoC A) only in stand-alone crash reproduction harness; no production changes.
- **Fallback:** current PNG preview only as explicitly labeled `Safe Preview/Compatibility` if modern renderer not yet validated; no falsely advertised real-time UI.
- **Rejected:** remove validation/hash/path guards or launch one VTK subprocess per pointer step as a performance fix.
- **Deferred:** UV texture fidelity, mesh editing/repair, fused point cloud, polygon segmentation, OBJ material complete support, camera pose estimator, ROI/metric results as future features.

## Links and risk ownership

`src/scantopath/modules/viewer3d/presentation/{controller,view}.py`, `infrastructure/{render_ply,render_navigation,pick_point}.py`, `docs/gd1/08_02_CRASH_REPAIR.md`, `docs/gd1/08_06_3_PERFORMANCE_STRESS_BENCHMARK.md`, `docs/gd1/08_06_5_DEFECT_DISPOSITION_AND_HMI_WAIVER.md`. **AR-02** (interaction latency) reopened for the upgraded goal; **AR-03** (close while native busy) remains OPEN until real B/C stress or equivalent reproduction passes. No waiver is treated as a test PASS.
