# ScanToPath — Nhật ký phát triển tổng

**Biên tập tại R7-C:** 28/10/2026. **Cơ sở Git:** nhánh `feat/gd1-desktop-ui`, commit R7-B `f923d1e4852f8f36c6b0c7c2c20ecee4dbcf91d1`. Đây là nhật ký đối chiếu lại các mốc đã có, **không** phải kết quả chạy thử phần cứng hoặc Windows mới.

## 1. Các mốc phát triển đã được ghi nhận

| Mốc | Git/bằng chứng | Nội dung chính | Tình trạng và giới hạn |
|---|---|---|---|
| GĐ0, PRE-01–06 | PR #3, commit merge `8bf33591389dcdff82f0fbd5bf5932a22547c984` | C++20/pybind11/Gemini 2, RAW RGB-D v2, SQLite, lưu/đọc và nghiệm thu GĐ0 | Git đã ghi nhận; thử camera theo báo cáo người vận hành; không phải kiểm định hình học metric |
| GĐ1 các phiên 06–08 đầu tiên | [Hồ sơ 06–08](../archive/README.md) | Qt shell, Project Workspace, VTK preview; phát sinh lỗi lifecycle và trải nghiệm người dùng | Lịch sử từng lần thử chưa tổng hợp đủ |
| R1–R3.5 | `8c295e0` và hồ sơ R1–R3 | Tái cấu trúc bố cục UI, Project, Inspector, Processing Workspace | Cần xem hồ sơ cùng lần thử; không đồng nhất với nghiệm thu Viewer native cuối |
| R4.1–R4.5 | `46427d7f37e1de287373a5eab1ed85b1cf9f64bb` | So sánh embedded VTK với Render Host cô lập, chọn B có điều kiện | Lựa chọn kiến trúc **không** đồng nghĩa crash C++/FPS/VRAM đã kiểm chứng |
| R5.1 | `1019127803d6eac391ed2f5ea567c254feecaf2c` | Hợp đồng đọc PLY points/mesh và OBJ, SHA nguồn | Đọc hình học ngoài, chưa tạo point cloud từ RAW |
| R5.2 | `2ec6e7dbd4c9ba6933cbee1b0d44081470ba84b3` | Live Qt viewer, đổi nguồn, xử lý mất tiến trình và fallback PNG | Trải nghiệm theo phản hồi người vận hành; giới hạn native vẫn cần xét |
| R5.3 | `ff45ccf87ce770e25eedf6e12df6bb5aaa958734` | Chọn điểm/mặt, bảng thuộc tính, SVG, lưới và widget định hướng | Có 2 lần FAIL quan trọng trước khi commit; xem sổ sự cố |
| R6 tự động | R5.3 không đổi source; log `R6_20261027T150605Z_19408` | **14/14 PASS**, pytest **618 PASS/3 SKIP**, CTest **2/2**, native probe và benchmark | `NGUOI_VAN_HANH_BAO_CAO`; chưa biến thành nghiệm thu R6 tổng thể |
| R7 gói ban đầu | `b6369dfc07a3e0f9551408219815a9ff980085f5` | Tạo tài liệu tổng hợp, chưa sắp xếp được toàn bộ kho | Bản chuẩn hóa đầu tiên được phản hồi cần làm lại |
| R7-A | `8e37eba2d270974b0dc61dde52c62ebc92d24a98` | Kiểm kê 91 tài liệu Markdown thuộc `docs/` lúc kiểm kê | Danh mục phân loại; không phải quyết định di chuyển cuối cùng |
| R7-B | `f923d1e4852f8f36c6b0c7c2c20ecee4dbcf91d1` | Tổ chức lại tài liệu tiếng Việt, lưu trữ hồ sơ cũ, đường dẫn chuyển tiếp | Git đã nhận commit; không suy ra các hạng mục HMI/native còn mở đã đạt |
| R7-C | Bản triển khai sau `f923d1e` | Chuẩn hóa nhật ký, sổ sự cố, docstring/comment và kiểm kê chú thích | **CHỜ KIỂM THỬ WINDOWS VÀ COMMIT**, không tự ghi PASS |
| R8, 08.06.6 | Chưa có mốc hoàn tất | Thống nhất test/hợp đồng và đánh giá đóng băng GĐ1 | Chưa khởi động nghiệm thu tổng thể |

## 2. Phân định hai loại kết quả

**Được báo cáo PASS:** R6 kiểm thử **tự động** 14/14 từ log người vận hành; code R5.3 đã được commit. **Chưa chứng minh:** DPI 100/125/150%, đóng khi xử lý native C++ thật sự bận, tiêm lỗi C++ thực, VRAM/GPU và độ trễ hiển thị thực. Các phép đo benchmark Render Host không phải FPS màn hình.

**Không phải lỗi ứng dụng:** hai lần đầu R6 thất bại do chính runner PowerShell (xung đột `$args`, cách lấy exit code và thiếu `ctest -C Release`). Cần giữ cả lần FAIL và lần PASS trong nhật ký, không xóa dấu vết.

## 3. Truy vết

- [GĐ0 — PRE-01–06](GD0/GD0_EXECUTION_JOURNAL.md) · [GĐ1 — R1–R7](GD1/GD1_EXECUTION_JOURNAL.md) · [Sổ sự cố](GD1/INCIDENT_REGISTER.md).
- [Trạng thái R6](../acceptance/GD1_R6_ACCEPTANCE_STATUS.md) và [hồ sơ GĐ1](../acceptance/GD1.md).
- Hồ sơ nguồn giữ ở [kho lưu trữ](../archive/README.md); đối chiếu đường dẫn trước–sau R7-B trong [bản đồ di chuyển](NGUON_HO_SO_CU.md).
- Evidence thô (nếu còn tại Windows) nằm trong `_setup/.../evidence`, không được sao chép sang Git hoặc coi như đã kiểm chứng từ xa.
