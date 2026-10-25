# ScanToPath GĐ1 / 08.02 — VTK Viewer Foundation

Baseline `feat/gd1-desktop-ui @ 7207a7354099a5c77d340993de755cc46baaf78b` (08.01 committed and accepted by operator).

## Scope and ownership

- New module `modules/viewer3d` follows feature-local MVC and SOLID. `domain/fixture.py` is a frozen five-point fixture, `application/ports.py` declares the narrow scene protocol, `infrastructure/fixture_scene.py` builds pure VTK actors, `presentation/view.py` owns Qt widgets, and `presentation/controller.py` owns GUI-thread VTK lifecycle.
- `ui/shell/main_window.py` **only composes** the Viewer with a lazy factory when Inspect 3D is activated. The other three pages and Project Workspace are unchanged. A fixture is tagged `FIXTURE`, **never a measured cloud**.
- Extra `.[viewer]` declares VTK explicitly; shell and UI imports remain usable without importing VTK. No artificial second worker manager. The fixture requires no worker because constructing five points is fast and GUI-owned.
- Qt `offscreen` tests deliberately defer native OpenGL rendering. Real GPU/Windows visual smoke is **mandatory** before 08.02 acceptance. Offscreen PASS does not establish actual VTK interoperability.
- VTK Qt host and rendering stay GUI-thread bound; on window closure `Finalize()`, actor removal and widget deletion are called once. The viewer is allocated only when first opened and reused across navigation.

## Not in 08.02

- No PLY import, background file loading or cancellation (08.03).
- No advanced orbit/zoom/pan/reset UX and coordinate axes controls (08.04); built-in VTK interactor has default gestures for visual smoke.
- No point picking/Inspector/layers (08.05), no large-cloud benchmark (08.06).
- No SQLite, RAW, Gemini2 SDK, C++ core, calibration, metric validation, registration, geometry or AI changes.

## Acceptance (Windows)

1. Branch/HEAD+SHA guarded apply with an initially clean worktree. No reset/checkout/migration and no changes outside manifest.
2. Install explicit `viewer` dependency in the project venv (after 08.01 isolated probe passed). Record `PySide6` and `vtk` versions.
3. Architecture 08.01 import guard, 07.12 quality gate and new 08.02 fixture/Qt tests; full Python+Qt regression, accepted Windows symlink skips only; compileall, CTest `2/2`, native no-camera self-test.
4. Physical Windows UI: open ScanToPath, click **Kiểm tra 3D**; five fixture points appear. Switch to Projects and back, view persists, no blank/duplicate actor. Close and reopen several times. No camera/SQLite automatically opened. Real-GPU viewport visual operator approval required.
5. Generate hash-bound automated receipt then publish exactly the scoped files on feature branch, no `main` merge.

The reader must not be described as implemented until 08.03, and `08.02 PASS` only follows the Windows acceptance result.
