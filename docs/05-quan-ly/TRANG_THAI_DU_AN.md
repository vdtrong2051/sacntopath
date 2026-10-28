# Trạng thái dự án ScanToPath — State Ledger hiện hành

> `owner: PROJECT_COORDINATOR` · `as_of_commit: 81da5d2050324b1dc4a65ffbca9a38ed1ebba10a` · `verified_at: 2026-10-28`  
> `scope: snapshot triển khai/kiểm thử GĐ0–GĐ1, kế hoạch GĐ2–GĐ5 và docs v2` · `source-of-truth: trạng thái sống duy nhất, không phải receipt nghiệm thu` · `evidence_level: GIT_VERIFIED / OPERATOR_REPORTED_HISTORICAL / CURRENT_WINDOWS_NOT_TESTED`

## 1. Ba trục trạng thái độc lập

`implementation` = `NOT_STARTED | PARTIAL | IMPLEMENTED | DEPRECATED`, dựa vào source. `automated_verification` = `NOT_TESTED | PASS | FAIL | SKIP_WITH_REASON` **kèm scope, thời điểm và nguồn**. `physical_manual_verification` = `NOT_TESTED | PARTIAL_EVIDENCE | PASS | FAIL | WAIVED_WITH_APPROVAL` (waiver phải đích danh gate, không cấp PASS). Một capability có source `IMPLEMENTED`, R6 automated được báo cáo PASS, nhưng manual GĐ1 vẫn `NOT_TESTED`. Các dòng dưới là **snapshot theo HEAD trên**, không tự đồng bộ với quá trình phát triển sau đó.

## 2. Capability ledger

| capability_id | implementation | automated_verification (scope và nguồn) | physical_manual_verification | Giới hạn/điều kiện còn mở |
|---|---|---|---|---|
| `FOUNDATION_GD0` | `IMPLEMENTED` | `PASS` — PRE-06 operator Windows report, [PRE-06](../99-lich-su/ARCHIVE/GD0/PRE/PRE_06_GD0_ACCEPTANCE.md) | `PARTIAL_EVIDENCE` — một lần chụp Gemini 2 và replay | Không phải chứng chỉ sync/pose/accuracy; merge PR #3 là Git evidence |
| `ACQ_GEMINI2` | `IMPLEMENTED` (command one-shot/adapter) | `PASS` — test RAW/adapter trong lịch sử PRE-06, nguồn operator | `PARTIAL_EVIDENCE` — one-shot Gemini 2 tại PRE-06 | SDK/hardware chưa chạy lại tại DOC-04; không có rig quyết định hiện hành |
| `RAW_V2` | `IMPLEMENTED` | `PASS` — PRE-06 + R6 operator, test unit/integration có source | `PARTIAL_EVIDENCE` — read-back/hash of real capture | `COMMITTED`, SHA-256; không atomic xuyên filesystem/SQLite |
| `PROJECT_WORKSPACE` | `IMPLEMENTED` | `PASS` — R6 automated operator-reported 618/3 (toàn suite) | `NOT_TESTED` — DOC-04 không có HMI từng ca mới | Không ngầm tạo SQLite từ màn hình; CLI có thể ghi/tạo DB |
| `DESKTOP_SHELL` | `IMPLEMENTED` | `PASS` — R6 Qt automated operator report | `PARTIAL_EVIDENCE` — lịch sử 08.06.4 session A/waiver | DPI 100/125/150, native busy/reopen chưa có chứng minh R6 final |
| `VIEWER_R53` | `IMPLEMENTED` (PLY/OBJ bên ngoài, interaction) | `PASS` — R6 automated 14/14 operator report | `PARTIAL_EVIDENCE` — R5.3/08.06.4 UI sample và operator waiver | Không có RAW→mesh hay FPS vật lý; native real fault vẫn mở |
| `RENDER_HOST_ISOLATION` | `IMPLEMENTED` (child process IPC) | `PASS` — R6 native/transport operator report | `PARTIAL_EVIDENCE` — normal shutdown; NOT_TESTED for busy native/fault | Benchmark render-completed không là input→display-present latency |
| `R8_TEST_INFRA` | `IMPLEMENTED` (scripts R8.1–8.5) | `NOT_TESTED` — DOC-04 **chưa đọc receipt Full Windows sau R8.5**, không phủ nhận báo cáo lịch sử | `NOT_TESTED` — không phải gate HMI | R8.5 commit `493a24d`; runner có Quick/Full/Acceptance, không đóng GĐ1 |
| `DOCUMENTATION_V2` | `PARTIAL` — DOC01–03C committed, DOC04 pack pending, DOC05 chưa làm | `NOT_TESTED` — chưa chạy checker/Full trên Windows cho DOC04 | `NOT_TESTED` — reviewer sign-off chưa có | Nguồn v2 mới viết, alias cũ còn sống; chuyển đích thuộc DOC05 |
| `HMI_GD1_08_06_6` | `PARTIAL` — danh mục gate/hồ sơ có sẵn, chưa final sign-off | `NOT_TESTED` — automation không thay manual | `PARTIAL_EVIDENCE` — riêng session A lịch sử; các gate khác còn mở | **GD1_OVERALL_PENDING**; waiver 08.06.5 không chuyển thành final approval |
| `METRIC_SINGLE_VIEW_GD2` | `NOT_STARTED` | `NOT_TESTED` | `NOT_TESTED` | RAW replay, unprojection, proof of units chưa tích hợp |
| `REGISTRATION_FUSION_TRUST_GD3` | `NOT_STARTED` | `NOT_TESTED` | `NOT_TESTED` | Chưa có calibrated pose, RMSE/drift, fusion verified |
| `FEATURE_REPLICA_GD4` | `NOT_STARTED` | `NOT_TESTED` | `NOT_TESTED` | Không có feature fit/residual CAD hiện hành |
| `ACTIVE_ACQUISITION_GD5` | `NOT_STARTED` | `NOT_TESTED` | `NOT_TESTED` | Chưa có nhận biết vật, NBV, điều khiển cơ cấu hoặc robot motion |

**Cách hiểu `NOT_TESTED` ở R8:** DOC-04 xác minh **tồn tại code/commit**, không có quyền đọc receipt Windows sau mốc đó. Bảng không phủ định một lần test có thể đã được người vận hành chạy nhưng chưa có nguồn trích trong đây. Khi xuất trình receipt, cập nhật chính hàng này với `executed_at`, commit, tool, environment và người phê duyệt.

## 3. Đối chiếu các giai đoạn và điểm mở

| Giai đoạn | Implementation/source | Kết luận giới hạn |
|---|---|---|
| GĐ0 | Source + PR #3 merge; PRE-06 Windows operator report | Có nền dữ liệu; không chứng nhận metric accuracy |
| GĐ1 | Qt, Project, Viewer R5.3/R6 đã có trong Git | **GD1_OVERALL_PENDING** theo [GD1 acceptance](../07-nghiem-thu/GD1_ACCEPTANCE.md) và `08.06.6` |
| R7/R8 | Mốc chuẩn hóa source/test đã có commit qua R8.5 | Không cập nhật kết quả 08.06.6 bằng việc test infrastructure tồn tại |
| DOC-01→03C | Tài liệu/kiểm tra đã commit tới `81da5d2` | Windows Full/reviewer chưa được xác nhận độc lập trong DOC-04 |
| DOC-04 | Bản vá đang được soạn tại HEAD này | Sau áp dụng và nghiệm thu mới ghi nhận commit mới |
| DOC-05, GĐ2→GĐ5 | Chưa thực thi trong source đã kiểm | Chỉ roadmap/điều kiện tương lai |

## 4. Những chuyển trạng thái được phép

`IMPLEMENTED` phải có code path và contract test tương ứng; nếu API bị xóa thì ghi `DEPRECATED` + commit. Chuyển `automated_verification` sang `PASS` cần receipt kiểm chứng JUnit/CTest/runner (hoặc nguồn operator được gắn nhãn rõ). Chuyển manual sang `PASS` cần phương pháp đo/hình ảnh/log ở môi trường đúng và người duyệt; `WAIVED_WITH_APPROVAL` là **một loại quyết định khác**, có residual risk và không tự lan sang cổng 08.06.6.

**Owner:** `PROJECT_COORDINATOR` cập nhật snapshot này sau khi [Task Register](TASK_REGISTER.md) và [Evidence Index](../07-nghiem-thu/EVIDENCE_INDEX.md) có link thực; không copy cả bảng gate vào README. Roadmap [định hướng](../01-tong-quan/LO_TRINH_PHAT_TRIEN.md) không sở hữu trạng thái test.

## 5. Giới hạn đã biết

Git xác nhận file và lịch sử, không xác nhận mọi lượt thử Windows/physical. Cấu hình Gemini 2 cố định/handheld/rig có các phương án theo thời điểm: thiếu ADR vật lý mới, trạng thái `HW-CURRENT-BASELINE` vẫn `BLOCKED`. Không tự thay `PARTIAL_EVIDENCE` thành `PASS` từ các lần thử ảnh fixture, GPU benchmark hay câu chữ ở hồ sơ 08.06.5.
