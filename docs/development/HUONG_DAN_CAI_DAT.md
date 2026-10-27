# Hướng dẫn thiết lập môi trường phát triển Windows

**Phạm vi:** môi trường đã có để tiếp tục GĐ1; không tự cài camera/SDK hoặc sửa hệ thống.

## Điều kiện nền

- Windows, Python 3.12 trong `.venv`; Qt6/PySide6 theo phụ thuộc dự án.
- CMake và MSVC/C++20 cho mô-đun native; `build-orbbec` là thư mục build CTest đã có.
- OrbbecSDK v2.10.6 và pybind11 chỉ cần khi xây dựng/kiểm chứng acquisition bằng thiết bị hoặc native bindings. Không bắt buộc cắm Gemini 2 để đọc tài liệu, chạy pytest hay mở Viewer PLY/OBJ.

## Kiểm tra tại thư mục gốc repo

```powershell
$repo = 'E:\1_BigProject\scantopath\scantopath-software'
Set-Location $repo
& .\.venv\Scripts\python.exe --version
& .\.venv\Scripts\python.exe -m pytest --version
ctest --test-dir .\build-orbbec -C Release --output-on-failure
```

Mở phần mềm với Qt desktop thật (không đặt `QT_QPA_PLATFORM=offscreen`):

```powershell
& .\.venv\Scripts\python.exe -X utf8 -m scantopath.ui.main
```

Không chạy lệnh xóa build cache, migrate SQLite, ghi/đọc thiết bị thật hoặc nâng phiên bản SDK khi không có nhiệm vụ riêng. [Quy trình kiểm thử](QUY_TRINH_KIEM_THU.md) ghi rõ cổng tự động và HMI.
