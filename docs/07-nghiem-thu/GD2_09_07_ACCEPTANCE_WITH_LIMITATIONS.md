# GD2-09.07 — Acceptance with known limitations

> Date: 2026-10-29. Branch: `feat/gd2-mvpb-20261104`.
> Operator accepted proceeding with the observed result. This is a
> scoped acceptance, **not** certification of the native SDK or of
> general-purpose object detection.

## Verified evidence

| Scope | Evidence | Interpretation |
|---|---|---|
| 09.07.1 | 46 unit PASS; 143 Capture Unit regression PASS | Algorithm contract on synthetic fixtures |
| 09.07.2 | Operator screenshots of Gemini 2 Live RGB/Depth, auto bbox and manually drawn ROI | UI works in the observed scenes; not a metric accuracy certificate |
| 09.07.3 | Hardware probe 2/2 normal start/stop/reopen, camera/analysis worker reaped | Normal lifecycle passed |
| P0 isolation | Disconnect report previously showed `0xC0000374` in `native_camera.close`; after process isolation, unplug still crashed camera *child* in `process_camera._child_main`, while GUI remained alive | Parent-process containment observed, native root cause unresolved |
| Commit gate | Capture regression and architecture checked immediately before commit | Results in operator terminal are authoritative |

Operator-local hardware receipt (not committed):
`E:\1_BigProject\scantopath\_setup\evidence\gd2-09-07-3\hardware_20261029-202511.json`.
Screenshots and terminal log remain operator-local; do not commit private camera images.

## Known limitations / debt

1. Auto bbox may select a tabletop or larger near-field surface instead
   of a smaller target in multi-object/cluttered environments. The ROI
   manual fallback is required. No claim of general object identification.
2. The OrbbecSDK/native process still incurs Windows heap corruption
   `0xC0000374` when USB is unplugged while streaming. Process isolation
   prevented the observed crash from killing the GUI, **not** the native crash.
3. Visible GUI error-state semantics and recovery/retry after physical
   unplug/replug have not been fully verified by this operator report.
4. The Manual ROI label may retain auto tracking/score text; confidence
   is heuristic and uncalibrated. Do not interpret it as a probability.
5. No RAW Capture/SQLite write was performed by these checks.

## Decision and boundary

Status: **ACCEPTED_WITH_LIMITATIONS** per explicit operator acceptance.
Proceed to 09.08 with Manual ROI available. Do not promote small-object
bbox accuracy, native unplug safety, full reconnect behavior, or any
G2-09 final session gate to PASS based on this record alone.
A future hardening task must investigate the OrbbecSDK stop/disconnect
heap corruption independently from the already implemented process isolation.
