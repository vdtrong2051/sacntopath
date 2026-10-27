# Hướng dẫn phát triển và bảo trì ScanToPath

## Khi bắt đầu một thay đổi

1. Xác nhận nhánh, commit và trạng thái `git status --short` sạch.
2. Xác định mô-đun sở hữu tính năng qua [cấu trúc source](../architecture/CAU_TRUC_SOURCE.md), hợp đồng đầu vào/đầu ra và kiểm thử hiện có.
3. Phân tách chức năng cần làm khỏi các giả định chưa chứng minh (hệ tọa độ, đơn vị, pose, độ chính xác).
4. Đóng gói thay đổi nhỏ, có bảo vệ SHA/baseline và backup nếu áp patch lên Windows.
5. Chạy gate phạm vi, hồi quy và nghiệm thu UI/native tương ứng trước commit.

## Quy tắc thực hiện

- Thay đổi giao diện dùng Qt/PySide6, không import VTK native trong luồng giao diện.
- Tầng nghiệp vụ không nhận QWidget hoặc tự thao tác filesystem/SQL ngoài cổng giao tiếp.
- Camera và dữ liệu RAW phải được cô lập khỏi các bài thử chỉ xử lý UI/docs.
- Tệp tạo từ phép xử lý phải có nguồn, phiên bản và giới hạn độ tin cậy khi các phiên về sau hỗ trợ.
- R7-B chỉ tổ chức tài liệu; mọi lỗi runtime phát hiện mới phải tách thành công việc sửa mã có kiểm thử.

Tra cứu: [Quy chuẩn mã](QUY_CHUAN_CODE.md) · [Git](QUY_TRINH_GIT.md) · [Kiểm thử](QUY_TRINH_KIEM_THU.md).
