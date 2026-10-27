# ScanToPath GĐ1 — 08.03 PLY Import & Data Contracts

**Base:** `feat/gd1-desktop-ui @ 26845ab727f723eb046a26ca172fb47e1e1017d1` (08.02 Crash Repair accepted and pushed). **Scope:** offline local PLY → real VTK rendered PNG + read-only summary. No VTK install or upgrade.

## Implemented workflow

1. Existing lazy `Viewer3DController` opens the Inspect 3D page, retains 08.02 five-point fixture and its safe isolated subprocess renderer.
2. **Mở PLY…** selects a local file. Qt does not read the point-cloud payload and imports no `vtkmodules`.
3. `QProcess` starts an isolated `render_ply` child, with 60-second deadline and cooperative UI responsiveness; the button is disabled during active loading. An unresponsive child is killed. No simultaneous render jobs.
4. Child applies a bounded PLY 1.0 header preflight (ASCII / little-endian / big-endian; up to 256 MiB and 1,500,000 vertices), requires scalar XYZ, and uses VTK `vtkPLYReader` + glyph/filter to render *points* as a PNG. It is not a mesh renderer. It checks finite XYZ, source size/mtime and creates a JSON summary.
5. GUI validates PNG signature/size and JSON typed contract, then shows the **actual VTK render** along with point count, XYZ bounds, optional RGB and `unknown` units/frame. No database or RAW updates and no inferred metric validity.
6. If input is missing, malformed, oversized or VTK/native fails, GUI stays alive and reports failure. Older preview remains visible rather than being silently replaced by fake data.

## Architecture / ownership

- `domain/fixture.py`: unchanged deterministic 08.02 synthetic fixture.
- `application/ply_contracts.py`: Qt- and VTK-independent immutable `PlySummary` for untrusted JSON result validation.
- `infrastructure/ply_header.py`: bounded read-only file preflight and SHA-256.
- `infrastructure/render_ply.py`: VTK native file reader and renderer, only executable in isolated subprocess.
- `presentation/controller.py`: Qt UI signal routing, QProcess lifetime, timeout/error and result validation.
- `presentation/view.py`: labels, button, static PNG; contains no VTK parser or process orchestration.
- `ui/shell/`: unchanged; existing lazy Viewer composition remains.

**Modular Monolith + MVC + SOLID:** Application/Domain import neither VTK nor Qt. Presentation does not import infrastructure implementation; it invokes a dedicated subprocess CLI without importing it into GUI. Shared `metadata`, `storage`, `acquisition`, GĐ0/native/C++, and Project Workspace remain unchanged.

## Validation / limits

- PLY `x,y,z` are only raw file coordinates: **unit and coordinate frame remain unknown** regardless of the numeric values. No `metric_validated`, `measured`, calibration, registration, fusion, ROI, crop, normals, or point-picking claim.
- Point colors are read if VTK provides supported RGB point scalars; otherwise default visualization is blue. Some uncommon PLY property schemes are intentionally rejected rather than guessed.
- PLY geometry is displayed as a **static PNG** for native crash isolation. Live orbit, pan, zoom and reset belong to 08.04 and require a fault-isolated interactive renderer design. This step does not reintroduce embedded `QVTKRenderWindowInteractor`.
- The SHA-256 is the checksum of file bytes read at inspection time, not a quality or calibration certificate. File size/mtime are rechecked after native rendering; concurrent adversarial modification and all filesystem race conditions are not exhaustively solved.
- 256 MiB/1.5 million points and 60s are preliminary safety limits, not performance benchmarks. Larger and malformed files must fail safely; 08.06 will establish measured performance limits on Windows hardware.
- Native faults may abort *only* the subprocess; Qt remains alive. This is a safety/availability property and not proof every graphics driver is compatible.

## Acceptance gates

1. `apply.ps1`: exact Git base, branch, clean working tree, SHA-bound changed paths; no reset/checkout.
2. `verify.ps1`: no package installation; check preexisting vtk/PySide6; real isolated ASCII RGB PLY render, invalid PLY refusal, metadata/PNG + SHA; focused 08.03 and prior 08.02 tests **no skipped tests**, full Python/Qt regression, architecture/07.12 quality gates, CTest 2/2 and native acquisition self-test (no camera).
3. **Windows HMI:** launch app; 08.02 fixture still renders; click Mở PLY and load a trusted small ASCII or binary point cloud; read nonzero point count/bounds and unknown unit; switch Projects ↔ Inspect 3D 5×; load a second PLY; reject malformed PLY without crashing; close/reopen app; Project Workspace still works.
4. `publish.ps1` only after automated receipt **and** manual approval; exact scoped paths on `feat/gd1-desktop-ui` only; no `main` merge. Proceed to 08.04 only after 08.03 accepted.
