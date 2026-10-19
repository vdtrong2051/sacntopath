# GĐ1 — 06.5A: HMI QSS gọn, màn hình laptop 14 inch

**Phạm vi:** UI-only sau 06.5, trước 06.6; không thay đổi hệ thống worker, SQLite, camera, RAW, VTK hoặc phép đo. Không gộp bước này vào 06.6 trước khi người dùng kiểm thử.

**Baseline Git:** `feat/gd1-desktop-ui` tại `cb427209d1b7287aa57be5f4114d5e8eae18c2e8`. Toàn bộ nhãn và thông báo người dùng giữ tiếng Việt.

## Thiết kế được chọn

- **HMI công nghiệp tối giản:** graphite tối, chữ sáng dễ đọc, một màu nhấn xanh thép cho lựa chọn/focus; màu vàng nâu dịu chỉ dùng cho trạng thái `CHƯA TRIỂN KHAI`. Không gradient, đổ bóng màu, hoạt ảnh hoặc icon tùy hứng.
- **Mật độ tương tác kiểu VS Code, không sao chép thương hiệu:** danh mục điều hướng nhỏ, menu và status bar gọn, ba dock có thể kéo/ẩn/mở, vùng làm việc trung tâm cuộn dọc; card góc 6px, nút góc 4px.
- **14 inch ≠ độ phân giải:** lấy `QScreen.availableGeometry()` ở **tọa độ logic của Qt**, đã phản ánh Windows DPI 100/125/150% và phần taskbar khi hệ điều hành hỗ trợ. Kích thước cửa sổ ban đầu không vượt vùng đó; giữ rìa tối đa 32×40 logical pixels. Không dùng `setFixedSize()` cho MainWindow.
- **Màn hẹp:** sidebar 172px, mặc định Inspector tạm ẩn nếu cửa sổ ban đầu hẹp dưới 970 logical px; Task Dock ẩn khi cao dưới 535 logical px. Mọi dock đều có thể bật lại từ **Hiển thị**. Sau lần thiết lập đầu không tự ẩn liên tục, tránh phủ định thao tác của người dùng.
- **Card không che nội dung:** workspace gói bằng `QScrollArea` dọc, nội dung tự xuống dòng và lề chỉ 16px. Các dock giữ kích thước tối thiểu và có thanh cuộn trong danh sách. Không dùng `position:absolute`, không cố định card dimensions.
- **QSS tách riêng:** `src/scantopath/ui/theme/hmi_panel.qss`, loader `theme/__init__.py`; thêm resource vào `pyproject.toml` để wheel/editable install không mất QSS.

## Hợp đồng hồi quy

- Không đổi public API của `ScanToPathMainWindow`, `NavigationViewModel`, `TaskAndEventPanel`, `QtTaskController` hoặc `TaskManager`.
- Không đổi bốn ID workspace, nhãn `CHƯA TRIỂN KHAI`, hay hai nút task fixture.
- Vẫn phân biệt `fixture` và `measured`/`validated`; QSS chỉ trình bày, không sửa nguồn dữ liệu.
- `QTimer`/worker chạy như 06.5; không mở camera, SQLite hay renderer trên GUI thread.
- Bài kiểm thử Qt offscreen không xác thực DPI thật hoặc chiều cao taskbar của Windows. Không tuyên bố UI 14 inch đã nghiệm thu nếu chưa chụp/kiểm tra màn hình vật lý.

## Cổng kiểm tra Windows

1. Chạy bộ `verify.ps1` mới (pytest full + Qt tests, CTest, native self-test, `git diff --check`). Trạng thái symlink test bị skip do quyền Windows như trước là ngoại lệ được ghi nhận, không coi là pass.
2. Khởi động `python -m scantopath.ui.main` với `QT_QPA_PLATFORM` không phải `offscreen`.
3. Kiểm tra laptop **1366×768 ở scaling 100% / 125% / 150%** nếu các mức khả dụng và **1920×1080 ở 125% / 150%** nếu thiết bị hỗ trợ. Không bắt buộc thay độ phân giải vật lý chỉ để chạy kiểm thử; ghi lại độ phân giải/scaling đang dùng.
4. Kiểm tra cửa sổ khởi tạo nằm trọn trong desktop làm việc; menu, cả bốn workspace, nhãn trạng thái, Cây dự án, Thuộc tính, bảng Tác vụ có thể truy cập, thông tin card có thể cuộn nếu nhỏ.
5. Kéo tách/thu hẹp dock, ẩn/mở từ **Hiển thị**, thu nhỏ cửa sổ và khôi phục; không có thao tác nào bị mất vì chồng lớp hoặc clipped.
6. Chạy và hủy một tác vụ **KIỂM THỬ** trong khi chuyển workspace; đóng an toàn như 06.5. Không có camera/SQLite auto-access.

**Chưa bao gồm:** thiết kế lại layout ở mức wireframe mới, icon set, bảng Project thật (07), VTK Viewer (08), mô hình 3D, đo độ chính xác hoặc HMI điều khiển actuator. Nếu nhận phản hồi kích thước 14 inch thật, sửa lại số liệu bố cục bằng một patch UI-only tiếp theo trước 06.6.
