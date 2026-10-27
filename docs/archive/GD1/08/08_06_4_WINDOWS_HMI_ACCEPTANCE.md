# ScanToPath — GĐ1 / 08.06.4 Windows HMI Acceptance

**Baseline:** `feat/gd1-desktop-ui @ 5e3c176077008e77087a4db88140e75806c520a2` (08.06.3 reviewed and published, native benchmark measured). **Scope:** real Windows UI validation for accepted 06/07/08 feature slice; do not build 08.06.5 or 08.06.6 here.

## Goal and evidence levels

- Preflight: focused Qt contract tests, architecture / quality guard, pre-existing CTest and hardware-free native self-test. `QT_QPA_PLATFORM=offscreen` applies **only** to these automated tests, and is **not** visual evidence.
- Native HMI: launch `scantopath.ui.main` with Qt desktop plugin (no `QT_QPA_PLATFORM=offscreen`), via direct PID-verified Python interpreter. Observer records actual GUI RSS, descendants' RSS and their lifetime per A/B/C session; **sampled process WorkingSet, not GPU VRAM or proof of no memory leaks**.
- Operator: manually evaluate TC01–TC12 and provide screenshot hashes plus notes; explicit acceptance of measured ~1–3s camera/picking latency for **UI MVP-A (inspection mode only)**. If UX insufficient, record FAIL and route to 08.06.5. Never equate script exit 0 with visual PASS.
- Data: all PLY files are deterministic synthetic fixtures with `units=unknown` / `coordinate_frame=unknown`; never claim calibration/Gemini 2 measurement or source metric validity. Preserve GĐ0 RAW and SQLite.

## Test cases and session protocol

Three independent HMI launches are mandatory. Save screenshots in `acceptance/evidence` with **exact** `TC02.png`, `TC04.png`, `TC05.png`, `TC06.png`, `TC07.png` (or jpg). Keep evidence in `_setup`, outside Git.

| Test | Session | Procedure / expected result |
|---|---|---|
| TC01 | A | Startup, Project Workspace and fixture 5 points; UI responsive, no driver crash. |
| TC02 | A | Open `TC02_ASCII_RGB_4pts.ply`; 4 RGB points, bounds X[0,1] Y[0,2] Z[0,3]. |
| TC03 | A | Open `TC03_BINARY_3pts.ply`; 3 points, no RGB, bounds X[-1,2] Y[0,4] Z[0,5]. |
| TC04 | A | After TC03 load `TC04_INVALID.ply`; short red error, old preview/metadata cleared, no traceback; reopen valid file afterwards. |
| TC05 | A | Orbit/pan/zoom/reset; change/revert view; toggle reference XYZ axes. |
| TC06 | A | Select fixture point: expected zero-based Point ID and XYZ. Click blank background: only selection cleared. |
| TC07 | A | Select RGB point from TC02: XYZ/RGB present; units and frame remain unknown. |
| TC08 | A | Toggle one cloud layer: hide and show, no false selected point. |
| TC09 | A | Switch Project ↔ Inspect3D **20 times**, verify Project tree/Inspector still operate. |
| TC10 | A | Import valid/invalid PLY **10 sequential attempts**, no stale image or UI freeze. |
| TC11 | B | Initiate import of 1M point `TC11_BUSY_CLOSE_1000000pts.ply` and close window immediately **while processing**. Native process must be cleaned up; observer session B records no child left. Repeated if process finishes before close. |
| TC12 | C | Relaunch after busy-close, reopen Project and fixture/PLY; close gracefully; no stale state. |

**Session A:** run `launch-hmi.ps1 -Session A` and perform TC01–TC10. Keep the same window open while switching tabs; close normally when done.
**Session B:** run `launch-hmi.ps1 -Session B`, start the 1M import and close immediately while it is busy. If VTK completed before close, repeat/record why (do not claim close-while-busy PASS).
**Session C:** run `launch-hmi.ps1 -Session C`, ensure Project/Viewer recover, then close.

> The observer samples descendant processes at 250 ms; very short-lived child processes can be missed, and the sampled RSS maximum may understate absolute peak. It records only direct descendants of the GUI it launched (not any unrelated user's Python processes). When GUI closes, observed descendants must also have exited. No forced native crash injection is performed.

## Acceptance gates

1. Git HEAD, branch and manifest match; clean working tree before apply; doc-only payload; no source changes.
2. Automated preflight PASS with 0 skipped focused Qt tests, mandatory lifecycle tests executed, architecture/quality PASS, CTest and hardware-free native self-test PASS.
3. Fixture hashes PASS. Three genuine Windows Qt sessions each have normal exit, 5+ resource samples, real GUI RSS >35 MiB, timeout false and no surviving observed child processes. Session data is machine-readable.
4. TC01–TC12 marked **PASS** by operator, five required screenshot files exist with hashes, UX latency explicitly accepted. If ANY test FAIL, no receipt; log defect for 08.06.5.
5. Receipt hash-binds manual record, screenshots, preflight and A/B/C sessions. `publish.ps1` refuses missing receipt or absent `-ManualHmiAccepted` switch. Only documentation file goes to the feature branch; no `main` merge.

## Out of scope and risk ledger

- Do not reintroduce in-process VTK OpenGL or `QVTKRenderWindowInteractor`, install dependencies, use camera, alter SQLite/RAW, change provenance or start GĐ2.
- AR-02: startup-based VTK action latency measured ~1–3 seconds; acceptable only if operator confirms static-inspection UX goals. **Not** a 60 FPS or live viewport acceptance.
- AR-03: close-while-active/child cleanup are mandatory manual+observer checks; monitor cannot prove absence of every Qt race or a graphics-driver-specific crash outside tested sequence.
- AR-04: this is a PNG-based viewer updated after each action; clarify limitation in final 08.06.6 acceptance.
- 08.06.5 is reserved for defects found by this review; it is not automatically required if there are none.
