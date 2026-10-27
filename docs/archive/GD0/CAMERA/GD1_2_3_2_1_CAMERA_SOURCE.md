# GĐ1.2.3.2.1 — OrbbecCameraSource (C++20, Gemini 2)

## Trạng thái

**Cập nhật 18/10/2026:** Người dùng đã biên dịch và chạy `scantopath_orbbec_source_smoke.exe --once` trên Windows với Gemini 2 thật; xác nhận `diagnostic.raw_packet_valid=true` và `buffer.copy_survived_close=true`. Các lệnh bên dưới là hướng dẫn tái kiểm thử. Mốc lịch sử này thuộc nhánh Acquisition bổ sung, **không đồng nghĩa GĐ1 — 3D Core đã hoàn thành**. Thành công thu nhận không chứng minh sai số đo 3D.

## Phạm vi (không vượt sang GĐ1.2.3.2.2)

- API C++20: `open()`, `read_next()`, `device()`, `close()`, `is_open()`.
- Một camera Orbbec Gemini 2, mặc định camera duy nhất; yêu cầu tắt OrbbecViewer.
- Thu nhận **RAW**: Color 1920x1080@30 MJPG, Depth 1280x800@30 Y16, `ALIGN_DISABLE`. Yêu cầu FrameSync và các khung cùng FrameSet nhưng **không khẳng định hai exposure đồng thời**.
- Mọi bộ đệm ảnh được **sao chép sang `std::vector<uint8_t>` do ứng dụng sở hữu**. Chúng tồn tại sau `close()`.
- Lưu metadata: kích thước, SDK device timestamps, frame indices, model/firmware/USB, intrinsics, SDK distortion model+8 coefficients, Depth→Color row-major rotation và mm translation, depth scale **m/unit**.
- `depth_scale_m_per_unit = depth->getValueScale() * 0.001`; SDK `getValueScale()` có đơn vị **mm/unit**, đã đối chiếu với probe cũ.
- Không nạp các hằng số INI vào mã chạy; INI dùng để đối chiếu. Không tự áp dụng distortion, không dùng D2C. Không có pybind11, Python bridge, persistence, point-cloud hoặc UI.
- Đây là **capture dữ liệu đo thật** ở tầng native, chưa được `SessionStore` lưu và chưa được kiểm định sai số.

## Bước chạy trên Windows

Thư mục gốc đã dùng: `E:\1_BigProject\scantopath`; SDK dev ở `_sdk\OrbbecSDK_v2.10.6`.

### 1) Áp dụng patch tại thư mục `_setup\Gemini2_CameraSource_PATCH`

```powershell
cd E:\1_BigProject\scantopath
powershell -ExecutionPolicy Bypass -File '.\_setup\Gemini2_CameraSource_PATCH\apply.ps1' -ProjectRoot 'E:\1_BigProject\scantopath\scantopath-software'
```

### 2) Build *riêng* build-orbbec (không đụng cấu hình build v0.1.0)

```powershell
cmake -S .\scantopath-software\cpp -B .\scantopath-software\build-orbbec -DBUILD_TESTING=ON -DSCANTOPATH_BUILD_ORBBEC_PROBE=ON -DSCANTOPATH_BUILD_ORBBEC_SOURCE=ON "-DOrbbecSDK_DIR=E:/1_BigProject/scantopath/_sdk/OrbbecSDK_v2.10.6/lib"
cmake --build .\scantopath-software\build-orbbec --config Release
ctest --test-dir .\scantopath-software\build-orbbec -C Release --output-on-failure
```

Kỳ vọng: `core_smoke` và `rgbd_contract_smoke` PASSED, và tạo `scantopath_orbbec_source_smoke.exe`. **Các kiểm thử CTest này không truy cập camera.**

### 3) Hardware smoke (thoát hoàn toàn OrbbecViewer)

```powershell
$env:PATH = 'E:\1_BigProject\scantopath\_sdk\OrbbecSDK_v2.10.6\bin;' + $env:PATH
.\scantopath-software\build-orbbec\Release\scantopath_orbbec_source_smoke.exe --once
```

Kỳ vọng: `diagnostic.raw_packet_valid=true`, `buffer.copy_survived_close=true`, Color 1920×1080, Depth 1280×800, `depth.scale_m_per_unit=0.001000` (với cấu hình thiết bị đã thử). In timestamp delta của một frameset nhưng không coi đó là phép kiểm định đồng bộ.

Nếu báo lỗi DLL/extension, kiểm tra thư mục `bin` và gói SDK đúng phiên bản, xem tài liệu probe cũ `docs/GD1_2_3_1_ORBBEC_PROBE.md`.

## Nghiệm thu

- Build MSVC C++20 thành công, không làm hỏng `scantopath_orbbec_probe` cũ.
- `ctest` >= 2/2 passed.
- Camera smoke trả về bản sao RGB/Depth sau khi `close()`, metadata finite, độ sâu có scale dương và kích thước buffer chính xác.
- Không xem một cặp timestamp là xác nhận đồng bộ. Không cho phép sửa thẳng dữ liệu đo để khớp INI.

## Nguồn SDK

- `include/libobsensor/hpp/{Pipeline,Frame,StreamProfile}.hpp`, `include/libobsensor/h/ObTypes.h`
- https://github.com/orbbec/OrbbecSDK_v2/tree/main/examples/3.advanced.sync_align
- https://github.com/orbbec/OrbbecSDK_v2/tree/main/examples/0.basic.enumerate
