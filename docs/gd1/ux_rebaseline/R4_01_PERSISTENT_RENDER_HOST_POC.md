# R4.1 — Persistent isolated VTK Render Host (research PoC)

**Branch/baseline:** `feat/gd1-desktop-ui @ 8c295e0000c734b709f4e99e68d7e8853362f257` (R3.5).
**Decision:** prototype **only**; no production Viewer/HMI changes, no A/B architecture decision, no GĐ1 final signoff.

## 1. Why R4.1 exists

The production 08.x Viewer launches a disposable `QProcess` and creates PNG previews for each gesture. R4.1 builds a separate persistent renderer that demonstrates a single VTK scene/renderer/window, continuous sequences of camera commands and RGB frames without reloading geometry or restarting the process for each command. It is **not** yet a Qt viewport and does **not** prove drag-to-frame FPS.

## 2. Implemented PoC architecture

```text
isolated CLI client (stdlib; test/benchmark only)
  ├─ starts ONE child process [Python -X faulthandler -m ...resident_poc.host]
  ├─ bounded JSON-line command/response, request ID monotonic
  └─ owns two RGB24 shared-memory frame slots
          │
          ▼
resident VTK child process (lazy native initialization)
  ├─ existing inspect_ply(path): size/header/SHA-256 once per OPEN
  ├─ vtkPLYReader + vtkVertexGlyphFilter: POINT-ONLY geometry cached
  ├─ vtkRenderer + vtkRenderWindow: stay resident between commands
  ├─ existing immutable CameraView + configure_scene: orbit/pan/zoom/reset/axes
  ├─ vtkWindowToImageFilter → raw RGB shared-memory frame; never PNG hot path
  └─ frame_revision/scene_revision/open_count, bounded shutdown + cleanup
```

**Message API:** `hello`, `open` (absolute PLY path), `camera` (`orbit|pan|zoom|reset|axes`, numeric `dx`, `dy`), `status`, `close_scene`, `shutdown`. Responses contain request ID, success flag and revision metadata. Maximum line 4096 bytes; request IDs monotonically increase. There is one synchronous request in flight at a time: this bounds the queue in R4.1. The parent copies a completed RGB frame from the announced shared-memory slot. `frame_revision` increments for every freshly rendered frame; initial frame on successful `open` is revision 1.

**Geometry/safety:** Only vertex-only PLY is supported. Any PLY faces are explicitly rejected (`MESH_DEFERRED_R5_1`), never silently converted into points. OBJ is deferred to R5.1. Sources must exist, be absolute, be regular files and pass the preexisting bounded `inspect_ply` validation; SHA-256/size/mtime are verified on open and source stat is rechecked after the native load. PLY is never rewritten. File changes after load require explicit reload; the prototype does **not** re-hash per camera command. Units/frame are `unknown`. No SQLite/RAW access, no camera driver calls, no UI patch.

**Ownership:** Qt is not imported. The client owns the child lifecycle and shared memory; only the child imports VTK. On `close_scene`, geometry is released without killing the render host. On final `shutdown`, the VTK window is finalized. On crash/timeout, parent detects failure or kills the child and unlinks its buffers. No claims about GPU driver crash probability or asynchronous Qt thread safety are made here.

## 3. Intentional limits (next steps)

- The client is synchronous, *must not* run on the Qt GUI thread; does not yet coalesce mouse moves, manage asynchronous cancellation, or protect delayed consumers from overwritten double-buffer slots. R4.3 adds final frame transport/ack/lifecycle semantics.
- No actual mouse/Qt viewport, no screen-space picking, no multi-layer scene, no OBJ/PLY mesh. R5 handles geometry, Viewer UX and picking.
- Image is **bottom-up RGB24** (VTK origin), not a PNG or Qt `QImage`. An eventual compositor must validate frame descriptors and flip rows or use a suitable consumer transform.
- R4.1 demonstrates event-to-render commands, but does not establish FPS or reliable p95 latency at 100k/1M on the operator's Windows GPU. Formal A/B measurements belong to R4.4.
- The existing 08.x Viewer remains the fallback until R4.5 architecture decision and R5 release gates.

## 4. Reproducible Windows operator gate

From `_setup/ScanToPath_GD1_R4_1_Persistent_Render_Host`, run `apply.ps1 -ProjectRoot <repo>` then `verify.ps1 -ProjectRoot <repo> -FullRegression`. Expected focused suite: **7 native/protocol/architecture tests**, not skipped, plus existing Python/Qt regression, Architecture Guard, 07.12 Quality, CTest if the full gate is used. The demo writes a **single** PPM final image, one JSON report and synthetic PLY into `_setup/.../evidence`; it never writes output into the repository or into an existing input PLY.

Manual Windows checks after automated gate: inspect the PPM, verify JSON `open_count=1`, `frame_revision=events+1`, same host PID, source SHA constant; inspect task manager for orphan processes after exit. Run the same demo again (20 cycles are R4.4 formal benchmark, not assumed R4.1 result). Capture OS/GPU/driver/VTK/Python versions, error logs, any fail+fix attempt in `_setup/.../evidence/R4_01_OPERATOR_JOURNAL.md`.

## 5. Acceptance matrix

| Gate | Requirement | Status before user verification |
|---|---|---|
| R41-P01 | VTK child persists for >= 18 camera operations; `open_count==1`; no PNG hot path | Local PoC smoke succeeded on tiny synthetic scene; Windows **PENDING** |
| R41-P02 | Frame bytes nonempty, revisions monotonic, camera updates alter frame | Local PoC smoke succeeded; Windows **PENDING** |
| R41-P03 | Invalid PLY rejected, mesh not misclassified, source hash unchanged | Native automated tests defined; Windows **PENDING** |
| R41-P04 | Close/reopen scene keeps host PID; forced host crash does not crash parent | Native automated tests defined; Windows **PENDING** |
| R41-P05 | No Qt/UI/Storage/RAW/SDK modifications; prior regressions remain green | Requires Windows full gate |
| R41-P06 | No abandoned child/shm; operator logs failure attempts and verdict | Manual Windows evidence **PENDING** |

**R4.1 may be committed only after the Windows gate and operator review.** Do not mark R4, native crash risk AR-03, or GĐ1 acceptance PASS because of a synthetic PoC. R4.2–R4.5 retain independent gates.
