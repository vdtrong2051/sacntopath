# GD2-09 — Checkpoint & Evidence Ledger

> Trạng thái sau khi nạp scaffold (chưa chạy test trên Windows): `IMPLEMENTATION_NOT_STARTED`; mọi G2-09 gates `NOT_TESTED`.

| Step | Trạng thái | Commit SHA | Small test + kết quả | Những file đã review | Blocker/evidence |
|---|---|---|---|---|---|
| 09.00 | SOURCE_AUDIT_COMPLETE / DESIGN_LOCKED | Documentation only | Windows UI **NOT_RUN** | `GD2_09_00_UI_AUDIT_LOCK.md` | Verify on actual Windows when UI integrated |
| 09.01 | SMALL_TEST_PASS | See Git checkpoint 09.01 | 48 passed; architecture 0 violations | contracts.py, ports.py, models.py, test_gd2_09_01_contracts.py, module skeleton | Windows; G2-09-A/B/C NOT_TESTED |
| 09.02 | ACCEPTED / SMALL_TEST_PASS | See Git checkpoint 09.02 | 35 passed; related regression 86 passed, 1 skipped (Windows symlink privilege); architecture 0 violations | replay.py, raw_reader.py, unit + integration tests | Synthetic RAW/SQLite; real Gemini 2 and G2-09-A/B/C NOT_TESTED |
| 09.03 | NOT_STARTED | — | NOT_RUN | — | — |
| 09.04 | NOT_STARTED | — | NOT_RUN | — | — |
| 09.05 | NOT_STARTED | — | NOT_RUN | — | — |
| 09.06 | NOT_STARTED | — | NOT_RUN | — | — |
| 09.07 | NOT_STARTED | — | NOT_RUN | — | — |
| 09.08 | NOT_STARTED | — | NOT_RUN | — | — |
| 09.09 | NOT_STARTED | — | NOT_RUN | — | — |

## Session gates (do not pre-fill PASS)

| Gate | Status | Evidence location / operator / git SHA |
|---|---|---|
| G2-09-A | NOT_TESTED | — |
| G2-09-B | NOT_TESTED | — |
| G2-09-C | NOT_TESTED | — |
| ARCH-09 | NOT_TESTED | — |
| DATA-09 | NOT_TESTED | — |
| LIFE-09 | NOT_TESTED | — |
| REG-09 | NOT_TESTED | — |

### Receipt fields

`step`, `date`, `operator`, `git_sha`, `OS`, `Python`, `Qt`, `SDK/firmware`, `test_command`, `test_result`, `manual_video/log`, `RAW hash`, `capture_id`, `next_action`, `reviewer`.

## Rule

Không coi `bootstrap` đã chép file hoặc test contract 09.01 là nghiệm thu các tính năng 09.02–09.09. Khi bước nào fail, sửa trực tiếp trên VS Code và cập nhật ledger bằng trạng thái FAIL/BLOCKED.
