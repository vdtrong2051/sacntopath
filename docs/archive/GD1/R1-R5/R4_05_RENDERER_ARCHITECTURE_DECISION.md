# R4.5 - Renderer architecture decision record (ADR-3D-001)

**Status:** CONDITIONAL ENGINEERING DECISION. **Branch/baseline:** `feat/gd1-desktop-ui@3280f62600c08133cce5860d8c81c0e39bccdebb` (R4.4 committed). **Authority:** direction for R5 experiments, not production acceptance. No production Viewer code changes in R4.5.

## Decision

**Choose B (isolated resident VTK Render Host + bounded IPC, explicit RGB24 shared-memory frame ACK) as the primary R5 integration prototype.** Keep A (in-process Qt QVTK) only as the isolated comparator. Retain the existing PNG compatibility preview until the R5/R6 safety and HMI gates pass. No unconditional promotion of B, no production Qt/VTK import, and no deletion of the compatibility path at R4.5.

This is a *conditional* choice, because benchmark A/B endpoints are not equivalent and the Windows native safety-critical acceptance remains incomplete. If the automated R4.5 evidence generator fails to validate R4.4 receipts or Windows resource telemetry, publication must not imply the decision is verified.

## Evidence reviewed from the operator's R4.4 Windows log

- Previous verified baseline: R4.3 commit `25d8fa0`; R4.4 committed HEAD `3280f626`.
- Windows 11 build 26300, Python 3.12.10, 30 interaction samples per size, 640x480, same vertex-only PLY sources per A/B comparison.
- R4.4 regressions: 566 PASS, 3 explicit Windows symlink-privilege SKIP; CTest 2/2; 6/6 A/B measurements PASS; A and B 20-cycle stability PASS.

| PLY points | B p50 / p95 / p99 ms | A p50 / p95 / p99 ms | B reported Hz | A reported Hz | B cold / A cold s |
|---:|---|---|---:|---:|---|
| 1,000 | 1.675 / 2.279 / 3.507 | 1.847 / 5.022 / 6.263 | 509.4 | 400.0 | 0.802 / 0.593 |
| 100,000 | 2.924 / 3.794 / 4.615 | 4.723 / 23.708 / 38.651 | 308.9 | 130.7 | 0.929 / 0.527 |
| 1,000,000 | 10.758 / 12.414 / 12.699 | 15.089 / 38.034 / 43.401 | 89.4 | 52.1 | 1.464 / 0.825 |

**These are operator-supplied R4.4 results, not independently replicated measurements by this patch.** `r4_5_decision.py` must read the existing R4.4 `SUMMARY.json`, six raw result files and PLY fingerprints from the operator's own `_setup` evidence before producing the R4.5 receipt. Do not claim 509 FPS on a physical monitor: A times Qt event to VTK Render() completion, B times input to immutable ACKed RGB bytes. They do not establish pointer-to-photon latency, vsync, or comparable trajectory/render presentation conditions. Cold B is slower on this run. There is no statistical inference beyond these limited 30-sample runs.

## Resource measurement correction

The R4.4 B host working set was recorded as approximately 4.4 MB and CPU time 0.0 seconds for all three workloads. These figures are **not accepted as evidence of B using less RAM or CPU**. The original `rss_bytes()` function sampled *current* `WorkingSetSize`, not Windows `PeakWorkingSetSize` for the lifetime. The `renderer_cpu_seconds` of 0.0 may reflect process CPU counter resolution and GPU-side execution. A and B also have different process topologies. R4.5 adds `r4_5_win_metrics.py` to observe both **Windows OS peak working set**, **current working set**, **private bytes**, and **CPU time delta**, for (A: Qt/VTK worker) and (B: supervisor + resident VTK host). These data are observational diagnostics, never dedicated GPU/VRAM. Memory totals may double-count shared pages; no ratio is an automatic performance gate.

The supplementary Windows probes use 100k and 1M fixture PLYs from the **same immutable R4.4 run** and a separate process per trial. The receipt must contain 4 valid native telemetry reports and traceable R4.4 SHA fingerprints. Suspicious telemetry is documented for interpretation rather than overwritten, clipped or labelled as a success of memory efficiency.

## Decision matrix

| Criterion | A - Qt in-process | B - isolated resident | Decision impact |
|---|---|---|---|
| Observed sample p95 (R4.4) | Higher for all 3 point sets | Lower for all 3 point sets | B favorable **in measured endpoints only** |
| Cold startup | Lower | Higher | A favorable for one-shot loads |
| Native failure domain | In production would share Qt app process | VTK in separately supervised child | B favored for protecting desktop/SQLite/RAW from native crashes; true native-fault injection still OPEN |
| Scene reuse | Qt live actor scene | Persistent VTK host, single load per scene | Both feasible |
| Qt integration | Direct native Qt widget, simple display path | Requires Qt shared-frame compositor and input mapping | B integration risk must be closed in R5.2 |
| Peak RAM / CPU | R4.4 numbers not fully comparable | R4.4 numbers suspicious/incomplete | Neither accepted until R4.5 telemetry reviewed |
| PLY faces / OBJ | R4.2 comparator can render faces, not validated as R5 geometry contract | Current resident rejects faces; OBJ unsupported | **R5.1 blocking feature** |
| Crash recovery | In-process crash could bring down application | Supervised failure/retry possible in principle | B preferred, recovery in production still UNPROVEN |

## Stage R5 delivery contract and hard gates

1. **R5.1 Geometry source/scene boundary:** validated, read-only PLY points, polygon PLY meshes and OBJ; geometry-kind DTO, face/point counts, bounds, source fingerprint, no fabricated units or coordinate frame; typed picking contracts. No implicit RAW data edits or SQLite writes.
2. **R5.2 Resident Qt viewport:** UI thread owns only Qt widgets and immutable DTOs; render worker owns VTK; import and source hash occur once; nonblocking drag orbit/pan/zoom/fit; compositor accepts monotonically increasing scene/input/frame revisions, rejects stale frames and frees buffers only after copy/ACK. Window lifecycle, timeout, close during genuinely busy VTK render, kill/restart and child orphan cleanup are mandatory.
3. **R5.2 Interactive acceptance:** actually exercise mouse drag while the display updates, with measured input-to-present or an expressly labelled/validated proxy; do not use R4.4 `fresh_frame_rate_hz` as screen FPS. Confirm 100%, 125%, 150% DPI and source selection. Capture CPU/working set/VRAM as available; if telemetry is missing, state missing.
4. **R5.3 Interaction UX:** usable point/face picking, Inspector provenance, scene layers where real, error/retry, keyboard accessibility; no fake functionality or hard-coded demonstration metadata.
5. **R6 integration & final gates:** full Python/Qt/CTest, Windows HMI, repeated reopen, fault containment, data integrity, benchmark on hardware, recorded deferred limitations. Do not grant 08.06.6 baseline freeze at R4.5 or R6 alone; R7/R8 remain in the agreed roadmap.

## Open risks and ownership

- **AR-02:** legacy gesture-to-PNG latency reopened for modern interaction. R4.4 indicates promise, but R5.2 must measure **actual UI interaction**; status OPEN.
- **AR-03:** close while native busy, Windows process-tree cleanup and native fault injection unproven. R4.4 close-race is not deterministic; status OPEN and non-waivable for production.
- **AR-04:** 4.4 MB B memory and 0.0 CPU anomaly; follow-up R4.5 resource audit, no conclusion about memory efficiency until reviewed.
- **AR-05:** A/B endpoints, gesture trajectories and vsync/display presentation not equivalent; R5.2 instrument Qt compositor.
- **AR-06:** mesh/OBJ and picking contracts deferred to R5.1.
- **AR-07:** resident two-slot shared memory, ACK, restart and thread handoff require integrated Qt lifecycle, not assumed from isolated PoC.

## Handover and provenance

R4.1/4.2 `3110dca`, R4.3 `25d8fa0`, R4.4 `3280f626`. Historical design ADR `R1_03_RENDERER_ARCHITECTURE_ADR.md` remains intact as pre-measurement proposal. R4.5 supersedes it only for the **R5 engineering direction**; no historical document, waiver or failed attempt is rewritten. Per-session journal: `_setup/ScanToPath_GD1_R4_5_Architecture_Decision/evidence/R4_05_OPERATOR_JOURNAL.md`. R7 will consolidate into GD1 and master execution logs. If the diagnostic fails, log each attempt and root cause; never change a measurement to force PASS.
