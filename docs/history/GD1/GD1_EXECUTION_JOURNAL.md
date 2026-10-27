# GĐ1 — Nhật ký triển khai và những lần kiểm thử

**Mốc tài liệu:** R7-C, sau commit R7-B `f923d1e`. **Phân loại nguồn:** commit/tài liệu Git = `XAC_MINH_GIT`, log PowerShell dán trong trao đổi = `NGUOI_VAN_HANH_BAO_CAO`. Không tự lập số lần thử chưa có dữ liệu.

## 1. Chuỗi triển khai

| Phiên | Nội dung đã triển khai | Điều cần nhớ khi bảo trì |
|---|---|---|
| 06–07, 07.11–07.12 | Qt shell, Project/SQLite/RAW, phân tách controller và quy tắc dependency | Architecture Guard/Quality Gate là kiểm tra tĩnh, không phải chứng minh toàn diện SOLID |
| 08 đầu | PLY/VTK preview; sửa lỗi khi tương tác hoặc đóng tiến trình | Sự cố UI/native đã dẫn đến quyết định tái kiến trúc; đừng dùng kết quả preview làm kết quả live hiện tại |
| R1–R3.5 | Compact navigation, Project Workspace, Inspector, Processing Workspace | Những lần HMI sớm không thay cho HMI R6 trên các mức DPI |
| R4.1–R4.5 | So sánh VTK nhúng và VTK ở tiến trình riêng, IPC và shared RGB frame/ACK | Chọn Render Host B **có điều kiện**, chưa đo FPS hiển thị/VRAM hay crash C++ thật |
| R5.1 | PLY points/mesh, OBJ và SHA nguồn | Nhập file ngoài; không phải pipeline biến ảnh RAW thành hình học |
| R5.2 | Live Qt viewer, đổi nguồn, retry và fallback PNG | Có sửa regression giới hạn dòng `main_window.py` |
| R5.3 | Picker điểm/mặt, SVG, grid, Inspector, thao tác chuột | Giữ giới hạn revision và clear selection; có 2 lỗi test được sửa trước commit |
| R6 | Kiểm thử tự động tích hợp | 14/14 PASS theo operator; **R6 tổng thể còn PENDING** |
| R7-A | Kiểm kê toàn bộ tài liệu hiện có | Commit `8e37eba` sau lần kiểm kê 91 file |
| R7-B | Tổ chức tài liệu tiếng Việt, archive và chuyển hướng | Commit `f923d1e`; giữ các đường dẫn tương thích mà test cũ sử dụng |
| R7-C | Nhật ký/sự cố và chú thích mã nguồn | Gói tài liệu/comment, chưa tự chứng minh hồi quy Windows PASS |

## 2. Các lượt thử không được xóa

| Lượt thử | Dấu hiệu trên log | Diễn giải đúng | Trạng thái tiếp theo |
|---|---|---|---|
| R5.3 ban đầu | 8 PASS, 1 FAIL: `test_r53_live_click_emits_uv_only_in_select_mode` | Fixture thiếu frame đã nhận ACK, đồng thời UI chưa đạt yêu cầu sử dụng | Sửa fixture, giữ no-frame guard, rework giao diện |
| R5.3 UI rework | 16 focused PASS; full 617 PASS, 1 FAIL, 3 SKIP | Bài R5.2 kiểm chuỗi constructor cũ không khớp lớp kế thừa | Sửa alias tương thích, không tắt test |
| R5.3 sau sửa | Commit `ff45ccf` | Git đã nhận mã nguồn R5.3 | HMI chuyên sâu chuyển R6 |
| R6 attempt 1 | Mọi subprocess FAIL trước khi chạy thực | `$args` đụng biến tự động PowerShell, các lỗi thiếu receipt chỉ là hệ quả | Vá runner; **không gán lỗi cho ScanToPath** |
| R6 attempt 2 | Pytest 618 PASS/3 SKIP nhưng runner ghi FAIL; CTest thiếu cấu hình | Exit code rỗng và CTest thiếu `-C Release` | Vá runner, không sửa source sản phẩm |
| R6 attempt 3 | 14/14 PASS, 618 PASS/3 SKIP, CTest 2/2, native Viewer và benchmark PASS | Log người vận hành, evidence `_setup/ScanToPath_R6_Auto_Acceptance/evidence/R6_20261027T150605Z_19408` | Đóng riêng phần **tự động**; tổng thể PENDING |

## 3. Những điều còn mở

**Chưa được xác nhận bằng phép thử phù hợp:** các DPI 100/125/150%, đóng khi native đang thực sự bận, tiêm lỗi C++ thực, GPU/VRAM, thời gian từ thao tác đến hiện trên màn hình. Thử kill tiến trình và benchmark render không chứng minh những việc này.

Ba `SKIP` quyền tạo symlink trên Windows: `tests/test_gd1_07_2_numbered_storage.py`, `tests/test_gd1_r4_3_transport_lifecycle.py`, `tests/test_raw_storage.py`. Đây là **ngoại lệ có giải thích**, không phải ba nhánh bảo vệ đã được kiểm thử.

## 4. Nguồn chi tiết

- [Sổ sự cố](INCIDENT_REGISTER.md) · [Nghiệm thu R6](../../acceptance/GD1_R6_ACCEPTANCE_STATUS.md) · [Nhật ký tổng](../DEVELOPMENT_MASTER_LOG.md).
- [Hồ sơ R5.3](../../archive/GD1/R1-R5/R5_03_INTERACTION_INSPECTOR_UX.md) · [R4.5 bàn giao](../../archive/GD1/R1-R5/R4_05_R5_HANDOVER_GATES.md) · [Kho lưu trữ](../../archive/README.md).
- **CHƯA ĐỦ LỊCH SỬ:** tổng số lần thay đổi và thời gian từng attempt R1–R4 nếu không có nhật ký đầy đủ; không ước đoán.
