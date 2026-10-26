# ScanToPath R3.3 — Contextual Inspector

## Mục tiêu

- Hiển thị ngữ cảnh từ **Project / Specimen / ScanSession / Capture / ProcessingRun** bằng `ProjectLoadBundle` và các DTO bất biến hiện hành, không đọc SQLite trực tiếp trong Qt.
- Tách **header đối tượng → separator 1px → bảng metadata → separator thao tác**, đồng nhất thiết kế R3.1–R3.2, không chồng các đường kẻ lên chữ.
- Loại bỏ vùng action chết: chỉ hiện nút liên quan đến loại đối tượng; quyền ghi vẫn do `ProjectWorkspaceController` quyết định.
- Giữ API `set_selection`, `set_store_fields`, `set_capture_inspection`, `set_actions`, `set_verify_capability` và objectName cũ để các tính năng 07.x không thay đổi.

## Nguồn dữ liệu và giới hạn

| SelectionRef | Metadata bổ sung từ DTO | Hành động có thể khả dụng |
| --- | --- | --- |
| Project | Mã, tên, mô tả, thời gian tạo/cập nhật, trạng thái lưu trữ | Sửa metadata (SQLite v2) |
| Specimen | Mã, vật mẫu, mô tả, Project cha, thời gian, lưu trữ | Sửa metadata (SQLite v2) |
| ScanSession | Mã, tên phiên, trạng thái, vật mẫu cha, thời gian, lưu trữ | Sửa/đóng phiên khi hợp lệ |
| Capture | Mã, loại, RAW schema, trạng thái lưu trữ, phiên liên kết, thời điểm đăng ký | Kiểm tra RAW theo yêu cầu |
| ProcessingRun | Mã, công đoạn, thuật toán, trạng thái, tham chiếu đầu vào/đầu ra, thời điểm | Chỉ đọc ở R3.3 |

`StorageRef.relative_path` có thể chỉ là đường dẫn logic. `output_files` là tham chiếu, không xác thực sự tồn tại. Trạng thái RAW không chứng minh độ chính xác hình học hoặc tọa độ metric. Không mở thiết bị/camera và không tự chạy các thuật toán xử lý.

## Kiểm thử và nghiệm thu

1. Khởi động chưa mở kho: Inspector ghi “Chưa chọn đối tượng”; không có button chiếm chỗ trống.
2. Chọn Project/Specimen/Session: header, metadata, quyền thao tác theo loại đối tượng và kho v1/v2 đúng thực tế.
3. Chọn Capture: RAW chưa kiểm tra không bị tô thành “Đã kiểm tra”; bấm Kiểm tra RAW theo yêu cầu mới cập nhật status hiện tại.
4. Chọn ProcessingRun: đọc stage/algorithm/state/reference, không có nút chỉnh sửa giả.
5. Đổi kho, bỏ chọn hoặc đổi đối tượng: không để lộ metadata và trạng thái RAW của selection cũ.
6. Toàn màn hình ở Windows: header/separator/bảng/action phân lớp rõ, không thiếu/đè chữ và không ảnh hưởng Task Dock.
7. Focused + full pytest, Architecture/Quality gate, kiểm chứng UI Qt và HMI theo quy trình. Native/CTest không bắt buộc chạy lại cho patch thuần presentation; không có source GĐ0/C++ bị sửa.

**Nghiệm thu:** chỉ publish sau khi Windows automated tests và HMI thực tế được operator chấp nhận.
