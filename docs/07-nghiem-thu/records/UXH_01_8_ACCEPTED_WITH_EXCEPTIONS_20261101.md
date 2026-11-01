# UXH-01.8 â€” Accepted with exceptions (owner-directed closure)

- **Decision:** ACCEPTED_WITH_EXCEPTIONS_FOR_MERGE on 2026-11-01T05:54:06Z.
- **Repository:** vdtrong2051/sacntopath, branch feat/gd2-uxh-01-hardening, original HEAD 016f0cf06de65a432626bb58ec8868483b30eb04.
- **Authority:** project owner explicitly requested on 2026-11-01 to stop further testing, commit and integrate UXH-01.8 into main, despite Full regression not passing.
- **IMPORTANT:** This waiver is not a successful Full regression, not the strict UXH-01.8 finalizer receipt, and does not establish that all test contracts pass.

## Observed results

- Targeted UXH A01â€“A07: PASS (earlier Windows run).
- R8.5 audit: PASS (158 test files, 43 scripts, 13 review-only candidates).
- R03 smoke: SMOKE_R7C=PASS, SMOKE_ARCH_LAYOUT=PASS.
- Real Gemini 2: H01_ONESHOT=PASS; H02_LIVE_60S=PASS; H03_CYCLES_2=PASS.
- HMI: **operator confirmed OK in conversation**, but no individual M01â€“M09 evidence/receipt was supplied; do **not** claim 9/9 PASS.
- Official R8.4 Full: **TIMEOUT after 480 seconds in PYTEST_FULL**. R7/R8.1/R8.2/R8.3/R8.5/Architecture/Quality completed PASS before timeout; Pytest Full/JUnit/CTest did **not** complete on this run.
- Previous Full diagnostic (before subsequent repairs): 22 failed, 1367 passed, 3 skipped. These results are historical and do not represent a passing post-repair Full run.
- Open P0/P1 status: **not independently reviewed as part of this exception closure**.

## Evidence custody (external to Git)

- R03 60-second FAST_SUMMARY.json SHA256: 018bbe39c24172f04e22e21d2a181223d0045bd7788386f0b53a83b04f708c35.
- Bounded Full FULL_SAFE_SUMMARY.json SHA256: b512af98858548e94ef7dd177a48f40cc34318c26dcafaae1465c2bf259c93d7.
- Operator-side files: E:\1_BigProject\scantopath\_setup\UXH_01_8\evidence\FAST_20261101T053017Z_23220\FAST_SUMMARY.json and E:\1_BigProject\scantopath\_setup\UXH_01_8\evidence\FULL_SAFE_20261101T053634Z_31356\FULL_SAFE_SUMMARY.json (not committed).

## Accepted residual risks and constraints

- A test in Full Pytest may hang or exceed expected runtime; root cause unresolved.
- Integration regressions not exercised by the completed smoke checks may remain.
- This decision waives the **closure process gate only**; it must not weaken runtime fail-closed input checks, remove tests, or imply metric geometry accuracy, reconstruction quality, robot actuation, or safety certification.
- Earlier strict acceptance documents that say LOCK_PENDING or require automated 8/8 remain historical process criteria; **this explicit exception record supersedes them for the decision to merge UXH-01.8 only**, not for claiming comprehensive verification.
- main integration is by a checked, non-force **fast-forward** push after committing the current UXH changes.

**Disposition:** merge source and preserve truthful failing/timeout evidence; future full-suite isolation is a known follow-up, not a blocker imposed on this owner-approved closure.
