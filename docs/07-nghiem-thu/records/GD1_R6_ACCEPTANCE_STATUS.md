# GĐ1 / R6 — Snapshot nguồn kiểm thử tự động và phạm vi còn mở

> `owner: ACCEPTANCE_OWNER` · `as_of_commit: 81da5d2050324b1dc4a65ffbca9a38ed1ebba10a` · `verified_at: 2026-10-28`  
> `scope: chỉ mục snapshot R6, không là một lần test mới và không thay thế receipt gốc` · `source-of-truth: biên bản R6 tại docs/acceptance giữ bất biến tới DOC-05` · `evidence_level: HISTORICAL_OPERATOR_REPORTED`

## 1. R6 được báo cáo gì?

Hồ sơ [GD1_R6_ACCEPTANCE_STATUS gốc](../../acceptance/GD1_R6_ACCEPTANCE_STATUS.md) ngày **27/10/2026**, branch `feat/gd1-desktop-ui`, trước R7 tại `ff45ccf87ce770e25eedf6e12df6bb5aaa958734`, ghi operator log R6: 14/14 automated gates `PASS`, full pytest **618 passed / 3 skipped**, JUnit 621/0 fail, CTest **2/2**, Render Host geometry/transport/native/benchmark reported PASS. Đây là bằng chứng **OPERATOR_REPORTED**, không phải lần chạy mới của DOC-04.

Ba symlink SKIP do Windows privilege được cho phép theo đúng node ID ở R8.3; chúng **không** chứng nhận các code path từ chối symlink đã chạy. Benchmark 1K/100K/1M points nói render-completed, không nói FPS thực, VRAM hoặc input-to-physical-present.

## 2. Các phép thử R6 không chứng minh

- `HMI_DPI_100_125_150`: **NOT_TESTED** theo bảng R6 final.
- `HMI_REOPEN_CLOSE_REAL`: **PARTIAL_EVIDENCE**; session A và các phép benchmark không thay toàn bộ UI.
- `CPP_NATIVE_BUSY_CLOSE`: **NOT_TESTED** vì chưa có trace C++ busy ngay lúc close.
- `CPP_NATIVE_FAULT_ISOLATION`: **NOT_TESTED**; kill process không tương đương C++ fault.
- `GPU_VRAM_MEASURED`: **PARTIAL_EVIDENCE** RAM; chưa được coi là VRAM đo.
- `INPUT_TO_PHYSICAL_PRESENT_LATENCY`: **NOT_TESTED**; render throughput không đo present.

Quyết định snapshot **`R6_AUTOMATED_PASS / R6_OVERALL_PENDING`** vẫn có giá trị diễn giải. 08.06.5 waiver lịch sử chỉ phạm vi riêng, không chốt 08.06.6.

## 3. Tiếp tục nghiệm thu tại đâu?

Dùng [GD1 acceptance hiện hành](../GD1_ACCEPTANCE.md) làm ma trận gate 08.06.6, [Evidence Index](../EVIDENCE_INDEX.md) để đăng ký receipt mới và [State Ledger](../../05-quan-ly/TRANG_THAI_DU_AN.md) để tra trạng thái hiện hành. **Không đưa log mới vào đây để giả làm log R6 gốc.** Nếu thay đổi đường dẫn tới R6 snapshot, DOC-05 kiểm incoming links/gates R7.

## 4. Giới hạn đã biết

DOC-04 không truy cập được thư mục R6 operator `_setup/ScanToPath_R6_Auto_Acceptance/evidence/R6_20261027T150605Z_19408`, và không chạy Windows HMI/native. Văn bản này chỉ tái lập chính xác mức kết luận của hồ sơ R6 đã có.
