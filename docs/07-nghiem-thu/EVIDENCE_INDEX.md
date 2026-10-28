# Evidence Index — nơi tra cứu chứng cứ và quy tắc bổ sung receipt

> `owner: ACCEPTANCE_OWNER` · `as_of_commit: 81da5d2050324b1dc4a65ffbca9a38ed1ebba10a` · `verified_at: 2026-10-28`  
> `scope: index chứng cứ, không thay log gốc hay phát hành PASS` · `source-of-truth: evidence index; file gốc lưu ngoài repo theo operator` · `evidence_level: SOURCE_REFERENCES_ONLY, NEW_WINDOWS_RECEIPT_NOT_TESTED`

## 1. Phân loại evidence tránh nhầm PASS

`GIT_VERIFIED`: SHA/file/PR đã đối chiếu, chỉ chứng minh thay đổi code/tài liệu. `OPERATOR_REPORTED`: log/đường dẫn do người vận hành báo, không phải PDF/JSON file gốc đã tải và kiểm độc lập. `AUTOMATED_RECEIPT`: JUnit/CTest/JSON có thực, gắn commit/environment/exit; phải kiểm schema/kết quả. `PHYSICAL_MANUAL`: ảnh/checklist/phương pháp đo trên màn hình/thiết bị thật và reviewer. `WAIVER`: quyết định có phạm vi, ngày, người duyệt và residual risk; không đồng nghĩa `PASS`.

## 2. Mục lục hiện có (không invent receipt)

| evidence_id | loại | đường nguồn/locator | bao phủ | giới hạn |
|---|---|---|---|---|
| `E-GD0-PRE06` | `OPERATOR_REPORTED` + Git PR | [PRE-06](../99-lich-su/ARCHIVE/GD0/PRE/PRE_06_GD0_ACCEPTANCE.md), PR #3 merge `8bf33591389dcdff82f0fbd5bf5932a22547c984` | RAW/C++/SQLite/one-shot report | File receipt raw Windows không có trong repository tại lần DOC-04 |
| `E-GD1-R6` | `OPERATOR_REPORTED` | [R6 status](records/GD1_R6_ACCEPTANCE_STATUS.md), `_setup/ScanToPath_R6_Auto_Acceptance/evidence/R6_20261027T150605Z_19408` | 14/14 automated, 618/3, CTest2/2 | Locator trên Windows, không truy cập/verify tại DOC-04; tổng thể PENDING |
| `E-GD1-08064` | `HISTORICAL_MANUAL_PARTIAL` | [08.06.4](../99-lich-su/ARCHIVE/GD1/08/08_06_4_WINDOWS_HMI_ACCEPTANCE.md) | Session A/ảnh một số ca và normal close | Không chứng minh close-while-busy, đầy đủ HMI hoặc physical latency |
| `E-GD1-08065` | `WAIVER_HISTORICAL` | [08.06.5](../99-lich-su/ARCHIVE/GD1/08/08_06_5_DEFECT_DISPOSITION_AND_HMI_WAIVER.md) | TC11/TC12 waived by operator tại thời điểm riêng | Không tự waive `08.06.6`, không phải HMI PASS |
| `E-R8-5-GIT` | `GIT_VERIFIED` | Commit `493a24d2ab62cd34e5968cbcb60d5f9857c3c4b8`, [R8.5](../99-lich-su/STANDARDIZATION/R8_5_KIEM_KE_VA_NGHIEM_THU.md) | Có audit/unified runner | Không có receipt Full của DOC-04 ở đây |
| `E-DOC03A` | `GIT_VERIFIED` | Commit `0557c0d4fed9a3df3b180fc9872c6d3293b5f0d5`, [handover](../standardization/DOC03A_TRUY_VET_VA_BAN_GIAO.md) | Có docs/architecture | Windows operator receipt chưa được đối chiếu trong phiên này |
| `E-DOC03B` | `GIT_VERIFIED` | Commit `a847faebe54050cd6f8bc42cc882b3927ddabfe2`, [handover](../standardization/DOC03B_TRUY_VET_VA_BAN_GIAO.md) | Có five-module handbooks | Không tự suy FULL PASS từ Git |
| `E-DOC03C` | `GIT_VERIFIED` | Commit `81da5d2050324b1dc4a65ffbca9a38ed1ebba10a`, [handover](../standardization/DOC03C_TRUY_VET_VA_BAN_GIAO.md) | Có developer handbooks | Không tự suy reviewer/HMI từ commit |
| `E-DOC04` | `NOT_TESTED` | Pack DOC-04 ngoài repository, receipt **chưa tạo** | Nội dung quản trị/stage/acceptance | Chỉ thêm nguồn sau Windows verify/commit, không đặt URL giả |
| `E-GD1-08066` | `OPERATOR_ACCEPTED_WITH_EXPLICIT_WAIVERS` | [Biên bản đóng GĐ1](GD1_ACCEPTANCE.md#7-quyết-định-đóng-gđ1-ngày-28102026); operator Windows `_setup/GD1_08_06_6/` | HMI DPI/reopen: operator PASS; NT-02 fail-fast Event 1000 PASS; Full 10/10 operator-reported | NT-01 BUSY, GPU/VRAM measured, input-to-present latency: WAIVED_NOT_MEASURED; external evidence chưa được connector đọc độc lập |

**Vị trí evidence sau Full:** script `scripts/verify.ps1 -Profile Full` ghi `SUMMARY.json` trong thư mục run ở `_setup/ScanToPath_R8_Verification/evidence/R84_<timestamp>_<pid>` hoặc `-EvidenceDir` chỉ định **ngoài repository**. Không đưa RAW, SQLite thật, `.pyd`, DLL SDK, ảnh riêng tư hay log có secrets vào Git.

## 3. Schema khi đăng ký receipt mới

| Field | Yêu cầu |
|---|---|
| `evidence_id` | ID ổn định, không tái sử dụng |
| `gate_id` | Đúng mã gate ở GD0/GD1 acceptance |
| `source_sha` | HEAD ở lúc chạy, `git status`/working tree rõ |
| `executed_at` | Timestamp kèm timezone |
| `environment` | Windows/Python/CMake/Qt/driver/GPU/camera tùy gate |
| `method` | Command/fixture/đo màn hình, ngưỡng đặt trước |
| `result` | `PASS`, `FAIL`, `SKIP`, `NOT_TESTED`, `WAIVED` theo đúng phép thử |
| `artifact_locator` | Đường dẫn thật hoặc permalink có thể truy lại; không tự sáng tạo |
| `reviewer_or_operator` | Danh tính người thực hiện/duyệt có nguồn, không ghi placeholder thành chữ ký |
| `limitation` | Phạm vi điều không được suy, residual risk/waiver nếu có |

## 4. Workflow kiểm tra và đối chiếu chéo

Mở receipt và so exit code/`SUMMARY.json` + JUnit + CTest, xác thực test case count, skip đúng node ID, các bước native `NOT_TESTED` nếu không bật. Khi có sign-off độc lập, liên kết evidence ID từ [GD1 acceptance](GD1_ACCEPTANCE.md), cập nhật cột verification tại [State Ledger](../05-quan-ly/TRANG_THAI_DU_AN.md) và quyết định task tại [Task Register](../05-quan-ly/TASK_REGISTER.md). Đây là các hệ thống khác nhau: **evidence là chứng cứ, status là trạng thái, task là hành động cần làm**.

## 5. Giới hạn đã biết

Index chưa có đường dẫn một receipt Windows đã được kiểm độc lập cho DOC-04 hoặc final 08.06.6. Đường `_setup` chỉ là locator do người vận hành báo, không có nghĩa file đó đã được mở tại môi trường biên tập. Không tự khẳng định `PASS_REVIEWED` từ metadata tồn tại.

## 6. Cập nhật mới nhất — 08.06.6 đóng GĐ1

`GD1_08_06_6_FINAL_CLOSURE_20261028`: [quyết định đóng tại hồ sơ nghiệm thu](GD1_ACCEPTANCE.md#7-quyết-định-đóng-gđ1-ngày-28102026) dựa trên operator reports/Windows Event Log. Evidence tự động gốc ngoài repository, không có lời xác nhận GitHub CI mới. 3 gate được miễn được ghi `WAIVED_BY_OPERATOR`, không chuyển thành measured PASS.
