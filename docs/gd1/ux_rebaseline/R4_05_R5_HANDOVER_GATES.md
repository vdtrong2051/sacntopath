# R4.5 to R5 handover - Integration guardrails

**Engineering architecture:** candidate B - resident isolated VTK host. **Not a production acceptance**. Keep A in a disposable Qt comparator child; keep the existing compatibility preview while production Viewer remains unchanged.

| Stage | Implementation/verification requirement | Exit proof |
|---|---|---|
| R5.1 | Scene source DTO, PLY point/faces + OBJ, source SHA, native geometry-kind, bounds and counts, no invented units | Points + mesh + OBJ fixtures, valid/invalid source, hash stability |
| R5.2 | Qt compositor consuming copy/ACK shared RGB frames, latest-only revisions; mouseMove live orbit, pan, zoom; source load once | Windows active-drag video/HMI, latency proxy clearly separated from true display present |
| R5.2 | Lifecycle in native Windows: open, busy-close, source switch, controlled host loss, retry, last-frame staleness, child resource cleanup | Test trace proving busy execution at shutdown; no orphan child, bounded timeout |
| R5.2 | GPU/CPU/RAM and GPU driver profile on real hardware at 1k, 100k, 1M; include GUI and render host processes | Reproducible measurement, RAM/private/CPU interpretation, no fictional VRAM |
| R5.3 | Picker correct point/cell XYZ and Inspector provenance; no fictitious layers, units or source identity | HMI and typed inspector/selection contracts |
| R6 | Full Qt regression, CTest, native stability, high DPI 100/125/150%, reopen/close, operator evidence | Acceptance report with PASS, FAIL, NOT_TESTED distinguished |

## IPC and compositing invariants

- Render-host native VTK is never imported inside the Qt UI process in candidate B.
- Frame is immutable when published to UI; ACK only after copying out of shared memory.
- `scene_revision`, `frame_revision`, and `input_revision` are checked together. New scene drops old frames, selection and metadata.
- Camera updates are coalesced for responsiveness, but the final input revision must eventually be rendered unless a later scene close cancels it.
- Do not block Qt event loop for child process startup, PLY read, render or shutdown.
- A forced native termination must not corrupt the application state or existing SQLite/RAW stores.
- Do not silently downgrade from mesh to vertices when a PLY has polygon faces.

## Recorded evidence and known limitations

R4.4 contains A/B completed-render estimates but not screen presentation time, GPU/VRAM, crash fault injection, or truly busy close. R4.5 observes Windows peak working set and private bytes for the host and worker, rather than trusting the earlier anomalous 4.4 MB figure. Both figures should be reviewed by the operator with OS/GPU context. No renderer performance target should be claimed as proven across machines or driver versions.

R4.5 completion therefore only freezes this **decision and the R5 integration contract**. GĐ1 final freeze follows R5, R6, R7 and R8 in the approved sequence. The R4.5 evidence stored under `_setup` remains separate from committed source and should be logged into GD1/master execution history during R7.
