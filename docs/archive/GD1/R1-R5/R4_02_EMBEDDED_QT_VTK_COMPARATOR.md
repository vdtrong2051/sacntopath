# R4.2 - Embedded Qt/VTK Windows comparator (standalone, isolated)

**Base branch/head:** `feat/gd1-desktop-ui@8c295e0000c734b709f4e99e68d7e8853362f257` with R4.1 applied as exactly seven new uncommitted files. **Scope:** A/B feasibility experiment, no production Qt Viewer integration or sqlite/camera/raw modifications. R4.1 and R4.2 are intended for ONE later combined commit after separate operator Windows acceptance.

## Question answered

Can PySide6 + VTK QVTKRenderWindowInteractor run native Windows OpenGL camera interactions, create/close repeatedly and exit cleanly on this actual Windows + GPU + driver configuration? Embedded VTK shares the Qt GUI process, so any C++ crash could terminate the entire application *if integrated*. The R4.2 experiment deliberately runs as a child executable and must not be confused with isolation of an embedded production implementation.

## Prototype boundaries

- `scripts/r4_2_embedded_harness.py`: runs Qt QApplication + QVTKRenderWindowInteractor in an isolated Python child process. Uses `vtkmodules.qt.PyQtImpl='PySide6'` and default QWidget host; no changes to ScanToPath runtime.
- `infrastructure/embedded_poc/runner.py`: pure-Python parent launches one child, checks exit code, timeouts, bounded report, preserves stdout/stderr. Qt and VTK imports are lazy *inside the child only*.
- `infrastructure/embedded_poc/contracts.py`: validates cycles, finite timing, non-offscreen platform, actual QVTK widget and changed camera pose after GUI mouse messages.
- `scripts/r4_2_embedded_comparator.py`: operator entrypoint; creates a temporary PLY fixture in the evidence folder; runs smoke, stress, manual and process-exit probe. No camera/RAW/SQLite access. `process_exit_probe` uses explicit `os._exit(86)` to demonstrate child isolation; **NOT** a reproduced VTK native crash.
- `tests/test_gd1_r4_2_embedded_comparator.py`: isolated contract/negative tests; not native Qt certification by themselves.

The Qt child constructs and tears down a new QVTK QWidget for each lifecycle cycle, attaches one VTK actor, performs a synthetic sequence of real Qt press/move/release events, checks camera movement, and records native render counts. Native driver faults may abruptly terminate the child; the runner treats any such termination as FAIL and retains bounded logs. `QVTK.closeEvent` owns RenderWindow finalization: never explicitly call a second Finalize during teardown.

## Data truth and limits

- For PLY, reuse GĐ1 `inspect_ply` header/bytes/SHA-256 checks and compare full SHA-256 again after run. The source is read-only and cannot be repurposed as writable output. Unknown units/frame remain unknown.
- A generated `4_point.ply` is only a GL + event/lifecycle smoke fixture; 1k/100k/1M points and representative mesh/OBJ throughput comparisons are for R4.4. VTK polygon fidelity is not certified in this patch.
- Qt native 100-window stress measures stability of in-process A *while isolated in a test child*. This alone cannot prove a production Qt process can recover from native segmentation faults. The R4.5 ADR must weigh this risk against R4.1 process isolation.
- No claims that automated event injection equals user drag UX; operator must check visually. No claims about p95 latency or target FPS until R4.4 common-workload measurement.

## Windows acceptance gates

1. Confirm branch/head and source-only scopes of R4.1 (7) + R4.2 (6). R4.2 verify re-executes R4.1 tests/demo under combined scope rather than calling the older R4.1 scope-limited verify; keep evidence in `_setup`.
2. Run `verify.ps1 -ProjectRoot <repo> -R41PatchRoot <...R4_1...> -FullRegression`. It first verifies R4.1 contracts and resident demo, then the full Qt/Python suite and CTest, then runs R4.2 contract tests, native smoke on a real Windows Qt platform, 100 independent create/close cycles, and controlled child-exit isolation probe.
3. Inspect `_setup/...R4_2.../evidence/r4_2_native_smoke.json` and `r4_2_native_stress.json`, output logs, and `R4_2_VERIFY_RECEIPT.json`. Native `qt_platform` must be `windows`, 100 stress cycles and native drag must be acknowledged. No logs from tests are stored in repository.
4. Run `scripts/r4_2_embedded_comparator.py --scenario manual --source <evidence>/r4_2_4_point.ply --report <evidence>/r4_2_manual.json` and physically orbit, pan and zoom. Check clean close, GPU/driver and HMI. Record operator verdict, OS, Python/PySide6/VTK versions, GPU driver and any crash/repro in `R4_02_OPERATOR_JOURNAL.md`.
5. After ALL gates and explicit manual HMI PASS, run external `_setup/...R4_2.../publish.ps1 -OperatorHmiAccepted` to create a **single combined R4.1+R4.2 commit** and push on `feat/gd1-desktop-ui`. It refuses mixed/unrelated Git changes, incomplete receipts, and unmatched SHA-256.

The `R4_2_VERIFY_RECEIPT.json` is an automation certificate *only*, not an HMI PASS; the publish switch is the operator's separate explicit attestation.

## Release status

R4.2 is **PATCH READY; NATIVE WINDOWS VERIFY PENDING**. Remote R4.1 was not committed as of the base HEAD. Do not promote prototype A into the main Viewer until R4.4 performance and R4.5 architecture decision.

## R4.2 architecture repair

The standalone Qt/VTK harness resides under `scripts/` because importing `PySide6` from `viewer3d/infrastructure` violates the established architecture boundary. The `infrastructure/embedded_poc/runner.py` contains only a source-tree subprocess launcher, and `contracts.py` remains Qt-independent. The native report now emits the required `widget` field so `read_report` can validate it. No production UI imports this comparator.
