# GĐ1 — Desktop Experience, Project Workspace và Viewer 3D

> `owner: STAGE_OWNER` · `as_of_commit: 81da5d2050324b1dc4a65ffbca9a38ed1ebba10a` · `verified_at: 2026-10-28`  
> `scope: hồ sơ outcome của GĐ1, không phải ledger hay final acceptance` · `source-of-truth: stage definition + Git source; kết quả gate thuộc 07-nghiem-thu` · `evidence_level: SOURCE_VERIFIED + OPERATOR_REPORTED_R6; FINAL_PENDING`

## 1. Mục tiêu, input và điều kiện Done

Trên nền GĐ0 (RAW và metadata), GĐ1 cung cấp Qt/PySide6 desktop với Project Workspace và Viewer hình học 3D có khả năng thao tác, sửa lỗi và kiểm tra hồi quy. Done yêu cầu: source contract/UI/Viewer, dữ liệu test, ổn định vòng đời process, **Full Windows regression** và kết luận manual HMI/native đúng gate. `git merge` hoặc `R8.5` không thay thế cổng cuối **08.06.6**.

In-scope: shell/window, task/Project/SQLite, mở PLY/OBJ ngoài, Render Host IPC, shared RGB copy/ACK, click picking Inspector. Out-of-scope: xử lý RAW→point cloud/mesh, metric calibration, fusion, feature/replica, Zigzag, robot trajectory, rig/actuator điều khiển.

## 2. Các gói kết quả và giá trị thực

| Mốc | Công việc có source | Vẫn cần kiểm soát |
|---|---|---|
| 06–07/07.12 | Qt shell, Project commands/queries/UI, RAW/numbering, boundary guard | Không đọc/ghi DB ngầm khi mở UI; tránh QObject ownership/race |
| 08 đầu | Viewer PLY, kết nối Qt/VTK | Đã có incident; code hiện chuyển sang host riêng |
| R1–R3.5 | Navigation/dock, Inspector/Project Processing Workspace | Mỗi lần UI rework không thay HMI cuối |
| R4.1–R4.5 | A/B embedded vs isolated host, frame transport | Chọn render host riêng có điều kiện; benchmark không phải physical FPS |
| R5.1 | SceneSource/Descriptor, PLY/OBJ, SHA nguồn | `units=unknown`, `coordinate_frame=unknown` đối với file ngoài |
| R5.2 | Qt live view, host lifecycle/retry, fallback | Không block Qt event loop, chỉ copy frame trước ACK |
| R5.3 | Picking điểm/mặt, toolbar SVG, Inspector/lưới | Chống stale scene/frame; cell hit ≠ CAD vertex |
| R6 | Automated acceptance | 14/14 automated PASS theo operator; overall PENDING |
| R7→R8.5 | Docs audit/standardization; reorganized tests; unified runner/audit | Test gates thay đổi cấu trúc nhưng không tự đóng 08.06.6 |
| DOC-01→03C | Docs v2 overview/modules/developer đã commit | DOC-04/05 còn thực hiện; reviewer/Windows receipt không do commit tạo ra |

## 3. Quy trình kỹ thuật hiện hành

- **Project**: Qt workspace → controller/presenter → application command/queries → adapters SQLite và RAW; không để QWidget tự thao tác DB. Xem [Project](../03-modules/PROJECT_WORKSPACE.md).
- **Viewer**: PLY/OBJ → SceneDescriptor / `source_sha256` → controller Qt → IPC → VTK Render Host child → frame RGB shared memory → client copy → ACK → Qt display. Interaction click có `scene_revision/frame_revision`, dùng picker point/face và Inspector. Xem [Viewer](../03-modules/VIEWER_3D.md).
- **Error/cleanup**: host loss/timeout/cancel/stale frame và đóng cửa sổ phải không để buffer bị truy cập sau ACK; bắt buộc kiểm tra bằng regression, native fault phải có phép thử riêng.

## 4. Trạng thái nghiệm thu GĐ1

Hồ sơ R6 ngày 27/10 báo 618 pytest PASS / 3 symlink SKIP, CTest 2/2, native + benchmark và 14/14 automated. Những gì còn thiếu: DPI 100/125/150, HMI reopen/close, native C++ busy close, native fault injection thật, GPU/VRAM và độ trễ input→physical present. Hồ sơ 08.06.5 ghi operator waiver cho TC11/12 của session B/C thời điểm trước nhưng **không tự miễn** các gate mới của `08.06.6`.

`GD1_OVERALL_PENDING` cho đến khi [bảng GD1 acceptance](../07-nghiem-thu/GD1_ACCEPTANCE.md) có đầy đủ receipt và quyết định cuối theo từng điều kiện. `scripts/verify.ps1 -Profile Full` là kiểm tra tự động cần chạy trên Windows, không đủ để ký manual.

## 5. Bàn giao, rủi ro và tác vụ

Giai đoạn tiếp theo GĐ2 ưu tiên RAW replay/single-view geometry, không nhảy thẳng sang registration/fusion nếu pose/metric chưa được chứng minh. Tên session mới theo [Crosswalk](SESSION_CROSSWALK.md) là đối chiếu năng lực, không phải danh sách task đã hoàn thành. `task_id` liên quan `GD1-06-07`, `GD1-08-R53`, `GD1-R6-AUTO`, `GD1-R8-QUALITY`, `GD1-08-06-6` ở [Task Register](../05-quan-ly/TASK_REGISTER.md); nguồn trạng thái ở [State Ledger](../05-quan-ly/TRANG_THAI_DU_AN.md). Các incident cũ và mọi attempt FAIL lưu tại [Incident Register](../05-quan-ly/INCIDENT_REGISTER.md) và [history](../99-lich-su/JOURNALS/GD1_EXECUTION_JOURNAL.md).

## 6. Giới hạn đã biết

GĐ1 có code và các kết quả operator-reported; DOC-04 không thực hiện phép HMI/camera mới, không có native C++ busy/fault physical receipt ở baseline được đọc. Không dùng một hình chụp Viewer để khẳng định độ chính xác hình học; mesh ngoài không có bảo đảm đơn vị.
