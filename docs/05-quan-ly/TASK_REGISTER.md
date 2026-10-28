# Task Register — một nguồn quản lý công việc ScanToPath

> `owner: PROJECT_COORDINATOR` · `as_of_commit: 81da5d2050324b1dc4a65ffbca9a38ed1ebba10a` · `verified_at: 2026-10-28`  
> `scope: công việc điều phối GĐ0/GĐ1, chuẩn hóa DOC-01→05 và điều kiện mở GĐ2` · `source-of-truth: task ledger duy nhất, không phải nghiệm thu` · `evidence_level: GIT_VERIFIED + HISTORICAL_OPERATOR_REPORTED; CURRENT_WINDOWS_NOT_TESTED`

## 1. Cách đọc và chỉnh sửa

Đây là **sổ task sống** từ DOC-04. Tài liệu khác chỉ dẫn tới ID; không sao chép bảng tiến độ. `DONE` chỉ được xác lập khi thỏa acceptance criteria, có receipt/commit phù hợp **và** người có quyền duyệt. Việc Git đã có commit không tự đồng nghĩa Windows Full hoặc HMI đã qua gate. Vì không có quyền đọc evidence ở ổ Windows trong lượt đối chiếu này, các mốc chuẩn hóa đã commit được ghi `IN_REVIEW`, không tự ghi `DONE` hồi tố.

Các trạng thái hợp lệ: `BACKLOG` (chưa lên lịch), `READY`, `IN_PROGRESS`, `BLOCKED` (nêu blocker), `IN_REVIEW` (đã có deliverable, chờ duyệt), `DONE`, `DEFERRED` (cần lý do), `CANCELLED` (cần lý do). Task là đơn vị giao việc; `PASS`, `FAIL`, `NOT_TESTED` chỉ dùng cho **gate** trong [hồ sơ nghiệm thu](../07-nghiem-thu/GD1_ACCEPTANCE.md). Mỗi lần cập nhật cần `updated_at`, `updated_by`, nguồn, owner và bằng chứng; không tái sử dụng ID cho phạm vi khác.

`updated_by: DOCUMENTATION_EDITOR` chỉ xác nhận người biên soạn snapshot DOC-04, **không phải danh tính người duyệt nghiệm thu**. `owner` là vai trò, chưa gán tên cá nhân. Tất cả mục bên dưới có `updated_at: 2026-10-28`, `updated_by: DOCUMENTATION_EDITOR`; người vận hành phải ghi receipt nếu phê duyệt sau khi chạy trên Windows.

## 2. Sổ nhiệm vụ đang quản lý

| task_id | parent_stage / workstream | title / outcome | owner | priority | status | depends_on | commit_or_pr | evidence_uri / giới hạn |
|---|---|---|---|---|---|---|---|---|
| `GD0-PRE06` | GĐ0 / foundation | Khóa nền RAW v2, SQLite, one-shot và bàn giao GĐ0 | `STAGE_OWNER` | P0 | `IN_REVIEW` | PRE-01..05 | PR #3; merge `8bf33591389dcdff82f0fbd5bf5932a22547c984` | [PRE-06](../archive/GD0/PRE/PRE_06_GD0_ACCEPTANCE.md); operator-reported, chưa recheck evidence tại DOC-04 |
| `GD1-06-07` | GĐ1 / desktop-project | Qt shell + Project Workspace đủ luồng UI/service | `MODULE_OWNER:DESKTOP_UI` | P0 | `IN_REVIEW` | GD0-PRE06 | Git source tại HEAD | [Desktop](../03-modules/DESKTOP_UI.md), [Project](../03-modules/PROJECT_WORKSPACE.md) |
| `GD1-08-R53` | GĐ1 / viewer | Render Host cô lập, PLY/OBJ, picking/Inspector | `MODULE_OWNER:VIEWER_3D` | P0 | `IN_REVIEW` | GD1-06-07 | `ff45ccf87ce770e25eedf6e12df6bb5aaa958734` | [Viewer](../03-modules/VIEWER_3D.md), [R6](../acceptance/GD1_R6_ACCEPTANCE_STATUS.md) |
| `GD1-R6-AUTO` | GĐ1 / verification | Khóa riêng kiểm thử tự động R6 | `ACCEPTANCE_OWNER` | P0 | `IN_REVIEW` | GD1-08-R53 | R5.3 commit + operator log | [R6 historical](../acceptance/GD1_R6_ACCEPTANCE_STATUS.md); 14/14 operator-reported |
| `GD1-R8-QUALITY` | GĐ1 / quality | Củng cố inventory, fixture/SKIP, unified runner, audit | `ENGINEERING_OWNER` | P0 | `IN_REVIEW` | GD1-R6-AUTO | `493a24d2ab62cd34e5968cbcb60d5f9857c3c4b8` | [R8.5](../standardization/R8_5_KIEM_KE_VA_NGHIEM_THU.md); Full Windows receipt mới chưa đối chiếu |
| `DOC-01` | Docs v2 / inventory | Kiểm kê 65 đối tượng và hợp đồng | `DOCUMENTATION_OWNER` | P0 | `IN_REVIEW` | GD1-R8-QUALITY | Mốc nguồn R8.5 | [DOC-02 overview](../standardization/DOC02_KIEN_TRUC_TAI_LIEU.md), người dùng thông báo hoàn tất |
| `DOC-02` | Docs v2 / architecture | Khóa cây tài liệu, mapping 65/trace 43/issues 20 | `DOCUMENTATION_OWNER` | P0 | `IN_REVIEW` | DOC-01 | `7a0df7c5b596ff8750bf91f47310067c53a8b204` | [Spec](../standardization/DOC02_KIEN_TRUC_TAI_LIEU.md) |
| `DOC-03A` | Docs v2 / content | Cổng README, overview và architecture | `DOCUMENTATION_OWNER` | P0 | `IN_REVIEW` | DOC-02 | `0557c0d4fed9a3df3b180fc9872c6d3293b5f0d5` | [Handover](../standardization/DOC03A_TRUY_VET_VA_BAN_GIAO.md) |
| `DOC-03B` | Docs v2 / content | Năm tài liệu module tự chứa | `DOCUMENTATION_OWNER` | P0 | `IN_REVIEW` | DOC-03A | `a847faebe54050cd6f8bc42cc882b3927ddabfe2` | [Handover](../standardization/DOC03B_TRUY_VET_VA_BAN_GIAO.md) |
| `DOC-03C` | Docs v2 / content | Bốn sổ tay kỹ thuật/Windows | `ENGINEERING_OWNER` | P0 | `IN_REVIEW` | DOC-03B | `81da5d2050324b1dc4a65ffbca9a38ed1ebba10a` | [Handover](../standardization/DOC03C_TRUY_VET_VA_BAN_GIAO.md); Windows receipt không hiện diện trong Git |
| `DOC-04` | Docs v2 / management | Task, trạng thái, ADR, GĐ0/1, nghiệm thu và incident | `PROJECT_COORDINATOR` | P0 | `IN_PROGRESS` | DOC-03C | chưa có commit DOC-04 | [Handover DOC-04](../standardization/DOC04_TRUY_VET_VA_BAN_GIAO.md); PACK_PREPARED |
| `DOC-05` | Docs v2 / migration | Điều hướng, archive, redirects và khóa Documentation Baseline v2 | `DOCUMENTATION_OWNER` | P0 | `BACKLOG` | DOC-04 | chưa có | [DOC-02](../standardization/DOC02_KIEN_TRUC_TAI_LIEU.md); không được xóa alias trước kiểm chứng |
| `GD1-08-06-6` | GĐ1 / final acceptance | Chốt bằng chứng HMI/native thực hoặc waiver theo từng gate | `ACCEPTANCE_OWNER` | P0 | `BLOCKED` | GD1-R8-QUALITY | chưa có quyết định final có nguồn | [GD1 acceptance](../07-nghiem-thu/GD1_ACCEPTANCE.md); **blocker:** thiếu receipt và quyết định manual/fault/GPU/present |
| `HW-CURRENT-BASELINE` | GĐ1→GĐ2 / hardware | Chốt cấu hình vật lý hiện hành bằng quyết định có nguồn | `ARCHITECTURE_OWNER` | P0 | `BLOCKED` | external evidence | chưa có ADR/baseline hợp lệ trong Git | [Decision index](QUYET_DINH_KY_THUAT.md); **blocker:** khác biệt lịch sử handheld/rig chưa được chứng thực bằng hồ sơ mới |
| `GD2-09` | GĐ2 / replay | RAW replay có provenance, không phá raw bytes | `STAGE_OWNER` | P1 | `BACKLOG` | GD1-08-06-6; HW-CURRENT-BASELINE nếu tích hợp cơ cấu | chưa có | [Roadmap](../01-tong-quan/LO_TRINH_PHAT_TRIEN.md); không gọi feature đã triển khai |

## 3. acceptance_criteria — điều kiện nghiệm thu và bước gỡ chặn theo nhóm

**GD0-PRE06:** đối chiếu receipt PRE-06 operator đã lưu, merge PR #3 và khối bằng chứng phản ví dụ; không yêu cầu tự mở camera để thử docs. **GD1-06-07/GD1-08-R53:** source/API và test trên HEAD; HMI/renderer thực đo nằm ở task `GD1-08-06-6`, không gộp vào việc hoàn thành feature. **GD1-R6-AUTO:** các kết quả R6 14/14, 618/3, CTest 2/2 được ghi đúng là nguồn operator và không biến SKIP thành PASS.

**GD1-R8-QUALITY:** kiểm tra runner `scripts/verify.ps1 -Profile Full` trên Windows cùng `SUMMARY.json`, JUnit và CTest; phân biệt commit R8.5 với lần chạy mới. **DOC-01/02/03A/03B/03C:** cần chứng cứ kiểm nội dung đúng mốc, đường dẫn, reviewer và commit; checker PASS chưa thay operator review. **DOC-04:** cần checker, targeted pytest, Full regression và đọc độc lập các bảng task/status/acceptance; chỉ chuyển `IN_REVIEW` sau khi áp pack, chưa tự chuyển `DONE`. **DOC-05:** chỉ mở khi DOC-04 được người vận hành duyệt, đánh giá inbound links và gate R7/R8; không tự xóa.

**GD1-08-06-6:** lập ma trận từng HMI/manual gate, môi trường/phương pháp/receipt, xử lý waiver đích danh với sign-off; nếu chưa có vẫn `BLOCKED`. **HW-CURRENT-BASELINE:** cung cấp quyết định có ngày, phần cứng, hình vẽ/đối chứng, người duyệt, loại `CURRENT_PHYSICAL` so với `TARGET_DESIGN`. **GD2-09:** chỉ khởi động khi kế hoạch riêng và dependency phù hợp được chốt; DOC-04 không tạo source mới.

## 4. Quy trình cập nhật và truy vết

1. Đề nghị thay đổi nêu `task_id`, hiện trạng, owner, blocker, nguồn và điều kiện đạt; không sửa hậu tố `task_id` để tạo vẻ hoàn thành.
2. Ghi nhận SHA đầy đủ hoặc PR, `evidence_uri` có thể truy cập từ môi trường nghiệm thu và ngày chạy thực. Thiếu nguồn thì giữ `IN_REVIEW`, `NOT_TESTED` hoặc `BLOCKED` tương ứng.
3. Khi acceptance duyệt, cập nhật `status`, `updated_at`, `updated_by` và link sang [Evidence Index](../07-nghiem-thu/EVIDENCE_INDEX.md), không copy log vào module.
4. Nếu task bị hủy/dời, nêu lý do và người duyệt; khi phát hiện mâu thuẫn giữa nhật ký cũ và code mới, ghi đính chính có ngày ở biên bản mới, **không sửa bản lịch sử**.

## 5. Giới hạn đã biết

Đây là seed register có nguồn tại một commit, **không giả định bao phủ mọi task vi mô hoặc toàn bộ 20 phiên bằng 20 dòng**. Task tương lai được thêm khi được giao. Các receipt Windows, danh tính người phê duyệt và cấu hình cơ khí hiện hành chưa được cung cấp cho DOC-04; không được suy diễn từ việc xuất hiện branch/commit. `BLOCKED` không có nghĩa source GĐ1 đã hỏng, chỉ có nghĩa **thiếu điều kiện để chốt nghiệm thu**.
