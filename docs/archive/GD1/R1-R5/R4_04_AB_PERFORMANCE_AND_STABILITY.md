# R4.4 - Native A/B benchmark and stability evidence

**Baseline:** `feat/gd1-desktop-ui@25d8fa0638abf6bea0dafa617022f9724775cd87` (R4.3 committed). R4.4 is an **additive measurement harness**, not a production Viewer change, architecture decision or guarantee of metric/3D correctness.

## Objective and measurement limits

Run **A = standalone PySide6 QVTKRenderWindowInteractor** and **B = isolated resident VTK process with acknowledged RGB24 shared memory** against the **same deterministic 1k/100k/1M vertex-only PLY files**, 640x480 viewport, and a fixed count of warm interactive camera updates. Each case runs in a bounded, disposable subprocess. The harness records cold source-open/render time, warm input-to-completed-render samples (p50, p95, p99), completed new-frame throughput, and observed renderer process working-set peak and CPU time; raw samples, source fingerprints, environment and failure logs remain in `_setup` outside Git.

**Do not mislabel frame readiness as screen presentation.** B measures input to immutable RGB frame acknowledged by the host. A measures Qt mouseMove dispatch through explicit VTK Render() completion. Native driver GPU display compositing, VSYNC, physical pointer-to-photon, actual 60FPS and VRAM are **NOT measured**. GPU driver info is separately captured by operator in Windows evidence. Workloads have comparable intent, not identical pixel trajectories or exactly equivalent timings.

B's R4.3 sequential interactive workload requires one fresh frame per input; separate R4.3 test proves burst coalescing, but **burst FPS is not a user-observed FPS metric**. `frames_dropped=0` in sequential mode is expected. Synthetic points have unknown unit/frame; no pose, watertightness or surface accuracy is claimed.

## Matrix and truthfulness

| Probe | A embedded comparator | B resident host |
|---|---|---|
| PLY points: 1k, 100k, 1M | Windows native required | Windows native required |
| 30 per-frame samples, 640x480 | Qt event to Render() completed | command to ACKed RGB ready |
| Native 20-cycle create/close or reopen | R4.2 comparator | R4.3 repeated open/close |
| Close while loading | Not exercised by this harness | B bounded stop immediately after submitting open (may race to finish; not guaranteed busy native work) |
| Native-crash isolation | Controlled process exit tested in R4.2, **not segmentation fault** | Controlled SIGTERM, **not segmentation fault** |
| PLY with faces / OBJ | Not part of equivalent R4.4 point benchmark | **DEFERRED_R5.1** (unsupported as implemented) |
| Invalid PLY / source mutations | Existing R4.1/R4.2/R4.3 regressions | Existing R4.1/R4.3 regressions |
| Native driver / VRAM / presentation | **NOT_MEASURED** by Python harness | **NOT_MEASURED** by Python harness |

Automatic exit code zero requires six real interaction reports (A/B x 3 sizes), positive p50/p95/p99, strict source fingerprint invariance, correct frame count, plus two stability reports at the requested cycle count. Any failed mode yields `MEASUREMENT_FAILED`, never fake success. Each run creates a unique folder with `SUMMARY.json`, `SUMMARY.csv`, raw times, logs and 3 synthetic source PLY files, and never overwrites prior evidence. Source PLY is in a temporary benchmark evidence folder and is **not RAW**.

Initial performance **targets**, not R4.4 facts: B 100k routine orbit p95 below 200 ms and 1M p95 below 500 ms. R4.5 must assess this with actual measured reports, memory and crash/lifecycle evidence, including tradeoffs and risks. R4.4 PASS means **measurement complete and validated**, not automatic selection of A or B.

## Operator workflow

Run `apply.ps1 -ProjectRoot $repo` (clean HEAD and commit pinned), then `verify.ps1 -ProjectRoot $repo -FullRegression -Benchmark` (full A/B measurement) on Windows with native Qt, Python 3.12, PySide6, VTK. This calls full tests and CTest before running the benchmark, then writes a receipt. Do not force `QT_QPA_PLATFORM=offscreen` for benchmark; verify clears that flag for native children.

Compare `SUMMARY.csv` and inspect `SUMMARY.json` + raw per-mode JSON, README test cases and logs. Record OS build, CPU, RAM, GPU model and graphics driver separately. If A crashes, don't delete it or retry until green: its failure is evidence; R4.5 may reject A. For B, do not hide any STOP failure or busy-close latency. Check Task Manager for host orphans, verify app unchanged. Every FAIL/FIX attempt belongs to `R4_04_OPERATOR_JOURNAL.md` and later GD1 master log. This PoC **never executes inside the production Viewer**.

Do not publish if the complete benchmark gate FAILS. If the result shows a repeatable native crash, **preserve logs and classify it** instead of changing thresholds or silently deleting the offending data. Publication of a research failure may be done with an explicit reviewed technical-debt decision in a later patch, not by forging a PASS receipt.
