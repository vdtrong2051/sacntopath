# GĐ1 07.9 — HMI Recovery: thiết kế lại lần hai (sau phản hồi Windows)

## 1. Tình trạng bản đầu

Bản slate-dark 07.9 ban đầu khiến các panel xám thiếu độ tách lớp, cột điều hướng `DA/RGB/3D/XL` chen giữa Explorer và vùng làm việc, gây khó thao tác. Kiểm thử 06.3 bị đỏ vì thay `Chưa chạy phép đo` thành `Không chạy phép đo` trong `workspaceFootnote`. Đây là regression phải sửa, không được bỏ assert.

## 2. Thiết kế thay thế

- **Technical Light**: canvas `#F4F8FD`, panel `#FFFFFF`, chữ chính `#17263C`, xanh thao tác `#1463D7`, xanh xác nhận `#08796A`. Không phải lớp xám-on-xám; độ tương phản kiểm tra bằng test.
- **Điều hướng ngang toàn chiều rộng** bằng `QToolBar` không di chuyển, thay cột 76px khó nhận biết. Bốn workspace có nhãn dễ đọc, vẫn giữ `WorkspaceId`, Ctrl+1..4 và `nav_buttons` API.
- **Workspace thực dụng**: nút `Mở kho dữ liệu` dùng chính `_choose_project_store`, nút `Xem nhật ký SQLite` dùng dock đã có; trang 3D/RGB-D chỉ hướng dẫn và không tạo dữ liệu.
- **Dock Qt nguyên bản**: tôn trọng Explorer/Inspector/Task, `toggleViewAction` và drag/dock; không thêm dependency docking ngoài, không sửa backend.
- **Trạng thái trung thực**: Project/Processing đã dùng qua panel, Capture/3D chưa triển khai; vẫn giữ `Chưa chạy phép đo` trong ghi chú, tránh làm sai kỳ vọng 06.3.
- **Nền và đường viền**: các panel trắng, nội dung phân cấp bằng kích thước và spacing, bo 7–11px. Không lạm dụng badge/trang trí, không bịa kết quả camera.

## 3. Tham chiếu thiết kế

- Spyder IDE: bố cục dock có thể sắp xếp/ẩn/hiện, tab làm việc. https://docs.spyder-ide.org/current/videos/first-steps-with-spyder.html
- Qt Advanced Docking System: mô hình docking và auto-hide phù hợp tương lai; **không cài** thư viện này ở GĐ1. https://github.com/githubuser0xFFFF/Qt-Advanced-Docking-System
- QDarkStyleSheet: nguồn tham khảo cách cấu trúc rules Qt; không nhập theme bên ngoài. https://github.com/colinduquesnoy/qdarkstylesheet

## 4. Nguyên tắc nghiệm thu

1. PySide6 6.12: giao diện không bị warning stylesheet hoặc font và không tự nạp SQLite/camera ở startup.
2. 4 workspace điều hướng bằng cả toolbar và menu/shortcut; không có rail trái chen ngang trung tâm.
3. Project Explorer vẫn mở kho thật, CRUD v2, Inspector, verify RAW; Nhật ký SQLite có thể mở từ workspace Xử lý.
4. Đảm bảo chạy 1366x768 và 125/150% DPI, không che nút; desktop thật là cổng nghiệm thu sau test Qt offscreen.
5. **Full regression** phải đạt 100%; không thay assertion của 06.3 để che lỗi. Hệ thống vẫn có 2 symlink skip dự kiến Windows.
6. Không sửa RAW, schema, camera, Orbbec/C++, số liệu.
