# Tổng quan kiến trúc hiện hành của ScanToPath

**Mốc kiểm kê:** R7-A `8e37eba`; **phạm vi:** các thành phần đã có từ GĐ0 đến Viewer R5.3, không phải kiến trúc dự đoán cho các phiên tương lai.

## 1. Kiến trúc tổng thể

```text
Ứng dụng Desktop — Qt 6 / PySide6
  ├─ Shell: điều hướng, bốn không gian làm việc, dock và vòng đời cửa sổ
  ├─ Quản lý dự án: controller → dịch vụ ứng dụng → SQLite/RAW registry
  └─ Kiểm tra 3D: controller → yêu cầu bất đồng bộ → VTK Render Host
                                      │
                                IPC, shared memory,
                                copy RGB rồi ACK

Nguồn Camera Gemini 2 (GĐ0) → C++20/OrbbecSDK → pybind11
                                → RAW MJPEG/Y16 + siêu dữ liệu
```

ScanToPath được tổ chức theo hướng **Modular Monolith + Presentation Controller**, phân tách `domain`, `application`, `infrastructure`, `presentation` trong các mô-đun có áp dụng. Đây là định hướng được thực hiện từng bước; không khẳng định mọi tệp đều đã đạt toàn bộ nguyên tắc SOLID.

## 2. Hai ranh giới quan trọng

**Qt ↔ VTK:** VTK vận hành trong tiến trình Render Host cô lập, không import VTK native trực tiếp vào luồng chính của Qt. Camera/orbit/pan/zoom, nạp PLY/OBJ và picking gửi qua phiên bất đồng bộ. Frame RGB chuyển qua bộ nhớ dùng chung, được sao chép trước ACK. Các revision của scene, input, frame và SHA-256 nguồn giúp từ chối kết quả cũ.

**Project ↔ lưu trữ:** SQLite lưu metadata và tham chiếu dữ liệu RAW, không nhúng ảnh vào các bảng. RAW của GĐ0 giữ byte gốc với manifest SHA-256; các thao tác mở Viewer không tự tạo Project/ScanSession/Capture hay biến PLY bên ngoài thành dữ liệu đã đo.

## 3. Công nghệ theo trách nhiệm

| Lớp | Công nghệ và nhiệm vụ |
|---|---|
| Giao diện | Python 3.12, Qt 6 / PySide6 |
| Dịch vụ ứng dụng | Python, DTO và điều phối tác vụ |
| Metadata | SQLite + SQLAlchemy |
| Camera RAW | C++20, OrbbecSDK v2.10.6, pybind11 |
| Hiển thị | VTK trong tiến trình con, IPC và shared memory |
| Kiểm thử | pytest, CTest, Architecture Guard, Quality Gate |

Thư viện Open3D/Eigen/OpenCV trong kế hoạch kỹ thuật không có nghĩa pipeline đo đạc, đăng ký nhiều góc hoặc đường dẫn robot đã hoạt động trong Viewer.

## 4. Trạng thái và giới hạn

- **Có bằng chứng tự động R6:** Python/Qt 618 PASS, 3 SKIP có lý do, CTest 2/2, thử hình học PLY/OBJ, vận chuyển frame, native Viewer, benchmark renderer thường trú.
- **Chưa nghiệm thu tổng thể:** thử lỗi C++ thật khi bận, DPI 100/125/150, GPU/VRAM, thời điểm ảnh thực lên màn hình, HMI tổng hợp.
- **Không tự nhận tính đo lường:** Lưới Oxy và gizmo XYZ là tham chiếu hiển thị; PLY/OBJ ngoài chưa có bằng chứng thì `units/coordinate_frame=unknown`.

Đọc tiếp: [Cấu trúc source](CAU_TRUC_SOURCE.md) · [Ranh giới mô-đun](RANH_GIOI_MODULE.md) · [Luồng dữ liệu](LUONG_DU_LIEU.md) · [Nghiệm thu](../acceptance/GD1.md).
