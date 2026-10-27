# GĐ1 — Nhật ký thực thi, hồi quy và UX rebaseline

**Lập ngày:** 27/10/2026. **Nhánh:** `feat/gd1-desktop-ui`. **R7 baseline:** `ff45ccf87ce770e25eedf6e12df6bb5aaa958734`. Nguồn chủ yếu là docs Git + log PowerShell người vận hành; ghi `HISTORY_INCOMPLETE` khi thiếu từng attempt.

| Mốc | Phạm vi / kết quả | Trạng thái và carry-over |
|---|---|---|
| 06–07 / 07.11–07.12 | Shell, SQLite metadata/RAW workspace, split controllers; hardening static boundaries | Đã có architecture guard và quality gate, không là chứng minh SOLID hoàn hảo |
| 08 đầu tiên | PLY preview và HMI, lỗi in-process VTK/Qt | Rebaseline bắt buộc do crash/lifecycle, 1–3s/gesture theo hồ sơ trước R4 |
| R1–R3.5 | Audit UX, compact shell, Project, Inspector, processing workspace | Nhóm thay đổi HMI; attempts rải trong `_setup`, cần bổ sung evidence nếu audit hoàn chỉnh |
| R4.1–R4.5 | PoC isolated resident vs embedded, shared frame/ACK, benchmark; ADR B conditional | Native crash C++/GPU real/display latency chưa được chứng minh đầy đủ |
| R5.1 | Typed Scene geometry PLY point/faces + OBJ | Không có camera scan→mesh tự động |
| R5.2 | Qt live viewer, source swap / retry / PNG fallback | Inc R5.2 shell 511 > 500 → regression repair; HMI operator báo tương tác mượt |
| R5.3 attempt A | Picker, tools text; focused 8 PASS/1 FAIL (fixture chưa có frame) | INC-GD1-R5-001: test và UX chưa đạt; không commit |
| R5.3 attempt B | SVG, XY grid, orientation corner, Inspector X/Y/Z; 16 focused PASS; full 617 PASS/1 FAIL/3 SKIP | INC-GD1-R5-002: R5.2 brittle source-string test, sửa compat, không xóa regression |
| R5.3 accepted | Commit `ff45ccf`, UI operator báo OK | Cần R6 HMI/DPI rộng hơn; không coi acceptance cảm quan là HMI 100/125/150 bằng chứng |
| R6 attempt A | All subprocess FAIL do PowerShell tự động `$args`; receipts thiếu theo hệ quả | INC-GD1-R6-RUNNER-001; **không phải thất bại của code ScanToPath** |
| R6 attempt B | Python thực 618 PASS/3 SKIP, CTest thiếu `-C Release`, exit_code reporter blank | INC-GD1-R6-RUNNER-002; kết quả thất bại thuộc harness |
| R6 attempt C | 14/14 automated PASS, 618/3, CTest 2/2, native probe+benchmark PASS, Git sạch | **R6_AUTOMATED_PASS**, tổng thể **PENDING** do các gate khác |
| R7 | Chuẩn hóa comment module, canonical docs, history, docs gate; không thay đổi runtime | PENDING cho đến Windows verify + commit |

**Log không nhét vào Git:** `_setup/ScanToPath_R6_Auto_Acceptance/evidence/R6_20261027T150605Z_19408` (operator báo, R7 không sở hữu dữ liệu trong đó). Bằng chứng cũ `_setup` không được tự suy đoán đã đầy đủ.

**Open acceptance:** [R6 matrix](../../acceptance/GD1_R6_ACCEPTANCE_STATUS.md). **Sự cố:** [register](INCIDENT_REGISTER.md). **Tài liệu nền:** [R4.5](../../gd1/ux_rebaseline/R4_05_R5_HANDOVER_GATES.md), [R5.3](../../gd1/ux_rebaseline/R5_03_INTERACTION_INSPECTOR_UX.md).
