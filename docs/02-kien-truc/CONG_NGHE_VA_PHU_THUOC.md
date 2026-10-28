# Công nghệ và phụ thuộc ScanToPath — cái gì đang dùng, cái gì chỉ dự kiến

> `owner: ARCHITECTURE_OWNER` · `as_of_commit: 7a0df7c5b596ff8750bf91f47310067c53a8b204` · `verified_at: 2026-10-28`  
> `scope: code, pyproject và CMake tại commit nguồn; không là báo cáo kiểm tra version đã cài trên từng PC` · `evidence_level: SOURCE_REVIEW`.

## 1. Ba loại thông tin cần phân biệt

1. **Được khai báo:** có trong `pyproject.toml` hoặc `cpp/CMakeLists.txt`; không có nghĩa đã cài trên máy Windows cụ thể.
2. **Được sử dụng trong code:** có import/call/target trong source. Phần mềm có thể dùng VTK cho Viewer mà chưa dùng Open3D cho pipeline geometry.
3. **Được đo/nghiệm thu:** có log/receipt cho trường hợp và điều kiện cụ thể; benchmark renderer không phải chứng nhận FPS màn hình hay GPU/VRAM.

Bảng dưới mô tả code GĐ0/GĐ1. Muốn biết dependency đã cài thật, kiểm tra `.venv` trên máy đang dùng; không suy ra từ tài liệu hoặc commit.

## 2. Công nghệ đang sử dụng

| Vai trò | Công nghệ và ràng buộc | Trong repository | Điểm kỹ thuật cần nhớ |
|---|---|---|---|
| Ngôn ngữ orchestration | Python `>=3.12` (Windows phát triển theo 3.12) | `src/scantopath/` | Heavy native/I/O không ở Qt event loop |
| UI | Qt 6 / PySide6 `>=6.7,<7` | `ui/main.py`, `ui/shell/`, `modules/*/presentation` | Phụ thuộc optional group `ui` |
| Renderer | VTK `>=9.5,<10` | `modules/viewer3d/infrastructure/` | Phụ thuộc optional group `viewer`; process VTK cô lập |
| RAW/array | NumPy `>=2.0,<3` | `storage/`, `acquisition/`, fixture | Không resize/align RAW tự động |
| Validation | Pydantic `>=2.7,<3` | `domain/raw_rgbd.py` | Frozen/strict schema v2; không nhầm measured/validated |
| Metadata | SQLAlchemy `>=2.0,<3` + SQLite | `metadata/`, `project_workspace/infrastructure` | SQLite ngoài byte RAW, migration rõ ràng |
| Acquisition native | C++20, MSVC, CMake | `cpp/`, `_scantopath_native` khi bật build | OrbbecSDK integration opt-in; không bắt buộc chạy Viewer file ngoài |
| Python-C++ bridge | pybind11 | `cpp/python/orbbec_bindings.cpp` | CMake option `SCANTOPATH_BUILD_PYTHON_BINDINGS=ON` |
| SDK camera | OrbbecSDK v2.10.6 trong hồ sơ đã thử | Adapter `acquisition`, `cpp/src/acquisition` | SDK runtime/bin phải được cấu hình riêng, không cài từ `pyproject` |
| Kiểm thử Python | pytest `>=8` | `tests/`, `scripts/verify.ps1` | Optional group `test`; JUnit+SKIP policy |
| Kiểm thử C++ | CTest (CMake) | `cpp/tests/`, `cpp/CMakeLists.txt` | `core_smoke`, `rgbd_contract_smoke` không yêu cầu camera |

**Tính tùy chọn thực tế:** `pyproject.toml` chỉ khai báo tối thiểu `numpy`, `pydantic`, `SQLAlchemy`; PySide6, VTK, pytest nằm trong extras `ui`, `viewer`, `test`. Không kết luận “Viewer bị thiếu code” chỉ vì người dùng chưa cài `vtk` vào `.venv`.

## 3. Công nghệ được cân nhắc hoặc thuộc giai đoạn sau

| Công nghệ | Dùng để làm gì về sau? | Trạng thái trong bản desktop đang mô tả |
|---|---|---|
| Open3D | Backprojection, point-cloud filters, normals, registration/fusion | Định hướng GĐ2/GĐ3, **không phải** pipeline đã tích hợp GĐ1 |
| OpenCV | Giải mã ảnh, distortion/rectification, hình học ảnh | Định hướng các phiên replay/projection; không tự suy đã có pipeline |
| Eigen | Hình học và transform trong C++ | Công nghệ target khi core nặng cần; không coi là bắt buộc với UI hôm nay |
| vcpkg | Quản lý dependency C++ | Chỉ khi dependency native yêu cầu; CMake hiện dùng tùy chọn OrbbecSDK |
| PCL | Phương án thay thế Open3D | Candidate benchmark, không chạy đồng thời hai geometry core mà thiếu lý do |
| RF-DETR, YOLO, SAM, DINO và các AI khác | Detection/segmentation/feature assist | Nghiên cứu GĐ5+, cần license/dữ liệu/VRAM/latency benchmark riêng |
| CAD/robot/CAM backend | Đích ứng dụng kỹ thuật | Ngoài scope mã GĐ1; không tự biến path planned thành trajectory |

Các tên công nghệ trong roadmap không được đưa vào tài liệu cài đặt như dependency bắt buộc nếu code hiện không gọi tới chúng.

## 4. Cài môi trường đúng vai trò trên Windows

**Chạy tại root repository**; các lệnh chỉ cài package vào `.venv`, không mở SDK hoặc camera:

```powershell
py -3.12 -m venv .venv
& .\.venv\Scripts\python.exe -m pip install -e ".[ui,viewer,test]"
& .\.venv\Scripts\python.exe -m pip show PySide6 vtk pytest
& .\.venv\Scripts\python.exe -X utf8 -m scantopath.ui.main
```

Nếu chỉ cần schema/metadata/RAW offline, `pip install -e .` cài nhóm cơ bản. Nếu chỉ cần chạy Qt không mở Viewer 3D, có thể chọn extra `ui` riêng; tuy nhiên vào trang Viewer cần thêm VTK cho renderer trên màn hình thật. Trên headless CI, fallback Qt offscreen không thay phép thử VTK native thực địa.

**C++ không camera (sau khi có MSVC + CMake):**

```powershell
cmake -S cpp -B build-orbbec -A x64
cmake --build build-orbbec --config Release
ctest --test-dir build-orbbec -C Release --output-on-failure
```

Kết quả kỳ vọng của cấu hình có `BUILD_TESTING=ON`: hai test `core_smoke` và `rgbd_contract_smoke`. Nếu dùng generator không hỗ trợ `-A x64`, chọn đúng generator/toolchain của máy; không sửa source để bỏ kiểm thử. `CTest` không xác nhận camera thật.

## 5. Khi nào cần Orbbec SDK và binding?

Chỉ khi người phát triển cần camera one-shot hoặc kiểm tra native binding. CMake cung cấp các cờ **mặc định OFF**:

- `SCANTOPATH_BUILD_ORBBEC_PROBE`
- `SCANTOPATH_BUILD_ORBBEC_SOURCE`
- `SCANTOPATH_BUILD_PYTHON_BINDINGS`

Bật binding yêu cầu source Orbbec đã bật và `find_package(OrbbecSDK)`/`find_package(pybind11)` thành công. Phải đối chiếu ABI Python/C++ và thư mục DLL SDK của máy. Không đưa đường dẫn SDK cá nhân lên README như đường dẫn portable. `--self-test` và `--once` là hai việc khác nhau; `--once` **mở thiết bị và ghi dữ liệu mới** khi chạy qua `capture_once`.

## 6. Rendering và đánh đổi kiến trúc

Tại R4.5, một lần so sánh VTK nhúng trong Qt với host resident độc lập dẫn đến lựa chọn **host B có điều kiện**. Code GĐ1 có `CoalescingRenderSession`, IPC/shared RGB24 frame và ACK. Nó giảm coupling của event loop/VTK native, đổi lại có chi phí process startup, shared memory, giao thức và quản lý shutdown/stale frames.

**Không được diễn giải:** chọn B có điều kiện ≠ production crash-proof; renderer benchmark 1K/100K/1M ≠ FPS màn hình; GPU/VRAM chưa được chốt bằng số đo thực. Native probe chỉ là một phép thử tương tác trong phạm vi của nó.

## 7. Quy tắc nâng dependency

Chỉ nâng SDK/PySide6/VTK/Python hoặc thêm Open3D/OpenCV/PCL khi có task, lý do kỹ thuật, phiên bản dự kiến, ảnh hưởng API/ABI, kiểm tra license, benchmark khi phù hợp và đường rollback. Với camera, đối chiếu firmware/SDK/USB profile và quyền DLL; với Qt/VTK, chạy full regression và HMI thực nếu thay interaction/native lifecycle.

Dẫn nguồn để xác minh: `pyproject.toml`, `cpp/CMakeLists.txt`, `src/scantopath/ui/shell/viewer_bootstrap.py`, `src/scantopath/modules/viewer3d/infrastructure/resident_poc/`, [Kiến trúc](KIEN_TRUC_HE_THONG.md) và [Phạm vi năng lực](../01-tong-quan/PHAM_VI_VA_NANG_LUC.md). Các quyết định công nghệ từ giai đoạn cũ có tại [Technology Scope R7](CONG_NGHE_VA_PHU_THUOC.md); văn bản đó được dùng như nguồn lịch sử và có bảng Viewer chưa cập nhật, **không** dùng làm trạng thái code ở commit này.

**Giới hạn:** đây là danh mục dependency từ source, không phải output của `pip freeze`, `ctest` hoặc bản kiểm kê driver GPU trên máy người vận hành.
