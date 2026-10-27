# GD1 08.02 — Native Qt/VTK crash containment repair

Baseline `feat/gd1-desktop-ui` @ `ce53f31cead2a27eba41ffb9ac1bc995471f8f83` (08.02 source committed, **Windows HMI FAILED**). The 08.02 session is NOT accepted until repaired acceptance passes. There is no 08.03 work in this patch.

## Evidence and root-cause status

- Original `Viewer3DController._initialize()` instantiates `QVTKRenderWindowInteractor` and calls `Initialize()` and `Render()` **inside the main Qt process**. A GPU/OpenGL/VTK native termination is not recoverable with a Python `except` clause.
- Existing 08.02 Qt tests set `QT_QPA_PLATFORM=offscreen`, expressly bypassing native render; therefore 400+ green tests did not validate the crashing path.
- **Exact native root cause on the user's Windows machine remains unconfirmed.** VTK/PySide6 and OpenGL/driver version incompatibilities are possible, not verified diagnoses.

## Repair behavior (consciously narrow)

- Preserve `viewer3d` Modular Monolith + MVC: Qt `Viewer3DPage` draws an immutable PNG; `Viewer3DController` supervises a bounded `QProcess`; `render_preview.py` instantiates `VtkFixtureScene` and renders it **with VTK in a separate Python process**.
- The child imports neither Qt nor SQLite nor Orbbec. A child native crash/timeout is reported in the Inspector workspace and terminal while the parent Qt application stays running.
- The five real VTK-produced fixture points have `units=None`, `coordinate_frame=fixture_local`, `source=synthetic_08_02`.
- **Deliberate capability limitation:** The 08.02 repair uses a *static VTK-rendered preview*, not an interactive native `QVTKRenderWindowInteractor` widget. Orbit/pan/zoom, PLY import and picking are NOT implemented. Mouse navigation remains scheduled for 08.04, and may use process-safe IPC. Do not claim an interactive viewer has been delivered.
- No VTK installation or upgrade is attempted; existing `.venv` is used. No SQLite schema, RAW, acquisition, C++, project workspace, camera access, or research dataset edits.

## Acceptance required

1. Exact committed baseline, clean worktree, scoped patch integrity PASS (no checkout/reset/migration).
2. `pytest` focused + full, architecture import check, quality gate, CTest, native hardware-free self-test PASS.
3. **Independent real VTK subprocess PNG test** on Windows PASS using current installed VTK; nonzero exit, timeout or missing PNG fails verification. Offscreen Qt GUI tests alone do not satisfy this gate.
4. Manual HMI: application opens Projects; clicking **Kiểm tra 3D** leaves main window responsive, then displays five blue fixture points rendered by VTK, tagged `FIXTURE 08.02` and "tiến trình riêng". Switch Projects/Inspect3D, close/reopen app three times. No crash/hang, no duplicate subprocess, no DB/RAW changes.
5. On subprocess failure: GUI remains open and reports child exit status and diagnostic excerpt; take logs before retrying. **Not accepted** if five VTK points do not appear.
6. Explicit user HMI acceptance + verified receipt before commit/push. No `main` merge, no 08.03 until 08.02 passes.

The original live VTK-in-Qt integration is not restored by this containment repair; a native in-process variant must be evaluated separately if required by 08.04 UX. This tradeoff is explicit rather than hiding potential crashes.
