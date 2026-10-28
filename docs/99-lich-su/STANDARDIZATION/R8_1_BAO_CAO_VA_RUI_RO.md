# R8.1 — Kiểm kê hệ thống kiểm thử và bản đồ hợp đồng

**Baseline khóa để kiểm kê:** `feat/gd1-desktop-ui@f59d3f8518c52879c9b5b7fe37539ffd9061827a` (R7-D).  
**Phạm vi:** kiểm tra tĩnh mã nguồn `tests/` và `scripts/` trực tiếp từ GitHub; công cụ bổ sung có thể đối chiếu với bản đang chạy trên Windows. **Không thay đổi test cũ, source ứng dụng, SQLite, RAW hoặc C++.**

## 1. Kết quả kiểm kê ban đầu

| Nhóm | Số lượng tại baseline |
|---|---:|
| Tệp Python trong `tests/` | **75** |
| Script tại `scripts/` | **22** (21 Python, 1 PowerShell) |
| **Tổng số đã phân loại** | **97** |
| Full pytest Windows do người vận hành báo ở R7-D | **635 PASS, 3 SKIP** |
| CTest Release R7-D | **2/2 PASS** |

**Lưu ý:** số lượng tệp, số hàm `test_` tĩnh và số test case thu thập bởi pytest là ba đại lượng khác nhau. Không dùng số hàm AST thay 635 PASS. Thống kê 635/3 là lịch sử đã báo cáo, không phải một phiên kiểm thử mới trong R8.1.

Đọc [ma trận 97 tệp](../../standardization/R8_1_MA_TRAN_97_TEP.csv) để tra từng thành phần: chủ đề, hợp đồng, tầng kiểm thử dự kiến, bước xử lý và mức chắc chắn. Quy tắc R8.1: `GIU` không đồng nghĩa hoàn thiện; `CAN_DOI_CHIEU` không đồng nghĩa trùng và được phép xóa; `CAN_SUA_R8_3` chỉ là ứng viên sửa sau khi có kiểm thử thay thế. Không có file nào được kết luận “trùng hoàn toàn” chỉ từ tên hoặc số phép thử.

## 2. Các vấn đề đã đối chiếu với mã nguồn

| Mã | Bằng chứng | Đề xuất bước tiếp theo |
|---|---|---|
| R81-01 | `tests/test_gd1_r3_5_integrated_ux.py`, `test_gd1_r3_4_processing_workspace.py` và `test_gd1_07_8_qt.py` import `_seed_*` từ `test_gd1_07_8_integrated.py`; một số test 07.3/07.6/07.7 cũng import helper của 07.2. | R8.2 chuyển helper sang `tests/support/` hoặc `conftest.py`, chạy song song trước khi bỏ import test→test. |
| R81-02 | `tests/test_gd1_r5_2_live_viewer.py` kiểm chuỗi `LiveViewer3DController(` và giới hạn dưới 500 dòng của `main_window.py`; `tests/test_gd1_07_10_modular_architecture.py` cũng đặt ngưỡng số dòng. | R8.3 thay kiểm tra chuỗi dễ gãy bằng AST/contract hoặc behavioral test; giữ nguyên các test đang chạy đến khi đối chiếu. |
| R81-03 | `scripts/check_qt_acceptance_xml.py` từ chối `len(skips)>2` trong khi Windows hiện có ba trường hợp symlink SKIP được ghi trong R6/R7. | R8.3 cho phép theo *đúng nodeid và lý do* (allowlist), không chấp nhận tăng ngưỡng tùy tiện. |
| R81-04 | Test Qt từ phiên 06, 07, 08, R2, R3 và R5 cùng kiểm tra Shell, Project, Viewer theo các giai đoạn khác nhau. | R8.2–R8.3 lập cụm đối chiếu hành vi; chưa có bằng chứng về assertion trùng tuyệt đối. |
| R81-05 | Script R4.1–R4.5 phục vụ mô phỏng, đối chứng A/B, đo hoàn tất khung hình và nguồn lịch sử ADR. | **Giữ** cho tới khi xác định không còn phụ thuộc; không xóa PoC chỉ vì không thuộc runtime chính. |
| R81-06 | Test native/VTK subprocess và Qt offscreen khác với HMI thật, native busy/fault và độ trễ trình bày màn hình. | Mốc nghiệm thu cuối 08.06.6 vẫn cần chứng cứ riêng, không chuyển thành PASS ở R8.1. |
| R81-07 | `scripts/r7_docs_gate.py` và hai test R7 bảo vệ AST/lịch sử cố định; các trang tương thích vẫn còn tồn tại. | Giữ đến khi R8 kiểm kê mọi caller, thay bằng cổng vững chắc trước khi bỏ. |

## 3. Bản đồ theo nhóm hợp đồng

| Phạm vi | Nhóm test/script cần bảo toàn | Hợp đồng |
|---|---|---|
| Thu nhận RGB-D | `test_native_loader`, `test_pre04_orbbec_adapter`, `test_raw_rgbd_contract` | Không tự mở camera, byte gốc, độ sâu Y16, provenance |
| RAW và SQLite | `test_raw_storage`, `test_capture`, `test_pre05_metadata_store`, `test_pre06_gd0_acceptance`, nhóm 07.2–07.8 | Ghi nhất quán, SHA-256, transaction, migration tường minh, v1/v2 |
| Qt Shell và tác vụ | 06, 07.9, R2 | Navigation, dock, worker, cancellation, khả năng truy cập |
| Project Workspace | 07.3–07.8, R3 | Dịch vụ, form, inspector, ProcessingRun, số mã và audit |
| Viewer hình học | 08, R5 | PLY/OBJ, điểm/mặt, chọn, camera, xóa trạng thái cũ |
| Render Host và IPC | R4.1–R4.5, R5.1–R5.3 | Resident process, copy/ACK, timeout, khởi động lại, benchmark |
| Cổng kiến trúc và tài liệu | 07.10–07.12, R7/R7-C, `scripts/check_*` | Boundaries, AST, cấu trúc, tình trạng chứng cứ |

**Đề xuất đích của ma trận** chỉ là vị trí sau này của R8.2. R8.1 **không tạo** các thư mục `tests/unit`, `integration`, `contracts`, `e2e`, `performance`, `regression` hay thay imports.

## 4. Kết quả kiểm kê động trên Windows

Sau khi áp dụng, chạy `scripts/r8_1_test_inventory.py --project-root ... --out-dir ...` để nhận:

- `R8_1_DU_LIEU_QUET.json`: đường dẫn, Git blob, SHA-256 local, hàm test, import module, đường dẫn source liên quan và cờ rủi ro.
- `R8_1_MA_TRAN_BO_SUNG.csv`: bảng lọc 97 mục với bằng chứng đọc trực tiếp từ filesystem Windows.
- `R8_1_BAO_CAO_QUET.md`: số liệu và những vấn đề cần xem xét.

Tool đọc AST, không import mã nguồn ứng dụng. Không đo mức phủ nhánh, không tự chứng minh test trùng, không kiểm tra phần cứng. Đây là kết quả kiểm kê để ra quyết định R8.2, không phải nghiệm thu R8 tổng thể.

## 5. Tiêu chí nghiệm thu R8.1

**PASS** khi: baseline phù hợp; bảng tĩnh đủ 75/22 và không trùng đường dẫn; tool kiểm kê local đọc đủ 97 tệp, không có lỗi phân tích; tập test R8.1 chạy PASS; full pytest/CTest/quality gates không bị ảnh hưởng; không có thay đổi ngoài các tệp R8.1. **Chưa PASS** nếu Windows chưa chạy test và chưa kiểm tra CSV.

R8.2 tiếp tục phân nhóm và tách fixture; R8.3 chạy song song test cũ/mới; R8.4 triển khai cổng kiểm thử thống nhất. Đóng băng GĐ1 vẫn phải chờ **08.06.6**.
