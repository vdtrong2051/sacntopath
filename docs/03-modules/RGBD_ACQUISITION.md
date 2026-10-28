# RGB-D Acquisition — Thu nhận dữ liệu màu và độ sâu từ Gemini 2

> **owner:** `acquisition` + `cpp/acquisition` · **as_of_commit:** `0557c0d4fed9a3df3b180fc9872c6d3293b5f0d5` · **verified_at:** 2026-10-28  
> **scope:** contract và one-shot acquisition GĐ0/PRE-04, không phải hệ quét tự động · **implementation:** IMPLEMENTED (one-shot, SDK opt-in) · **evidence:** mã nguồn Git, kiểm thử tổng hợp, hồ sơ PRE-06 theo log người vận hành; **không** có kết quả chạy camera mới trong DOC-03B.  
> **source-of-truth:** `src/scantopath/acquisition/`, `src/scantopath/domain/raw_rgbd.py`, `cpp/`; **manual/metric verification:** NOT_TESTED trong đợt biên soạn này.

## 1. Mục đích và tình huống sử dụng

Mô-đun này lấy **một cặp khung hình RGB-D nguyên gốc** từ Orbbec Gemini 2, chuyển thành đối tượng Python bất biến có nguồn gốc rõ ràng và trả về cho lớp ghi RAW. Nó giải quyết việc thu nhận/sao chép/kiểm tra dữ liệu cảm biến, **không** xây dựng đám mây điểm hay tìm vị trí camera trong không gian. Ví dụ: operator muốn ghi một lần đo để về sau phát lại và nghiên cứu hiệu chuẩn; thiết bị chỉ được mở khi gọi lệnh thu nhận thật.

Ba thứ phải được tách biệt: (i) pixel gốc, (ii) metadata do SDK báo và (iii) đánh giá độ chính xác hình học. Một frame đến từ camera thật có `measured=True` nhưng **không** mặc nhiên `metric_validated`, đã đồng bộ exposure hay có `T_world_camera`.

## 2. Phạm vi chạy được và chưa có

| Năng lực | Hiện trạng ở baseline | Điều không được suy diễn |
|---|---|---|
| Native C++20 CameraSource OrbbecSDK v2 | Có mã nguồn, CMake tùy chọn; GĐ0 có hồ sơ one-shot Windows | Không tự bật thiết bị khi chạy desktop |
| Cầu nối pybind11 → Python | Có mã `_scantopath_native`, nạp khi gọi `load_native()` | Không là dependency bắt buộc để xem PLY/OBJ |
| RAW v2 MJPEG/Y16 và metadata | Có validation Pydantic và kiểm payload, byte được sao chép | Chưa align/resize/đổi encoding tự động |
| Chụp một lần và kiểm file đã lưu | CLI `--once` và `--verify` | Không phải streaming UI Capture đầy đủ |
| Pose, multi-view, calibration metrology, robot control | **Chưa triển khai thành pipeline desktop** | Không xem timestamp delta là đồng bộ hóa được chứng minh |

Cấu hình phần cứng/cơ khí hiện hành cấp hệ thống phải được xác nhận bằng quyết định riêng. Contract cũ mang `camera_pose=None` vì **PRE-02 không có pose**; không dùng chú thích `handheld` trong file lịch sử để bác bỏ một cấu hình cơ khí mới chưa nhập vào source.

## 3. Kiến trúc và source có thật

```text
Operator: python -m scantopath.acquisition.capture_once --once
  → capture_once.main() / validate session + specimen
  → orbbec_adapter.capture_one_raw()
  → native.load_native() / OrbbecSDK DLL + _scantopath_native (opt-in)
  → CameraSource C++: open → capture → validate → close
  → orbbec_adapter.raw_capture_from_native()
  → RawRgbdCaptureMetadataV2 + RawRgbdCapture(owned bytes)
  → SessionStore.commit_raw() → SessionStore.read_raw() → JSON summary
```

| Thành phần | Trách nhiệm |
|---|---|
| `cpp/include/scantopath/acquisition/orbbec_camera_source.hpp`, `cpp/src/acquisition/orbbec_camera_source.cpp` | CameraSource native, sở hữu vòng đời SDK |
| `cpp/src/acquisition/rgbd_validation.cpp` | Kiểm hợp đồng packet RGB-D ở C++ |
| `cpp/python/orbbec_bindings.cpp` | Xuất interface `_scantopath_native` cho Python |
| `src/scantopath/acquisition/native.py` | Nạp extension/DLL tường minh; `--self-test` không cần mở camera |
| `src/scantopath/acquisition/orbbec_adapter.py` | Ánh xạ metadata SDK và sao chép byte gốc thành domain DTO |
| `src/scantopath/acquisition/raw_rgbd.py` | `RawRgbdCapture`, kiểm byte bất biến, kích thước payload |
| `src/scantopath/domain/raw_rgbd.py` | `RawRgbdCaptureMetadataV2` và các kiểu stream/intrinsics/distortion/extrinsics |
| `src/scantopath/acquisition/capture_once.py` | CLI điều phối capture–commit–readback hoặc verify offline |
| `src/scantopath/acquisition/sources.py` | `SyntheticSource`, `FrameBundle` hợp đồng legacy v1; **khác** RAW v2 |

## 4. Đầu vào, đầu ra và hợp đồng dữ liệu

| Dữ liệu | Kiểu/đơn vị | Điều kiện/nguồn |
|---|---|---|
| `session_id`, `specimen_id` | ASCII ID | Bắt buộc cho `--once`, kiểm trước khi mở camera |
| `color_mjpeg` | `bytes`, JPEG/MJPEG | SOI marker; chiều dài khớp `color.payload_size_bytes`, không giữ vùng nhớ SDK |
| `depth_y16_le` | `bytes`, uint16 little-endian | Đúng `depth.width * depth.height * 2` byte |
| `color`, `depth` | `RawStreamInfo` | MJPEG và Y16; kích thước, frame index, timestamp SDK (µs) độc lập |
| intrinsics | `fx, fy, cx, cy` và kích thước từng stream | Không tráo calibration depth/color |
| distortion | `sdk_model`, 8 coefficients | Giữ đúng thứ tự/mô hình SDK, không tự đổi sang OpenCV |
| `depth_to_color.translation_mm` | **mm** | Không tự đọc thành m; rotation 3×3 theo hàng |
| `depth_scale_m_per_unit` | **m/unit** | Chỉ áp dụng khi giải mã điểm sâu, không sửa giá trị Y16 RAW |
| `alignment_mode` | bắt buộc `disabled` | RAW v2 chưa đăng ký pixel RGB↔depth |
| `timestamp_domain` | `sdk_reported_unverified` | Chênh lệch timestamp là thông tin chẩn đoán, không chứng nhận sync |
| `coordinate_frame`, `camera_pose` | `depth_optical`, `None` | Không tự suy ra world frame hay pose camera |

**Chú ý hai dạng dữ liệu cũ:** `FrameBundle` của `SyntheticSource` phục vụ hợp đồng v1 đã registered vào lưới depth, còn `RawRgbdCapture` của PRE-02/04 giữ **hai lưới không đồng kích thước**. Không truyền RAW v2 vào `SessionStore.commit()` v1 hoặc mô tả chúng là giống nhau.

## 5. Luồng chạy tốt từ đầu đến cuối

1. Operator chọn thư mục dữ liệu ra và ID phiên/mẫu; CLI xác thực ID **trước** khi mở phần cứng.
2. Adapter gọi native khi có lệnh; Windows dùng thư mục `SCANTOPATH_ORBBEC_SDK_BIN` nếu DLL không có sẵn trong cơ chế nạp hiện hành. `load_native()` không mở sensor khi chỉ import.
3. Native mở CameraSource, nhận hai buffer cùng metadata SDK và kiểm tính hợp lệ; C++ đóng camera trước khi trả packet cho Python (quyền sở hữu dữ liệu đã sao chép).
4. Adapter tạo DTO v2; Pydantic từ chối sai encoding, shape, đơn vị scale hoặc stream không cùng loại đã yêu cầu. `RawRgbdCapture` chỉ nhận `bytes` sở hữu riêng.
5. `capture_once.py` gọi `SessionStore.commit_raw()` rồi `read_raw()` để xác minh roundtrip. Báo cáo JSON thể hiện path, kích thước, timestamp delta **diagnostic only**, checksum verified.
6. Metadata SQLite/Project là khâu riêng; `commit_raw()` **không tự tạo** Project, Session, mã đánh số hoặc ProcessingRun.

## 6. Bất biến và ranh giới

- Không thay đổi byte MJPEG/Y16 sau khi nhận; không giải nén rồi nén lại trước khi commit RAW.
- Không coi `measured=True` là chứng minh sai số hoặc datum.
- Không sinh `camera_pose` chỉ từ RGB-D một shot; không biến gợi ý chuyển động thành pose thực.
- Không dùng ảnh màu/độ sâu chung lưới khi `alignment_mode=disabled`.
- Không lưu serial camera trong log/public evidence theo mặc định; không đưa RAW thật vào Git.
- Native SDK là option CMake; `pyproject.toml` không tự build `_scantopath_native`.

## 7. Vòng đời, trạng thái và hủy

```text
UNLOADED --load_native()--> BINDING_READY --explicit capture--> CAMERA_OPEN
CAMERA_OPEN --packet/validation--> CAMERA_CLOSED --copy--> PYTHON_RAW_V2
                  └─ lỗi → close/release → ERROR (không xuất capture giả)
```

One-shot không phải API streaming/cancellation cho desktop. Không gọi hành động `--once` khi OrbbecViewer hoặc tiến trình khác đang giữ thiết bị. Nếu thoát bất thường giữa các bước, xử lý tồn dư thư mục `.partial` thuộc Storage, không phải trách nhiệm SDK.

## 8. Lỗi, phục hồi và biểu hiện

| Nguyên nhân | Lỗi/triệu chứng dự kiến | Cách phục hồi an toàn | Kiểm thử |
|---|---|---|---|
| `SCANTOPATH_ORBBEC_SDK_BIN` không hợp lệ | `RuntimeError` về OrbbecSDK.dll | Kiểm lại thư mục `bin`, không chép DLL tùy tiện | `tests/contracts/camera/test_native_loader.py` |
| `_scantopath_native` chưa build | Import/native load failure khi gọi thật | Build extension theo CMake tùy chọn | native loader/CTest |
| Không đúng MJPEG/Y16, aligned packet | `ValueError` từ adapter/DTO | Kiểm profile và metadata; không ép sửa dtype để bỏ guard | `tests/contracts/camera/test_pre04_orbbec_adapter.py` |
| Depth bytes/shape sai | validation error | Bỏ capture hỏng; không commit | `tests/unit/raw/test_raw_rgbd_contract.py` |
| Không cắm/không truy cập camera | lỗi native capture | Đóng ứng dụng chiếm camera, kiểm USB/driver, thử lại có chủ ý | thử sensor thật (không tự động) |
| Timestamp delta lớn | báo cáo diagnostic; không tự FAIL phép đo | Thẩm định clock domains ở giai đoạn calibration | chưa có gate metrology |

## 9. Ví dụ an toàn, có thể chạy lại

**Tại gốc repository Windows, đã kích hoạt `.venv`.** Ví dụ đầu tiên không mở thiết bị và không ghi RAW:

```powershell
& .\.venv\Scripts\python.exe -X utf8 -m pytest -q `
  tests/unit/raw/test_raw_rgbd_contract.py `
  tests/contracts/camera/test_pre04_orbbec_adapter.py
```

Kết quả mong đợi: pytest không lỗi; không sinh capture thật. Để **kiểm tệp đã lưu**, cần nhập đường dẫn Capture v2 thực và output root tương ứng (đọc/kiểm hash, không tạo capture mới):

```powershell
& .\.venv\Scripts\python.exe -X utf8 -m scantopath.acquisition.capture_once `
  --verify '<CAPTURE_DIR_V2>' --output '<DATA_ROOT>'
```

**Lệnh có tác dụng phụ phần cứng** (không thuộc quickstart; chỉ operator chủ động thực hiện trên camera đã cắm):

```powershell
# Ví dụ: mở camera thật, ghi RAW và đọc lại; không chạy trong pytest/docs verification.
& .\.venv\Scripts\python.exe -X utf8 -m scantopath.acquisition.capture_once `
  --once --session session01 --specimen specimen01 --output '<TEST_DATA_ROOT>'
```

Sử dụng thư mục thử riêng, bảo đảm dung lượng, đóng các process khác; không trỏ vào RAW sản xuất. `--self-test` của `scantopath.acquisition.native` là bài test binding, có thể cần extension được build với `BUILD_TESTING=ON`; nó **không** chứng minh thiết bị thật.

## 10. Hiệu năng và giới hạn phép đo

Bằng chứng PRE-06 xác nhận một lượt capture/verify thực qua log operator, **không** cho phân phối sai số, tỷ lệ frame drop hay sync jitter đủ để công bố định lượng. Chưa có phép đo FPS streaming hoặc pipeline 3D trong GĐ1. Độ phân giải 1920×1080 MJPEG và 1280×800 Y16 là một profile từng kiểm thử, không bảo đảm mọi firmware USB/profile đều giống.

## 11. Sửa ở đâu khi mở rộng

Thêm profile/stream → `cpp/src/acquisition/` và `orbbec_adapter.py` → contract v2 + test. Thêm loại source → interface native/adapter, **không** import SDK trong Qt shell. Thêm replay/point cloud GĐ2 → mô-đun mới tiêu thụ `read_raw()`, giữ RAW gốc và provenance; tránh sửa `RawRgbdCaptureMetadataV2` phá ngầm schema. Thay đổi nghĩa pose/đơn vị → ADR và acceptance metric độc lập.

## 12. Kiểm thử tự động và thủ công

| Nhóm | Đường dẫn/lệnh | Đánh giá |
|---|---|---|
| Offline v2 | `tests/unit/raw/test_raw_rgbd_contract.py` | byte/metadata/validation |
| Native adapter | `tests/contracts/camera/test_pre04_orbbec_adapter.py` | nguồn packet giả có kiểm soát |
| DLL/module | `tests/contracts/camera/test_native_loader.py` | contract load, không là sensor proof |
| GĐ0 integration | `tests/integration/metadata/test_pre06_gd0_acceptance.py` | metadata + storage |
| C++ không camera | `ctest --test-dir .\build-orbbec -C Release --output-on-failure` | 2 CTest; không là sensor acceptance |
| Sensor thật | quy trình operator PRE-06 | có log lịch sử; DOC-03B không chạy lại |

Tổng thể `scripts/verify.ps1 -Profile Full` chỉ là hồi quy tự động. Ba SKIP do quyền symlink (theo whitelist R8.3) **không** đồng nghĩa các nhánh đó đã chạy. HMI/native-busy/metric vẫn cần nghiệm thu riêng.

## 13. Quyết định và giới hạn còn mở

RAW được bảo toàn làm nguồn quan sát; đo độ chính xác 3D, camera pose, đồng bộ exposure và cơ cấu quay thuộc các gate nghiên cứu/phần cứng độc lập. Khi hợp đồng nguồn hiện hành khác hồ sơ PRE-02/04, không sửa lịch sử; tạo quyết định mới, gắn baseline và phép đo. Xem tài liệu [dữ liệu và tọa độ](../02-kien-truc/DU_LIEU_VA_HE_TOA_DO.md) để hiểu sâu toán học; trang này vẫn mô tả đầy đủ contract thu nhận cần thiết.
