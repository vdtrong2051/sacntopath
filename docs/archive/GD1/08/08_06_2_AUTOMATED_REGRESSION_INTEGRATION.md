# ScanToPath — GĐ1 / 08.06.2: Automated Regression & Integration

**Baseline:** `feat/gd1-desktop-ui @ 4586a3849e99e0ad6c7aff85dabf878c8640dc94` (08.06.1 audit pushed). **Scope:** automated regression and cross-feature Qt integration only; no runtime refactor.

## Deliverables and ownership

- `tests/test_gd1_08_06_2_integration.py` tests shell/project ↔ 3D viewer navigation, immutable Project Workspace state, synthetic successful PLY then invalid PLY recovery, child-process disposal, and no work after window closes. Qt offscreen tests do **not** claim a physical VTK/OpenGL/HMI PASS.
- `scripts/runner.py` (package-local) runs without installing dependencies: existing PySide6, VTK, pytest must already be installed in `.venv`. Verifies architecture import boundary, 07.12 quality gate, focused integration, **full** GĐ0+GĐ1 pytest, existing Qt JUnit validator, Python compileall, CTest Release, and hardware-free Orbbec native self-test (`native.hardware_access=false`).
- Failure stops the gate. All command logs, JUnit and JSON receipt are written in the external `_setup/.../acceptance/` directory; no generated files are added to Git. Exact file SHA and HEAD validated before and after.
- Full pytest: must execute all mandatory Qt/Viewer tests; **only two documented Windows symlink privilege skips** (`test_gd1_07_2_numbered_storage.py`, `test_raw_storage.py`) are allowed, never arbitrary skips. A skip elsewhere is an automatic failure. JUnit counts are actual values, not preset PASS claims.
- The focused suite includes 08.06.2 and established 08.02–08.05 Qt tests; it must not skip any test. Native fixture/PLY/camera/picking integration remains in the full suite.

## Explicit limitations / handoff

- This stage is automated **not** manual Windows HMI (08.06.4) and **not** measured memory/latency benchmark (08.06.3).
- Child shutdown test uses a harmless sleeping Python subprocess rather than an actual GPU driver to test Qt lifecycle deterministically. It does not prove all VTK native crash cases.
- Keep isolated VTK subprocess. Never embed `QVTKRenderWindowInteractor` into Qt main process based on offscreen success.
- Neither acquisition RAW nor SQLite is modified by this package. The full suite may create temporary fixtures/databases, not production data.
- Do not modify dependency versions, install VTK, modify firmware, run real camera or merge `main`.
- Once `verify.ps1` generates a PASS receipt, review `acceptance/08_06_2_SUMMARY.json` then invoke `publish.ps1 -ManualReviewAccepted` to publish only this doc and Qt integration test. Do not start 08.06.3 until this gate is accepted.
