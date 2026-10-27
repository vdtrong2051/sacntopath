# Công nghệ và nguồn tham khảo — Trạng thái sử dụng

Tài liệu này phân biệt công nghệ **đã dùng trong source**, công nghệ dự kiến và nguồn nghiên cứu. Không tự coi một công nghệ được liệt kê trong roadmap là dependency đã tích hợp.

| Nguồn/công nghệ | Vai trò tại GĐ1 | Lưu ý |
|---|---|---|
| Qt 6 / PySide6 | Giao diện desktop thực tế | Kiểm tra DPI và vòng đời ứng dụng |
| Python 3.12 | Điều phối ứng dụng, lưu trữ và test | Không chạy native VTK nặng trong Qt main thread |
| C++20 / MSVC / CMake | Nguồn camera, native binding và CTest | Giữ phụ thuộc SDK riêng |
| OrbbecSDK v2.10.6 | Đọc Gemini 2 RGB-D | Kiểm phiên bản/firmware, không coi timestamp là sync proof |
| pybind11 | Cầu nối Python–C++ | Bộ đệm sở hữu riêng sau close |
| SQLite / SQLAlchemy | Metadata, audit và quan hệ Project | Không lưu nguyên MJPEG/Y16 trong DB |
| VTK | Render/mesh/picking trong child process | Shared-frame copy/ACK và recovery |
| Open3D, OpenCV, Eigen | Mục tiêu/thư viện trong định hướng xử lý hình học | Không suy ra mọi pipeline đã tích hợp vào Viewer |
| PCL, các mô hình AI 2D/3D, CAD từ ngôn ngữ | Nghiên cứu/đánh giá sau | Phải có A/B, hiệu năng, license, rủi ro phép đo |

Danh mục nghiên cứu và link chi tiết ban đầu được bảo toàn ở [bản tài nguyên lịch sử](https://github.com/vdtrong2051/sacntopath/blob/08ef856a04d61f20db1e26b2ceeb399065db902f/docs/archive/NGUON_THAM_KHAO/RESOURCE_MATRIX.md). Không xác nhận một mô hình AI hoặc tham số benchmark ngoài nguồn nếu chưa có lần kiểm chứng độc lập.
