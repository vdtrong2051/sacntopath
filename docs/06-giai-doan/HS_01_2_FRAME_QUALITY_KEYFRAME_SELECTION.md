# HS-01.2 — Frame Quality & Automatic Keyframe Selection

- Scope: **application-only, offline; selection suggestion; no hardware capture/persistence/UI wiring**.
- Basis: ScanToPath V2 GD2-09 `LiveRgbdFrame`, native-depth `DepthRoi`, tracked ROI in existing UI.
- Evidence: two focused pytest modules; no substitute for Gemini 2 Windows runtime test.

## Contracts

`FrameQualityEvaluator.evaluate(live_frame, depth_roi)` -> `FrameAssessment`:
- `ROI_REQUIRED` if no ROI: **never silently select the full background scene**.
- `INSUFFICIENT_DEPTH` for invalid/missing metric depth samples within ROI.
- `LOW_FOCUS` only if explicitly configured (`min_focus_score > 0`). Low-texture surfaces alone are **not** rejected by default.
- `OK` with sampled depth fraction, focus variance, tiny immutable signatures.

`KeyframeSelector.evaluate(live_frame, depth_roi)` -> `KeyframeSelectionResult`:
- `SELECT`: recommendation to issue a **new RAW capture** in HS-01.3, not permission to persist the preview buffer.
- `WAIT`: await ROI/stabilization/cooldown/novelty or pending capture.
- `REJECT`: invalid quality, stale frame.
- `reason_code`, `frame_index`, `timestamp_us`, `motion_proxy_m`, `novelty_score` are diagnostic fields.

`capture_completed(True)` MUST occur only **after fresh RAW was successfully verified/persisted**; call `capture_completed(False)` on errors. Until then a `SELECT` is latched pending, avoiding multiple simultaneous capture requests. `reset()` is compulsory after stop/reopen, source switch or scan-session change. Keep all calls serialized on one owner (e.g. analysis thread / event dispatcher).

## Assumptions / deliberate limitations

1. RGB-D images are **not aligned**. The depth ROI is sampled in the native Depth grid; an approximate proportional RGB crop is used only for a brightness/texture proxy. **No metric 3D RGB registration is asserted.**
2. Motion proxy is median depth difference at matched image sampling bins; novelty proxy is normalized depth/brightness difference relative to the last acknowledged preview. **These are neither calibrated camera movement/pose nor physical overlap/6DoF**. Lighting/background changes can yield false novelty; low-texture or symmetric surfaces can defeat novelty. Actual pose/overlap validation belongs to HS-02.
3. `sample_grid=16` bounds processing to 256 depth and 256 color samples. Scores and thresholds are **provisional defaults requiring tuning on Gemini 2 data**; there is no real-camera acceptance for HS-01.2 yet.
4. No capture ID, raw packet, timestamp synchronization, registration pose, object mask or SQLite writes are generated. The selected preview differs from the **subsequent** fresh RAW; HS-01.3 must revalidate captured RAW.
5. `DepthRoi` comes from existing tracking/manual UI. A missing/ambiguous ROI produces `WAIT`, so a user can override via existing manual ROI.
6. Existing GD2-09 architecture and original RAW-v2 contracts remain unchanged. No direct imports of UI, native SDK, SQLite, storage or Open3D.

## Acceptance gates

| Gate | Requirement |
|---|---|
| KF-01 | Reject insufficient/out-of-range depth. |
| KF-02 | Do not select missing ROI. |
| KF-03 | Do not repeatedly select identical preview. |
| KF-04 | Select stable changed preview after acknowledgment and cooldown. |
| KF-05 | Enforce cooldown and pending capture latch. |
| KF-06 | Expose reason codes; stale frame guard; reset on reopen. |
| KF-07 | Focused offline tests PASS; replay/Gemini 2 runtime evaluation **pending**. |
| KF-08 | No modifications to camera lifecycle, native, RAW, Qt or storage. |

**Decision:** HS-01.2 is `CODE_READY / OFFLINE_TESTED`; the current checkpoint is NOT an automatic RAW capture feature. HS-01.3 owns integration, revalidation, persistence and Windows replay acceptance.
