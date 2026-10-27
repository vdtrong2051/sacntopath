# GĐ1 — 07.9B: Viền panel và xử lý nội dung dài

**Baseline:** 19e950c9a3bcd5ed08decb59f8d1fd1b203536ba (07.8), trên working tree đã cài 07.9/07.10 và bản UI Redesign Fixed. Chưa được nghiệm thu Windows hoặc push khi tạo bản vá này.

## Phạm vi

- Giữ theme **Technical Light** đang được duyệt; bổ sung border 1px `#C7D6E7` cho ba QDockWidget native và viền `#D5E1EF` cho workspace, không xếp thêm vùng màu xám hay lớp card giả.
- Nhấn rõ border của card nội dung và tab pane, đồng nhất spacing trong `ProjectExplorer`, `PropertyInspector`, `TaskAndEventPanel`.
- Điều chỉnh dock mục tiêu cỡ 215–255px và min 205–215px: bảo vệ workspace trung tâm trên laptop nhỏ thay vì ép dock tới 300–340px.
- Dòng dài trong Explorer và Inspector sẽ elide ở giữa, có **tooltip đầy đủ**; không cắt/mất nội dung dữ liệu. State/Planned/Action hint trong workspace sẽ word-wrap. Status bar có tooltip chứa nguyên chuỗi.
- Dock Tác vụ khi hẹp dưới 460px sẽ tự xếp hai nút **thành hai hàng**, tránh tràn chữ, không đổi tên nút, signal hoặc worker.
- Bổ sung test resource và Qt offscreen. Test thực tế 100%, 125%, 150% Windows DPI là cổng nghiệm thu thủ công; offscreen không thay thế ảnh thật.

## Giới hạn

- Không đổi SQLite, RAW, VTK, camera, C++ hay nghiệp vụ 07.1–07.8.
- Không tự xác nhận `QFont::setPointSize(-1)` hết cảnh báo nếu máy Windows chưa kiểm tra.
- Không tự chạy migration, không cấp mã và không mở kết nối DB khi khởi động UI.
- Các nội dung dài của `QTreeWidget` được **elide + tooltip**, không thể tự giãn nhiều hàng bảo đảm mọi thiết lập font. Người dùng có thể mở rộng dock bằng kéo đường chia.

## Kiểm thử và nghiệm thu

1. `repair.ps1`: HEAD đúng baseline, đối chiếu 14 tệp đã cài và 3 thành phần vẫn nguyên bản, sau đó thay 6 tệp và tạo 3 mục mới (2 test, 1 doc).
2. `verify.ps1`: kiểm tra đủ 20 mục thay đổi, chạy focused resource + Qt test, toàn bộ regression, CTest 2/2 và native selftest hardware_access=false.
3. Kiểm tra mắt thường các dock khi cửa sổ 1366×768, 125% DPI và các dock nhỏ/được kéo rộng; chữ ở Cây dự án, Inspector, trạng thái, tác vụ không bị che không có cách xem toàn văn.
4. Không commit/push trước khi full Windows regression và manual UI đều đạt.
