# HS-01.3 — Auto Keyframe → RAW v2 Commit (2026-11-01)

**Implementation scope:** opt-in auto capture through the existing Qt Capture workspace. No new camera process, no new database schema, no RAW migration, no point-cloud registration. No automatic hardware operation at import/startup.

## Data flow

`LiveStreamWorker → LiveCaptureUiController / DepthAnalysisThread (one-slot analysis mailbox) → AutoCaptureController → AutoCaptureSession (HS-01.2 selector) → CaptureActionCoordinator.capture_auto() → LiveCameraController.capture_keyframe() → LiveStreamWorker → fresh native RAW-v2 → CaptureActionCoordinator / _StoreActionThread → NumberedCapturePersistenceAdapter → SQLite + verified RAW replay → action.finished(capture_id) → AutoCaptureSession.mark_saved()`.

`SELECT` is a pending preview suggestion, **not** Capture identity or successful persistence. If the new RAW read is stale relative to the triggering preview frame, reject. Capture receipt is only acknowledged after existing RAW write, registration and replay verification pass.

## Architecture

- `application/auto_capture_session.py` owns counters, selector, capture pending, Stop and success/failure state, no Qt, SDK, storage.
- `presentation/auto_capture_controller.py` owns the opt-in UI callback and captured Scan Session identity; it **delegates all actual capture and storage** to the existing `CaptureActionCoordinator`.
- `presentation/depth_analysis_worker.py` returns analyzed frame + tracker via an **overwrite-one mailbox**, not unbounded Qt frame signals; `live_ui_controller.py` checks camera generation/index before forwarding.
- `CaptureActionCoordinator.capture_auto` reuses its existing preflight/capture/persistence pipeline, validates new RAW indices strictly exceed the triggering preview and preserves selection of the same Scan Session after each successful auto commit. Manual `capture()` still selects the Capture entry as before.
- Auto mode requires a chosen open Scan Session in the numbered SQLite v2 store. During automatic capture, selecting a different Session stops proposing further keyframes. The preflight and commit path checks context again.
- Automatic mode starts **OFF**. Enabling it does not start camera without explicit user Start. Stopping auto during an in-flight capture does not interrupt or destroy the ongoing storage transaction; subsequent receipt can still be recorded and no new auto request is started.
- Terminal storage integrity errors STOP automatic selection and require inspection/recovery. They must not be silently retried. Nonterminal capture timeouts can be retried after a subsequent valid proposal.
- ROI source switch resets HS-01.2 novelty history; dynamically adjusted ROI coordinates are handled by overlap test within existing selector.

## Verification

Targeted offline checks in operator Windows environment (run `INSTALL_HS_01_3.py --repo <repo> --smoke` after applying):

- HS-01.2 baseline: 24 tests.
- HS-01.3 pure state tests: 15 tests.
- HS-01.3 Qt mock tests: 7 tests (requires PySide6), including Session retention after saved RAW.
- Existing Capture UI / lifecycle test subset.
- Architecture and compileall checks.

The packaging environment has no PySide6; **Qt mock tests and full integration are pending Windows execution**, not counted as a verified pass here. There is no real Gemini 2 test in HS-01.3 software preflight.

## Known constraints / deferred checks

1. New RAW is **not necessarily the same frame** as the preview that triggered it. Monotonic frame indices and RAW verification do not establish identical visual content or correct multi-view registration.
2. HS-01.2 quality scores are deliberately approximate: RGB sampling is not calibrated pixel alignment, image texture is not pose novelty, and camera motion too fast may cause missing/poor frames.
3. `saved` counts only receipts emitted from RAW persistence/replay verification, not number of SELECT proposals. Source/store audit remains the ground truth and will be verified with real Gemini 2 in the later hardware gate.
4. Some scenes have no trackable ROI; use the existing manual ROI fallback. No object segmentation or auto underside coverage is claimed.
5. On a failed mid-write registration, the existing storage layer leaves a recoverable reservation. Do **not** delete/retry-overwrite it automatically.
6. No claim of MB-01/MB-05, geometric accuracy, or 5 physical viewpoints until hardware test evidence is collected.

## Follow-up physical acceptance (NOT EXECUTED)

Separate fresh test store → choose open Scan Session → camera Start → Auto Keyframe ON → handheld motion around a textured object → Stop → count unique verified RAW v2 Capture IDs and session links → replay independent RAW/metadata/calibration/checksum → test Stop, context switch and error recovery. Agree exact recording protocol with operator before running physical acceptance.
