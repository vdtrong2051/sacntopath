# CT-GD2-01 — Hợp đồng RAW replay → XYZRGB một góc (bản thiết kế v1)

> `owner: GEOMETRY_MODULE_OWNER` · `specified_at: 2026-10-29` · `implementation: NOT_STARTED`  
> `source_baseline: main@9e32daf` · `source-of-truth: hợp đồng đề xuất; không phải API class đã có trong code`  
> Hợp đồng kế thừa `RawRgbdCaptureMetadataV2`, không thay schema RAW bất biến.

## 1. Input và nguồn gốc

| Trường logic | Đầu vào | Ràng buộc |
|---|---|---|
| `capture_id` | MetadataStore Capture | Đã đăng ký hoặc có recovery state tường minh; ID bất biến |
| `color_bytes` | `color.mjpg` | JPEG hợp lệ, byte size và SHA-256 khớp manifest |
| `depth_bytes` | `depth.y16` | Little endian `uint16`, shape `(height, width)` depth, byte count chính xác |
| `K_depth`, `D_depth` | Metadata của **đúng** Capture | Không lấy calibration hardcoded từ capture khác |
| `K_color`, `D_color` | Metadata của **đúng** Capture | Pixel grid màu độc lập depth |
| `T_color_depth` | SDK depth→color extrinsics | `p_color = R·p_depth + t_m`, `t_m = translation_mm/1000` |
| `depth_scale` | `depth_scale_m_per_unit` | Hữu hạn, dương; `z_m = depth_raw × scale` |
| `frame_info` | RAW metadata | `depth_optical`; timestamps `sdk_reported_unverified`; `camera_pose=None` chưa có world pose |

Bắt buộc verify RAW qua `SessionStore.read_raw()`/`read_raw_numbered()` thích hợp. RAW v1 được coi là **nhánh tương thích riêng**; không giả đã có color-depth transform hoặc provenance v2 khi metadata v1 không cung cấp.

## 2. Phép chiếu và distortion

Với pixel depth `(u_d,v_d)` sau khi xử lý méo **theo model xác minh** và `z_m>0`:

```
X = (u_d - cx_d) * z_m / fx_d
Y = (v_d - cy_d) * z_m / fy_d
Z = z_m
```

- Không mặc định intrinsics cung cấp là trên ảnh đã rectified; xác minh `sdk_model`, thứ tự hệ số và đường dùng của OpenCV/SDK. Nếu không hỗ trợ model cụ thể, trả `DISTORTION_MODEL_UNSUPPORTED` thay vì coi méo bằng 0.
- Sử dụng pixel-center convention nhất quán; không resize depth, align RAW hay hoán đổi axes ngầm.
- Khi gắn màu: biến đổi `p_depth` sang `p_color`, project theo intrinsics/distortion **color**, kiểm tra vùng ảnh, `z_color>0`, visibility/occlusion và color decode; điểm không đủ điều kiện màu phải có **validity mask**.
- Quy ước frame cloud cuối: `depth_optical` trừ khi có transform đã xác nhận. Tọa độ `m`; hiển thị mm chỉ ở presentation layer.

## 3. Hợp đồng output đề xuất

Tên DTO dưới đây là *conceptual*, chưa phải Python class đang tồn tại:

| Trường | Loại/đơn vị | Ý nghĩa |
|---|---|---|
| `points_xyz` | `float32[N,3]` hoặc `float64[N,3]`, mét | Vị trí 3D hữu hạn, chiều sâu dương |
| `colors_rgb` | `uint8[N,3]` hoặc `float32[N,3]` với định nghĩa range | Có validity mask; không tự gán màu nếu missing |
| `source_pixel_uv` | `int32[N,2]` | Mapping về pixel depth gốc, phục vụ provenance |
| `color_valid` | `bool[N]` | Đánh dấu điểm có RGB hợp lệ |
| `source_capture_id` | immutable string | Capture nguồn |
| `units` / `frame` | `m` / `depth_optical` | Có nguồn từ RAW, **chưa certified accuracy** |
| `transform_chain` | danh sách typed transforms | Rỗng trong single-view nếu chưa có pose |
| `quality_stats` | count/range/rejection reasons | Không nhân nhượng NaN và zero-depth |
| `algorithm_id/version/params` | JSON structured | Cho phép tái tạo kết quả |

Point colors và geometry có thể được xuất PLY khi đủ hợp đồng; manifest/metadata lưu Capture IDs, hash nguồn, bounds, thresholds, thuật toán, runtime environment.

## 4. Lỗi bắt buộc

| ID | Khi nào | Hành vi |
|---|---|---|
| `RAW_INTEGRITY_FAILED` | Thiếu/sai hash/byte/shape | Từ chối xử lý, giữ RAW |
| `DEPTH_SCALE_INVALID` | scale không hữu hạn/dương | Từ chối |
| `INTRINSICS_INVALID` | shape/K không phù hợp | Từ chối |
| `DISTORTION_MODEL_UNSUPPORTED` | model khác assumption được xác minh | Từ chối kết quả metric; không silently fallback |
| `COLOR_REGISTRATION_FAILED` | D2C/occlusion/projection không hợp lệ | XYZ có thể còn giá trị nhưng **XYZRGB gate FAIL** |
| `EMPTY_VALID_DEPTH` | không có điểm depth hợp lệ | Từ chối cloud rỗng |
| `RESOURCE_LIMIT_EXCEEDED` | vượt giới hạn worker/memory | Báo lỗi, không crash UI |

## 5. Ground truth tối thiểu

- Synthetic depth plane và grid với intrinsics biết trước; so sánh XYZ và round-trip pixel/reprojection theo dung sai số học cụ thể.
- Cases: zero-depth, min/max, mismatched stream resolutions, distortion model, D2C mm→m, color pixels out-of-frame, occlusion, invalid bytes/hash.
- Test thực: replay ít nhất một RAW Gemini 2 với metadata nguyên trạng; đo mẫu ngoài đời GĐ3 mới cấp accuracy PASS.

## 6. C++ và hiệu năng

Có `cpp/src/geometry.cpp::unproject` **đơn điểm**; chưa có batch pybind geometry module. Bắt đầu bằng NumPy/Open3D reference và native batch nếu benchmark cho thấy đáng giá. Không gọi pybind11 từng pixel. GIL/ownership: khi trả mảng, bộ nhớ không trỏ về SDK đã close. Benchmark phải tính cả copy qua binding.

## 7. Giới hạn đã biết

Chưa xác nhận hiệu chuẩn depth thực tế/độ chính xác tuyệt đối. Không tự kết luận `measured=True` là metric validated. Điểm không có màu không được tùy tiện tô RGB nhưng vẫn có thể lưu geometric validity riêng; MB-03 vẫn cần màu hợp lệ trên vùng object đã chốt.
