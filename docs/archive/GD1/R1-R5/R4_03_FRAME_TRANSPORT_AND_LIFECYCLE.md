# R4.3 - Frame transport and lifecycle prototype

**Baseline:** `feat/gd1-desktop-ui@3110dca0a0b14e7bb88b7dca48ef4fc4b5a3ec6c` (combined R4.1+R4.2).  **Scope:** strict frame acknowledgement and non-Qt, bounded camera scheduler; no production viewer or Qt integration. No schema, RAW, acquisition, mesh/OBJ implementation, sensor or native C++ modification.

## Contracts

- R4.1 `ResidentRenderClient` and `PersistentScene` are extended **compatibly**. Default `hello` remains legacy and all seven R4.1 tests continue to pass. `hello(frame_mode="ack")` negotiates strict shared-frame lifetime **before a scene is opened**.
- In ACK mode, the host publishes one RGB24 frame via its existing two shared-memory slots, then records the tuple `(scene_revision, frame_revision, slot)`. `camera` and `set_camera` are refused with `FRAME_NOT_ACKED` until the parent copies all bytes and sends matching `ack_frame`; stale or mismatched acknowledgements are refused. Closing or replacing a scene invalidates the previous descriptor. SHM is allocated/unlinked by the parent, with only one worker owning the child.
- `set_camera(state)` accepts only the existing immutable `CameraView` schema, not arbitrary transforms. All frames still represent uncalibrated display camera views: `units` and `coordinate_frame` remain `unknown`. Rendering still uses VTK in a child only.
- `CoalescingRenderSession` has **one I/O worker**, a bounded 8-command control queue and a single cumulative `CameraView` target. Rapid mouse-intent updates change the target without allocating one queued IPC message per event. The worker sends the newest absolute camera, copies an immutable RGB frame, ACKs the producer and publishes one latest-wins snapshot. Intermediate frame snapshots may be dropped; final camera intent must be rendered. No GUI-thread blocking calls are added to the production application.
- The scene controls return `concurrent.futures.Future` objects; `next_frame()` returns immutable `FrameSnapshot`. Timeout / process exit fails closed and requires a new session rather than silently announcing recovery. `stop()` terminates a stalled child after a bounded cooperative grace. A new session instance is required for a restart.

## Scope boundary / deferred

- This is a **standalone renderer contract**, not a Qt compositor or benchmark guarantee. It does not implement production input handling, native hardware GPU benchmarking, event-loop polling or mouse gestures. R4.4 measures latency/FPS at 1k/100k/1M, RAM and native-close stress. R5 integrates any approved renderer.
- R4.1 only accepts vertex-only PLY; mesh PLY/OBJ remains R5.1. Input integrity is validated/hashed once on scene load, not per camera command; no guarantees against every possible filesystem TOCTOU race on Windows. No SHA pinning across external file mutations while a scene is resident; reload is explicit.
- ACK protects shared buffer reuse only while the parent **copies the entire RGB frame before ACK**. The snapshots use copied bytes (not zero-copy GPU sharing). R4.4 will quantify overhead and thread scheduling on Windows; no 60 FPS claim.
- A synthetic child kill demonstrates that the parent is not killed and cleans resources; it does **not** certify recovery from every OpenGL/C++ native crash or GPU driver issue. AR-03 remains open until real close-while-busy Windows stress is reviewed.

## Acceptance and traceability

| ID | Contract / evidence | Gate |
|---|---|---|
| R43-01 | Legacy R4.1 protocol and 7 tests unchanged | PASS required |
| R43-02 | ACK required before second frame, reject stale/invalid ACK | PASS required |
| R43-03 | Absolute `CameraView` and latest-wins coalescing retain final input revision | PASS required |
| R43-04 | Single PID/scene load; valid RGB snapshots, bounded queues | PASS required |
| R43-05 | Close/reopen invalidates stale frames; terminate/cleanup after child exit | PASS required |
| R43-06 | Architecture Guard, 07.12 Quality, full Python Qt suite, CTest | PASS required |
| R43-07 | Windows proof JSON, real process cleanup, operator review | PASS required |

All Windows evidence lives outside the repository in `_setup/ScanToPath_GD1_R4_3_Frame_Transport_Lifecycle/evidence/`. Do not backfill a PASS from local Linux smoke. Capture all failed attempts and fixes in that directory's `R4_03_OPERATOR_JOURNAL.md` and later summarize in R7.

## Known prior-failure prevention

- Windows PowerShell `.ps1` is ASCII-only; launcher commands never contain typographic dashes or Unicode quotes. Parser check occurs before publication.
- Source patch checks exact Git SHA, branch, clean repo, old SHA-256, and explicit file scopes. Never touch other modules.
- Verify checks exact payload hashes, new functional regression including R4.1, Architecture/Quality, `git diff --check`, compiled source, full tests and CTest.
- Publish stages only declared files, re-checks cached whitespace, validates evidence and is restartable after an interrupted stage. No automatic merge or force push.
