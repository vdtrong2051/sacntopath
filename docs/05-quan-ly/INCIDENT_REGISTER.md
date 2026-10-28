# Incident Register — sổ theo dõi sự cố và rủi ro còn mở

> `owner: PROJECT_COORDINATOR` · `as_of_commit: 81da5d2050324b1dc4a65ffbca9a38ed1ebba10a` · `verified_at: 2026-10-28`  
> `scope: sự cố GĐ1 và nguyên tắc mở sự cố mới` · `source-of-truth: sổ incident hiện hành; nguồn chi tiết lịch sử giữ nguyên` · `evidence_level: GIT_REVIEWED + OPERATOR_REPORTED; NOT_NEW_RUNTIME_TEST`

## 1. Phân biệt ba thứ không được gộp

**Incident** là hiện tượng đã xảy ra có attempt và nguồn; **risk** là khả năng/điều kiện chưa thử; **test harness defect** là lỗi cách chạy/diễn giải phép thử, không tự động đồng nghĩa lỗi application. Không tự tạo incident cho native crash hay GPU fail nếu chưa xảy ra. `NOT_TESTED` khác `FAIL`; `WAIVED` khác `PASS`.

## 2. Các incident đã có nguồn (giữ nguyên ID)

| incident_id | Triệu chứng / phân loại | Nguồn và điều đã sửa | remaining_risk / trạng thái |
|---|---|---|---|
| `INC-GD1-07-ARCH` | Quoting PowerShell, Qt QObject/import, ranh giới dependency | [Register lịch sử](INCIDENT_REGISTER.md), [07.12](../99-lich-su/ARCHIVE/GD1/07/07_12_CONSOLIDATION_RISK_REGISTER.md); Architecture/Quality guard | `MITIGATED_WITH_TESTS`; chưa chứng minh mọi race/thread lifecycle |
| `INC-GD1-08-VTK` | Qt/VTK cùng process có sự cố | [R4.5](../99-lich-su/ARCHIVE/GD1/R1-R5/R4_05_RENDERER_ARCHITECTURE_DECISION.md); chọn host riêng | `PARTIAL_EVIDENCE`; crash C++ thật chưa chứng minh |
| `INC-GD1-R5-003` | Qt shell quá lớn/ảnh Qt API warning | [Register lịch sử](INCIDENT_REGISTER.md); tách bootstrap | `MITIGATED`; cần review khi thêm workspace |
| `INC-GD1-R5-001` | Fixture chưa có frame, tool từ chối picking | [Nhật ký](../99-lich-su/JOURNALS/GD1_EXECUTION_JOURNAL.md); sửa test fixture, giữ frame guard | `MITIGATED`; HMI thật chưa khép |
| `INC-GD1-R5-002` | Test R5.2 dò constructor string cũ | [Register lịch sử](INCIDENT_REGISTER.md); alias tương thích | `MITIGATED`; cần refactor test source-coupled khi có phạm vi riêng |
| `INC-GD1-R6-RUNNER-001` | `$args` trùng biến PowerShell khiến subprocess không chạy | [R6](../07-nghiem-thu/records/GD1_R6_ACCEPTANCE_STATUS.md); rename param | `RESOLVED_IN_HARNESS`; không gán lỗi application |
| `INC-GD1-R6-RUNNER-002` | Runner hiểu sai exit code, thiếu CTest `-C Release` | [R6](../07-nghiem-thu/records/GD1_R6_ACCEPTANCE_STATUS.md); kiểm tra exit trực tiếp | `RESOLVED_IN_HARNESS`; 14/14 là nguồn operator |

Không tự thêm incident R8 chỉ vì bảng DOC-02 đặt nghi vấn có thể có lỗi runner R8.4. Hiện tại **CHƯA CÓ attempt/receipt trong các nguồn Git đã đọc** đủ để cấp incident R8 độc lập.

## 3. Risk register gắn với 08.06.6 (không phải incident đã xảy ra)

| risk_id | Điều chưa thử | Quyết định/đầu ra cần |
|---|---|---|
| `RISK-HMI-DPI` | 100/125/150% ảnh hưởng bố cục/focus | HMI checklist từng DPI, ảnh/log, kết luận độc lập |
| `RISK-NATIVE-BUSY` | close khi native C++ thực sự đang bận | Trace worker busy→close→PID/cleanup, không suy từ 08.06.4 session A |
| `RISK-NATIVE-FAULT` | fault injection C++ thật | sandbox subprocess, xác minh parent Qt sống/cancel/restart |
| `RISK-GPU-PRESENT` | GPU/VRAM, input-to-physical-present | công cụ đo, cấu hình driver/monitor, đơn vị, receipt |
| `RISK-HW-BASELINE` | cấu hình cơ khí/camera hiện hành chưa có quyết định trong Git | ADR vật lý ký, version, chứng cứ ảnh/diagram |

Các rủi ro này nối tới [GD1 final acceptance](../07-nghiem-thu/GD1_ACCEPTANCE.md) và [Task Register](TASK_REGISTER.md). Waiver cũ [08.06.5](../99-lich-su/ARCHIVE/GD1/08/08_06_5_DEFECT_DISPOSITION_AND_HMI_WAIVER.md) chỉ áp dụng phạm vi đã ghi và để lại residual risk.

## 4. Hợp đồng thêm/sửa incident

Mỗi bản ghi mới phải có ID cố định; thời điểm; `symptom`; `source/attempt`; môi trường; phân loại; `root_cause` với mức chắc chắn `CONFIRMED|UNCONFIRMED`; `fix_or_mitigation`; `regression`; `remaining_risk`; owner và ngày duyệt. Nếu sai kết luận trong hồ sơ cũ, ghi **ĐÍNH CHÍNH** có link/commit mới, không xóa attempt FAIL. Khi chỉ có giả thuyết, ghi risk thay vì phát minh incident.

## 5. Giới hạn đã biết

DOC-04 không mở log RAW, debug camera, chạy native fault hay đọc evidence ngoài Git. Sổ này nêu các nguồn lịch sử đã được lưu và phần chưa được chứng minh; việc di chuyển lịch sử sang `99-lich-su/` thuộc DOC-05.
