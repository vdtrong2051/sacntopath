# ScanToPath — GĐ1 08.06.3 / Performance & Stress Benchmark

**Baseline:** `feat/gd1-desktop-ui @ 2cca7dcd26d7d9bf7a1083bfa7097cb288ade5e1` (08.06.2 confirmed). **Purpose:** measure native Viewer *without changing its architecture or runtime*. Architecture remains offline-first Modular Monolith + MVC per feature + SOLID, with VTK in isolated child processes. No VTK/PySide6 install or upgrade; no access to Gemini 2, RAW, SQLite, C++ build outputs or cloud services.

## Protocol

- Test datasets synthesized outside the repository, never called real scans or calibrated geometry. Deterministic point cloud generated as PLY 1.0: 1k ASCII RGB, 10k/100k/300k/1M binary little-endian XYZ. Each file is SHA-256 fingerprinted; import and navigation metadata must match source fingerprint/count and preserve `units=unknown`, `coordinate_frame=unknown`.
- For **each size**, run the unmodified production child CLI entrypoints (`render_ply`, `render_navigation`, `pick_point`) with one child process per operation. Import, 33° orbit with zoom/pan/axes state, then center-screen picking; each operation records exit/marker, wall time including interpreter & VTK initialization, child peak working set and sampled parent+child RSS. The center pick may be a miss; result must be valid and source-matched. Only small 1k/10k groups repeat twice; larger groups run once, so report **observations**, not population P95 claims. The application does not provide 60 FPS live interaction.
- On Windows, memory uses `GetProcessMemoryInfo` WorkingSetSize and PeakWorkingSetSize; on Linux `/proc/*/status` RSS/HWM where available. GPU memory, desktop Qt RSS, whole system load, and thread-level race conditions **are not measured**. Additional probes reject invalid PLY and stale source hashes, kill and reap a busy native process, and verify source bytes remain unchanged. Child-process reaping is verified after each step; a reaped child alone is **not** proof that Qt successfully manages every close/cancel race.
- Child process deadline: 150 seconds by default, configurable 30–600 seconds. Any timeout, missing marker, invalid PNG/JSON/provenance, missing memory reading, or nonzero child exit is a **measurement failure**, not a numerical zero. Log, CSV and intermediate summary remain for diagnosis.
- A **smoke profile** covers only 1k and 10k; it is not GĐ1 acceptance. Full profile covers all five datasets (21 operations = 2×3×2 + 3×3) and requires a Windows test run on the target machine. No fixture or report overwrites; each verify creates a new run ID.
- Summary status `MEASURED_PENDING_PERFORMANCE_REVIEW` means the benchmark successfully gathered all full-profile data, **not** that performance has been approved. Reviewing latency/RAM and deciding a target-machine usability threshold is mandatory before closing 08.06.3. No invented limits are imposed on small/large scenarios; abnormal slowness, disk pressure or driver errors must be identified and recorded, not masked.

## Evidence and acceptance gate

`verify.ps1` enforces exact Git HEAD and payload integrity; verifies Python `.venv` has already-installed VTK, runs harness self-test, architecture guard, 07.12 quality guard, targeted Viewer Python tests, native full benchmark, validates 21 measurement rows, and generates a signed-by-SHA receipt in `_setup/<package>/acceptance/` outside Git. Reports: `08_06_3_RESULTS.csv`, `08_06_3_RESULTS.json`, `08_06_3_SUMMARY.json`, `08_06_3_RECEIPT.json`, and logs; machine-specific paths/credentials are not stored in the source repository.

`publish.ps1` commits **only this protocol document**, after operator has inspected metrics, confirmed target hardware and acknowledged that HMI race/stress testing is still pending 08.06.4. It must never merge `main` or misreport GĐ1 complete. The actual benchmark JSON/CSV remain local; final measured findings should be summarized in GĐ1 final acceptance (08.06.6).

## Interpreting results / remediation

- Group by point count, operation, elapsed milliseconds and peak child/combined memory. Compare 1k→1M growth, pay particular attention to full VTK startup per gesture and SHA re-hashing. Per-worker memory reuse is not applicable: each subprocess exits after one operation.
- Monitor for outstanding processes, excessive response delay, RAM pressure and disk errors. If any operation FAILs, **do not publish or report performance PASS**: save logs, classify the defect in 08.06.5.
- 08.06.4 must still test actual Qt HMI with repeated switching, heavy PLY, active cancellation/close, real driver environment and resource monitor. Static/offscreen tests and native CLI measurements cannot prove visual smoothness or event-loop responsiveness.
