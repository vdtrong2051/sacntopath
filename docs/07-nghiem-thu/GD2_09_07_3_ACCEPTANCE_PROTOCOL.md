# GD2-09.07.3 — Windows + Gemini 2 Acceptance Protocol

> Scope: depth suggestion, manual ROI, Qt Live UI, lifecycle/replay coexistence.  
> Baseline: `feat/gd2-mvpb-20261104 @ 7d228078c1481a5ab856fded75068b1be2a716a2` + uncommitted 09.07.1/09.07.2.  
> **No RAW capture/SQLite write, no camera pose, no object mask, no semantic detection.**  
> A screenshot of streaming UI alone **does not** prove the automatic ROI is correct.

## Setup and required evidence

- Windows desktop display (not `QT_QPA_PLATFORM=offscreen`); Gemini 2 via USB 3; OrbbecViewer closed; OrbbecSDK DLL path set.
- Prepare **one matte, simple object** (box or statuette) at ~0.5–1.0 m and a reasonably flat background at least ~0.3 m farther away; avoid people and other near objects in the test field of view. Record actual distances as measured or *estimated* (never claim calibrated).
- Close other camera apps, keep an empty Project selection for live-only checks. Never automatically create a Project/ScanSession or write RAW.
- Store pytest output, hardware JSON (metadata only), manual results, test environment and optional **operator-approved** screenshots/video outside tracked source (`E:\1_BigProject\scantopath\_setup\evidence\gd2-09-07-3`). Never commit raw images, face images, or sensor frames.
- `GD2_09_07_3_HARDWARE_UI=PASS` tests lifecycle/UI wiring **only**. Physical object detection needs the following manual gates.

## Physical/UI test cases

| Test | Operator action | PASS criteria / evidence | Result |
|---|---|---|---|
| H07-01 | Open ScanToPath and Capture without clicking Connect | Camera IDLE; no frames or SDK auto-opening; 4 workspaces and 3 docks preserved | NOT_TESTED |
| H07-02 | Click Connect with Gemini 2 plugged in | STREAMING, RGB 1920×1080, Depth 1280×800, updates repeatedly; UI navigation remains responsive | NOT_TESTED |
| H07-03 | Place **one matte object** clearly in front of distant background; hold for 5 s | Auto bbox visibly encloses the object, not entire room/body; frame grid is 1280×800; label reports tracking. Compare with operator-drawn ROI (see H07-07); target overlap IoU ≥ 0.50, record discrepancies. | NOT_TESTED |
| H07-04 | Move object slowly left/right 10–20 cm while keeping background similar | Auto bbox follows object with no persistent old box or large unintended jump; describe jitter/lag | NOT_TESTED |
| H07-05 | Put two similarly sized objects at comparable distance | If equally plausible, system reports ambiguity/absence rather than falsely locking the wrong object; note if heuristic fails | NOT_TESTED |
| H07-06 | Show flat/empty background or mostly invalid Depth | No fabricated confident box; notice `no_target`/low confidence as appropriate | NOT_TESTED |
| H07-07 | Enable “Chọn ROI thủ công”; drag around visible object, then hold scene 3 s | Green ROI; source MANUAL; coordinates x/y/w/h in original 1280×800 Depth grid, bounded and stable even as auto analysis updates; click “Dùng ROI tự động” to relinquish override | NOT_TESTED |
| H07-08 | Resize/maximize and restore main window, including letterbox margins | ROI stays on same object; same stored Depth coordinates; dragging only outside image yields no selection | NOT_TESTED |
| H07-09 | Stop → wait CLOSED → Connect again; switch Capture ↔ Projects | No stale bbox/manual ROI after stop/reopen; camera closes on leaving Capture, never opens automatically when returning | NOT_TESTED |
| H07-10 | While live STREAMING, close the app; then launch it again | Safe cooperative shutdown, no hanging/orphaned Qt/SDK worker, camera available next launch | NOT_TESTED |
| H07-11 | Open registered RAW v2 from a test Project (if available), use replay after stopping live | Replay RGB/Depth unchanged; no store writes, no replacement of captured RAW; if no test Project, record NOT_TESTED and do not fabricate PASS | NOT_TESTED |
| H07-12 | Disconnect Gemini 2 **only after CLOSED**, then attempt Connect and Retry after reconnecting | FAILED with useful error, no freeze; explicit Retry after cleanup returns STREAMING; skip if not feasible and document reason | NOT_TESTED |

**IoU** for H07-03: intersection area divided by union area of **auto bbox** and **manual reference bbox**, both measured in the same Depth grid. The 0.50 threshold is an engineering *acceptance target* for this declared demo scene, not an accuracy guarantee for arbitrary objects. If the scene has no distinct near foreground, mark H07-03 FAIL or NOT_TESTED; manual ROI passing does not make auto detection PASS.

## How to run

1. Run `ScanToPath_GD2_09_07_3_VERIFY.ps1` (automatic related regression and architecture; **no sensor**). All commands must exit 0.
2. Close the actual ScanToPath application, set the SDK DLL variable and unset Qt offscreen; run `python scripts/gd2_09_07_3_hardware_probe.py --cycles 2 --seconds 5 --output <NEW_JSON_PATH>` (automated *real* UI Start/Stop/Reopen/shutdown). Each cycle has real RGB/Depth, an analysis result and a fully reaped camera. No images saved.
3. Open `python -m scantopath.ui.main` and perform H07-01 to H07-12 manually, marking PASS / FAIL / NOT_TESTED and noting scene/time/distance/firmware. The observed UI screenshot previously showed a large yellow bbox; **do not** assert object accuracy until testing a single controlled specimen.
4. Keep all gates of the full session (G2-09-A/B/C, ARCH/DATA/LIFE/REG) `NOT_TESTED` until 09.09; 09.07.3 is a step gate only. Do not stage, commit, or update ledger until review of actual manual receipts.

## Sign-off form

- Operator: ______
- Date and local time: ______
- Git branch and SHA: ______
- OS / Python / Qt: ______
- Camera name / firmware / USB: ______
- Fixture, background, camera-object distance: ______
- Automated pytest: ______ passed / ______ failed / ______ skipped
- Architecture: ______ violations
- Hardware JSON: ______
- H07-01..H07-12 manual results and evidence: ______
- Blockers (particularly H07-03/05/06): ______
- Final 09.07.3: **PENDING** / **ACCEPTED** / **BLOCKED**
- Reviewer / commit SHA (only after accepted): ______
