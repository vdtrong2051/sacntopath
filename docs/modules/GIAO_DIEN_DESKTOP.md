# Mô-đun giao diện desktop

## Mục đích

Cung cấp bốn không gian làm việc trên Qt/PySide6, thanh điều hướng, các dock thông tin, bảng Thuộc tính dùng chung, trạng thái tác vụ/lỗi. Phần lắp ráp ở `src/scantopath/ui/shell/main_window.py` và các module giao diện riêng.

## Hành vi thực tế

- Khởi động ứng dụng không tự động mở Gemini 2, cơ sở dữ liệu hay VTK Render Host nếu chưa vào chức năng tương ứng.
- Trang Project làm việc qua `ProjectWorkspaceController`; Viewer được tạo chậm khi chuyển vào khu vực Kiểm tra 3D.
- Bảng Thuộc tính hiển thị Project metadata hoặc lựa chọn điểm/mặt thông qua cầu nối riêng; không đồng nhất hai miền dữ liệu.
- Công việc đọc file/render/IPC có timeout và đường xử lý sự cố; Qt main thread phục vụ điều hướng và hiển thị.

## Khi phát triển

Kiểm tra `objectName` đã dùng trong các Qt test, phản hồi khi chuyển workspace, trạng thái disabled/busy/error, DPI thực và tình huống đóng ứng dụng lúc còn worker. Không thay mã chỉ để vượt kiểm tra giới hạn số dòng. Các gate HMI/DPI 100–150% chưa được xem là PASS tổng thể tại R7-B.

Liên quan: [Quản lý dự án](QUAN_LY_DU_AN.md) · [Kiểm tra 3D](KIEM_TRA_3D.md) · [Kiểm thử](../development/QUY_TRINH_KIEM_THU.md).
