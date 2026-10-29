# GD2-09 — Checkpoint & Evidence Ledger

> Trạng thái checkpoint: 09.01–09.05 đã nghiệm thu; 09.06–09.09 chưa triển khai. Các gate toàn phiên G2-09-A/B/C vẫn `NOT_TESTED`.

| Step | Trạng thái | Commit SHA | Small test + kết quả | Những file đã review | Blocker/evidence |
|---|---|---|---|---|---|
| 09.00 | SOURCE_AUDIT_COMPLETE / DESIGN_LOCKED | Documentation only | Windows UI **NOT_RUN** | `GD2_09_00_UI_AUDIT_LOCK.md` | Verify on actual Windows when UI integrated |
| 09.01 | SMALL_TEST_PASS | See Git checkpoint 09.01 | 48 passed; architecture 0 violations | contracts.py, ports.py, models.py, test_gd2_09_01_contracts.py, module skeleton | Windows; G2-09-A/B/C NOT_TESTED |
| 09.02 | ACCEPTED / SMALL_TEST_PASS | See Git checkpoint 09.02 | 35 passed; related regression 86 passed, 1 skipped (Windows symlink privilege); architecture 0 violations | replay.py, raw_reader.py, unit + integration tests | Synthetic RAW/SQLite; real Gemini 2 and G2-09-A/B/C NOT_TESTED |
| 09.03 | ACCEPTED / SMALL_TEST_PASS | See Git checkpoint 09.03 | Unit 13 passed; integration 3 passed; related regression 99 passed + 1 skipped (Windows symlink privilege); project regression PASS; architecture 0 violations | decoding.py, jpeg_codec.py, unit/integration tests, pyproject.toml | Pillow 12.3.0; synthetic RGB-D; Gemini 2 real device NOT_TESTED |
| 09.04 | ACCEPTED / AUTOMATED_PASS / WINDOWS_VISUAL_PASS | This checkpoint commit | 20 Qt preview/integration passed; 57 GD1 UI regression passed; 99 Capture regression passed; architecture 0 violations | preview_widget.py, preview_controller.py, replay_worker.py, main_window.py, 2 Qt test files | Windows visual PASS 2026-10-29; synthetic RAW v2 Capture c1; RGB 24x16; Depth 3x2; scale 0.001 m/unit; Gemini 2 live NOT_TESTED |
| 09.05 | ACCEPTED / AUTOMATED_PASS / HARDWARE_PASS | This checkpoint commit | Application, native adapter mock, Qt worker and Capture regression PASS (operator confirmed); architecture PASS; native self-test PASS | application/live_stream.py, infrastructure/native_camera.py, presentation/live_worker.py, 3 test files, scripts/gd2_09_05_live_probe.py | Windows Gemini 2 firmware 1.4.98; one-shot PASS; live 15.22 s / 400 frames / 26.28 FPS PASS; live 60.84 s / 1750 frames / 28.76 FPS PASS; 1920x1080 MJPEG + 1280x800 Y16; owned buffers PASS; no RAW persisted; full 09.06 lifecycle and session gates NOT_TESTED |
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
