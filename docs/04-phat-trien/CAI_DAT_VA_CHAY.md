# Cài đặt, build và chạy ScanToPath trên Windows

> `owner: ENGINEERING_OWNER` · `as_of_commit: a847faebe54050cd6f8bc42cc882b3927ddabfe2` · `verified_at: 2026-10-28`  
> `scope: môi trường nhà phát triển Windows, Python/Qt, C++ mặc định và SDK tùy chọn` · `source-of-truth: pyproject.toml; cpp/CMakeLists.txt; src/scantopath/ui/main.py; scripts/verify.ps1` · `evidence_level: SOURCE_REVIEWED / WINDOWS_EXECUTION_NOT_TESTED`

## 1. Chọn đường chạy: không cần camera trước

ScanToPath là ứng dụng desktop Python 3.12 + Qt/PySide6; Viewer dùng VTK và Render Host ở tiến trình riêng. Native C++20 phục vụ lõi tối thiểu, hợp đồng gói RGB-D và tích hợp camera **opt-in**. Python gọi SQLite/RAW thông qua các module riêng; cài chương trình không có nghĩa phép đo hình học hoặc HMI thật đã được nghiệm thu. Các tuyến thao tác:

| Tuyến | Cần gì | Chạm vào thiết bị/dữ liệu? | Kết quả kỳ vọng |
|---|---|---|---|
| Kiểm tra Python + pytest | Python 3.12, venv, extras `test` | Không cắm camera | Kiểm tra các hợp đồng tự động |
| Desktop + Viewer | Extras `ui,viewer`, Windows có display | Không tự động mở camera; người dùng có thể chọn dữ liệu | Cửa sổ với 4 workspace, Viewer có thể mở PLY/OBJ bên ngoài |
| C++ mặc định | CMake >=3.22, C++20, MSVC | Không cần OrbbecSDK | Hai bài CTest không phụ thuộc camera |
| Gemini 2 native | Thiết bị/SDK chính xác, pybind11, CMake config, Python Dev.Module | **Có thể mở thiết bị** chỉ khi gọi lệnh riêng | Probe/binding tùy chọn, không phải bước Quick Start |

`pyproject.toml` quy định `numpy>=2,<3`, `pydantic>=2.7,<3`, `SQLAlchemy>=2,<3`; optional `ui` là `PySide6>=6.7,<7`, `viewer` là `vtk>=9.5,<10`, `test` là `pytest>=8`. **Đó là khoảng phiên bản, không phải lockfile**: hai máy cài vào ngày khác nhau có thể chọn bản khác nhau. Ghi lại `pip freeze` trong evidence khi tái hiện lỗi; không tự nâng SDK hoặc đổi dependency để chữa một test.

## 2. Kiểm tra máy mới và repository

Mở PowerShell, đặt đúng thư mục Git. Ví dụ đường dẫn dưới là của operator; thay nếu checkout khác.

```powershell
$repo = 'E:\1_BigProject\scantopath\scantopath-software'
Set-Location -LiteralPath $repo
git rev-parse --show-toplevel
git branch --show-current
git log -1 --oneline
git status --short
py -3.12 --version
cmake --version
ctest --version
```

**Kiểm tra:** root phải chính là repository, branch theo mốc được giao (DOC-03C: `feat/gd1-desktop-ui`), HEAD dự kiến `a847fae` trước khi áp pack; `git status --short` rỗng. Python 3.12 có thể được gọi bằng `py -3.12`. CMake/CTest chỉ cần cho nhánh native và `Full` runner; khi thiếu, dừng và ghi blocker, không tự đổi profile để nhận PASS. Nếu có MSVC: từ Developer PowerShell for VS dùng `cl` kiểm tra compiler; PowerShell thường không có `cl` trên PATH là chuyện có thể xảy ra, không mặc định compiler chưa cài.

## 3. Tạo môi trường Python và cài gói

Các lệnh **ghi** `.venv/` và tải/cài dependencies qua package index; không chạm RAW thật và không khởi tạo SQLite của người dùng. Nếu `.venv` đang dùng ổn định, không xóa/cài lại chỉ để thực hiện DOC-03C.

```powershell
Set-Location -LiteralPath $repo
py -3.12 -m venv .venv
if ($LASTEXITCODE -ne 0) { throw 'CREATE_VENV_FAILED' }
$py = Join-Path $repo '.venv\Scripts\python.exe'
& $py -m pip install -e '.[ui,viewer,test]'
if ($LASTEXITCODE -ne 0) { throw 'PYTHON_INSTALL_FAILED' }
& $py --version
& $py -m pip show PySide6 vtk SQLAlchemy pytest
if ($LASTEXITCODE -ne 0) { throw 'DEPENDENCY_AUDIT_FAILED' }
```

Với `.venv` có sẵn, chỉ chạy ba lệnh cuối để kiểm phiên bản. Kết quả kỳ vọng: interpreter 3.12.x, thông tin bốn package. Không `pip install` bằng Python hệ thống rồi chạy bằng `.venv`; hai môi trường đó khác nhau. Nếu bị chặn mạng hoặc wheel VTK không tương thích, ghi lỗi exact của pip và phiên bản interpreter, không tự chuyển sang Python 3.14.

## 4. Chạy desktop thật và kiểm tra đầu vào

```powershell
Set-Location -LiteralPath $repo
Remove-Item Env:QT_QPA_PLATFORM -ErrorAction SilentlyContinue
& $py -X utf8 -m scantopath.ui.main
if ($LASTEXITCODE -ne 0) { throw 'DESKTOP_EXIT_NONZERO' }
```

Ứng dụng chạy Qt event loop tới khi đóng cửa sổ, nên PowerShell chỉ quay lại sau khi thoát. Điểm vào là `src/scantopath/ui/main.py::main`, lớp cửa sổ `src/scantopath/ui/shell/main_window.py::ScanToPathMainWindow`. Có bốn workspace theo README; có thể chạy không cắm camera. Để đọc PLY/OBJ, dùng thao tác Viewer và xem [sổ tay Viewer](../03-modules/VIEWER_3D.md); việc có tệp từ bên ngoài **không** cho phép suy ra đơn vị mét, hệ tọa độ robot hoặc tự tái tạo từ RAW. Không dùng `QT_QPA_PLATFORM=offscreen` cho kiểm tra mắt thật, DPI, GPU, nhấp-chọn.

Nếu lỗi `ModuleNotFoundError`, kiểm `$py` và editable install; nếu lỗi Qt platform plugin, ghi OS, `QT_QPA_PLATFORM`, phiên bản PySide6 và đường plugin trước khi sửa environment. Nếu Viewer không lên, kiểm `vtk` cùng `.venv`, xem log Render Host; không import/chạy VTK nặng trực tiếp trong Qt GUI thread để né lỗi.

## 5. Build và CTest C++ mặc định, không mở camera

`cpp/CMakeLists.txt` thiết lập C++20, `scantopath_core`, `scantopath_rgbd_contract`, hai CTest `core_smoke` và `rgbd_contract_smoke`; ba tùy chọn `SCANTOPATH_BUILD_ORBBEC_PROBE`, `SCANTOPATH_BUILD_ORBBEC_SOURCE`, `SCANTOPATH_BUILD_PYTHON_BINDINGS` mặc định `OFF`. Ví dụ tạo **build mới** để không đụng cache của `build-orbbec` vốn được R8 Full sử dụng:

```powershell
Set-Location -LiteralPath $repo
cmake -S .\cpp -B .\build-doc03c-core -DBUILD_TESTING=ON `
  -DSCANTOPATH_BUILD_ORBBEC_PROBE=OFF `
  -DSCANTOPATH_BUILD_ORBBEC_SOURCE=OFF `
  -DSCANTOPATH_BUILD_PYTHON_BINDINGS=OFF
if ($LASTEXITCODE -ne 0) { throw 'CMAKE_CONFIGURE_FAILED' }
cmake --build .\build-doc03c-core --config Release
if ($LASTEXITCODE -ne 0) { throw 'CPP_BUILD_FAILED' }
ctest --test-dir .\build-doc03c-core -C Release --output-on-failure
if ($LASTEXITCODE -ne 0) { throw 'CTEST_FAILED' }
```

Tác dụng phụ: tạo thư mục build mới trong checkout (không phải RAW). Trước khi commit, **không stage** build directory. `Full` runner **không dùng** `build-doc03c-core`: nó gọi `ctest --test-dir <repo>/build-orbbec -C Release --output-on-failure`. Nếu chưa có cache/binary ở `build-orbbec`, cần chủ động cấu hình/build đúng profile không camera trong chính thư mục đó hoặc xin xác nhận operator trước khi thay thế cache native đã cấu hình SDK. `Full` bắt buộc ít nhất hai CTest PASS; không bỏ qua bước chỉ vì docs đổi.

## 6. Gemini 2 và native bindings: chỉ khi được giao riêng

Bản source có đường `cpp/src/acquisition/orbbec_camera_source.cpp`, `cpp/python/orbbec_bindings.cpp` và `src/scantopath/acquisition/native.py`. OrbbecSDK v2.10.6 là baseline SDK được ghi trong hồ sơ; bản `cpp/CMakeLists.txt` hiện dùng `find_package(OrbbecSDK CONFIG REQUIRED)` khi bật tùy chọn và `find_package(pybind11 CONFIG REQUIRED)` cho bindings. `SCANTOPATH_BUILD_PYTHON_BINDINGS=ON` **yêu cầu** `SCANTOPATH_BUILD_ORBBEC_SOURCE=ON`; chọn `Python3_EXECUTABLE` trỏ đúng `.venv` và cấu hình CMake package của SDK/pybind11 theo **đường cài thực trên máy**.

Không có lệnh build SDK một phát dùng được cho mọi máy vì `OrbbecSDK_DIR`, `pybind11_DIR`, toolchain và DLL runtime phải được xác minh cục bộ. Không tự copy `.pyd`/DLL, nâng firmware, mở Gemini 2, chạy `capture_once --once` hay Orbbec probe trong cổng tài liệu. Khi được duyệt: ghi SDK/firmware, USB, compiler, Python, CMake Cache, đường DLL, môi trường process, quyền thiết bị và bằng chứng runtime; chạy probe trong phiên riêng, không đồng thời chiếm camera từ ứng dụng khác.

## 7. CLI an toàn và CLI có tác dụng phụ

`src/scantopath/cli.py` hỗ trợ `scantopath demo --output ...` để **ghi fixture tổng hợp** và `scantopath verify --output ...` để kiểm vùng dữ liệu đó. Nếu cần thử, dùng một thư mục tạm **mới, nằm ngoài repo và không chứa RAW thật**. `src/scantopath/acquisition/capture_once.py` có `--verify` để đọc/kiểm checksum capture đã lưu nhưng `--once` mở camera và ghi RAW nên **không** dùng trong bài thử cài đặt. `src/scantopath/metadata/cli.py` có thể tạo SQLite nếu root trống ngay cả ở lệnh tưởng như chỉ đọc; không chạy để "xem thử" vào root dữ liệu người dùng. `src/scantopath/storage/numbered_cli.py migrate --confirm`, `assign*` và `src/scantopath/storage/legacy_migration_cli.py apply/rollback --confirm` là nghiệp vụ thay đổi dữ liệu, không thuộc Quick Start.

## 8. Troubleshooting ngắn gọn

| Hiện tượng | Kiểm gì trước | Xử lý an toàn |
|---|---|---|
| `py -3.12` không tìm thấy | `py --list`, đường cài Windows | Cài đúng 3.12 hoặc chặn công việc; không đổi yêu cầu dự án |
| Import PySide6/vtk thất bại | `& $py -m pip show ...` | Cài đúng extras trong venv; không sửa source để lách |
| `ctest` báo `No tests were found` | CMake configure có `BUILD_TESTING=ON` không; đúng thư mục build | Cấu hình/build theo chủ ý, không ghi PASS |
| Full không thấy `build-orbbec` | Cache/exe CTest của operator | Báo blocker, không tự xóa cache hoặc hạ Full xuống Quick |
| Render Host mất/không mở tệp | log host, đường PLY/OBJ, đơn vị nguồn, revision | Xem [Viewer](../03-modules/VIEWER_3D.md), không ép Qt main thread xử lý VTK |
| Cảm biến bận/DLL sai | Driver/SDK/process đang giữ camera | Dừng probe, thu evidence, không tự reset thiết bị khi chưa được giao |

## 9. Giới hạn đã biết và đường đọc tiếp

Đây là sổ tay dựa trên source tại commit ghi đầu trang; chưa có phép chạy trên máy Windows trong lần biên soạn này (`WINDOWS_EXECUTION_NOT_TESTED`). CMake mặc định có hai smoke test nhưng không xác nhận mọi biến thể MSVC. `pip` extras không đảm bảo binary wheel ở mọi môi trường. Mọi kết luận về giao diện DPI/GPU, closed-while-busy, present latency, camera thực hay độ chính xác đo đạc phải xem [kiểm thử & nghiệm thu](KIEM_THU_VA_NGHIEM_THU.md) và biên bản có evidence, không rút ra từ build thành công. 
