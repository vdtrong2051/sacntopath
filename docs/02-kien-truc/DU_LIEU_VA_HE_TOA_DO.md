# Dữ liệu, đơn vị và hệ tọa độ trong ScanToPath

> `owner: ARCHITECTURE_OWNER` · `as_of_commit: 7a0df7c5b596ff8750bf91f47310067c53a8b204` · `verified_at: 2026-10-28`  
> `scope: hợp đồng dữ liệu hiện có GĐ0/GĐ1 và yêu cầu bắt buộc cho GĐ2+` · `evidence_level: SOURCE_REVIEW + RAW_CONTRACT_TESTS`  
> **Nguồn chuẩn về ngữ nghĩa dữ liệu xuyên module.** Thông tin chi tiết về schema/transaction của RAW và SQLite sẽ được triển khai riêng trong DOC-03B, không thay đổi các bất biến mô tả tại đây.

## 1. Vì sao phải ghi rõ dữ liệu thuộc loại nào?

Một giá trị `x=12.3` không nói được đó là pixel, milimét, mét hay tọa độ trong tệp CAD; một point cloud có thể được đo thật, nội suy hoặc tạo từ fixture. Nếu thiếu **nguồn gốc (provenance)**, **đơn vị (unit)** và **hệ tham chiếu (coordinate frame)**, bản sao số và đường robot ở các giai đoạn sau sẽ không có căn cứ kỹ thuật.

Trong ScanToPath, ít nhất bốn lớp dữ liệu phải tách biệt:

| Lớp | Ví dụ và nguồn | Điều được phép kết luận |
|---|---|---|
| **RAW cảm biến** | MJPEG/Y16, calibration SDK, timestamps, Capture ID | Đã nhận payload và provenance; không tự kết luận metric accuracy |
| **Metadata** | Project/Specimen/Session/Capture/ProcessingRun SQLite | Quan hệ và lịch sử được ghi; không chứng minh thuật toán đã chạy chỉ vì có `Run` |
| **Hình học từ bên ngoài** | PLY/OBJ do người dùng chọn, SHA-256 tệp | Hình học có thể được xem/chọn; units/frame mặc định unknown |
| **Dữ liệu xử lý dự kiến** | Cloud metric, multi-view pose, mesh, features, Zigzag | Chỉ là kế hoạch nếu chưa có pipeline/test theo nguồn tại GĐ1 |

## 2. Hợp đồng RAW v2 — hai lưới pixel độc lập

`RawRgbdCaptureMetadataV2` trong `src/scantopath/domain/raw_rgbd.py` tách `color` và `depth` thành hai `RawStreamInfo` độc lập. Mỗi stream có encoding, chiều rộng/cao, `frame_index`, `timestamp_us`, `payload_size_bytes` và intrinsics phù hợp kích thước của chính nó. Nguồn đo ở mốc GĐ0 đã ghi Color **1920×1080 MJPEG**, Depth **1280×800 Y16** cho một profile thật; đó là **profile của lần thu**, không phải cố định mọi thiết bị/lần chạy.

```text
RAW Capture v2
  ├─ color.mjpg            MJPEG bytes, width_color × height_color
  ├─ depth.y16             raw uint16 little-endian, width_depth × height_depth
  ├─ metadata.json         camera, K_color/K_depth, distortion, D2C, scale, timestamps
  ├─ manifest.json         kích thước + SHA-256 từng payload
  └─ COMMITTED             marker khi writer đã hoàn thành công bố
```

Không được tự gộp hai lưới, scale ảnh màu theo depth, hay giả rằng pixel `(u,v)` của hai stream trỏ cùng tia. `alignment_mode` của contract v2 là `disabled`. Nếu một ngày xuất hiện ảnh đã align, đó phải là **artifact dẫn xuất** với tham số/biến đổi và provenance, không thay thế byte gốc.

### Intrinsics và distortion

Theo mô hình pinhole lý tưởng, với depth pixel `(u_d,v_d)` và depth vật lý `z_m`:

\[
X_d = (u_d-c_{x,d})z_m/f_{x,d},\quad
Y_d = (v_d-c_{y,d})z_m/f_{y,d},\quad Z_d=z_m.
\]

Đây là công thức **minh họa** khi tọa độ pixel đã được hiệu chỉnh biến dạng phù hợp. Khi distortion của SDK khác mô hình lý tưởng, phải áp dụng quy trình undistort tương ứng trước khi coi tọa độ 3D là đúng. **GĐ1 chưa triển khai đầy đủ pipeline tạo cloud metric** nên không coi phép chiếu này là một chức năng đã chạy.

## 3. Scale, D2C và phép đổi đơn vị bắt buộc

- `depth_scale_m_per_unit`: **mét trên một đơn vị nguyên Y16**, kiểm tra `>0`. Ví dụ minh họa: `depth_raw=1000`, `scale=0.001 m/unit` ⇒ `z=1.000 m`. Số này không chứng minh chính xác tuyệt đối tới milimét.
- `RawDepthToColorExtrinsics.translation_mm`: tịnh tiến từ **depth optical sang color optical**, **đơn vị mm**, trong khi point 3D tính từ scale ở trên dùng **mét**. Trước khi cộng vào tọa độ `m`, phải đổi `t_m = t_mm / 1000`. Không được tự suy chuyển ngược chiều nếu chưa nghịch đảo transform.
- Rotation được lưu **3×3 row-major** trong `rotation`; cùng với tịnh tiến tạo `p_color = R_depth_to_color · p_depth + t_depth_to_color`, sau khi đồng nhất đơn vị. Giả định hai tập tọa độ là optical frames của hai stream; chưa đồng nghĩa hệ `world`, `table`, `robot_base` hay `tool`.

Ví dụ tính riêng phép đổi đơn vị (không động tới camera/file):

```python
raw_depth = 1200
scale_m_per_unit = 0.001
z_m = raw_depth * scale_m_per_unit  # 1.2 m
translation_mm = (-13.0, 0.0, 0.0)  # số minh họa, KHÔNG phải calibration hiện hành
t_m = tuple(v / 1000.0 for v in translation_mm)  # (-0.013, 0, 0) m
```

Từng độ lớn thực phải lấy từ metadata của **đúng Capture**. Không chép giá trị calibration từ một lần chạy lịch sử sang vật thể hoặc thiết bị khác.

## 4. Timestamp, đồng bộ và pose

`RawStreamInfo.timestamp_us` là timestamp do SDK báo, không được tự cho rằng clock domain là PTP hay đồng bộ exposure. Schema ghi `timestamp_domain='sdk_reported_unverified'`; `observed_timestamp_delta_us` là **độ lệch chẩn đoán**, không phải xác nhận đồng bộ vật lý giữa hai frame.

`coordinate_frame='depth_optical'` chỉ xác định cách diễn giải dữ liệu nguồn theo camera. `camera_pose=None` trong metadata v2 nghĩa là **không có pose đã ước lượng/xác nhận từ mẫu RAW đó**. Ngay cả khi cơ cấu quét vật lý đặt camera cố định, muốn đưa point vào hệ thế giới vẫn cần định nghĩa transform và calibration có nguồn; không tự thêm `T_world_camera` hay `T_table_object` chỉ vì có motor/encoder trong bản thiết kế.

Một chuỗi transform hợp lệ về sau cần nói rõ **từ frame nào sang frame nào, đơn vị, thời điểm và độ tin cậy**. Ký hiệu `T_A_B` nên được định nghĩa tường minh là biến đổi điểm từ frame B sang A trong ngữ cảnh tài liệu sử dụng, không giả mọi source theo cùng quy ước. Chưa có transform hợp lệ thì phải giữ frame `unknown` ở dữ liệu dẫn xuất ngoài.

## 5. RAW và SQLite — hai hệ ghi có trách nhiệm riêng

SQLite quản lý Project → Specimen → ScanSession → Capture và ProcessingRun, còn RAW trên filesystem. `SessionStore.commit_raw` ghi vào thư mục `.partial`, xác minh manifest và công bố qua rename/`COMMITTED`. `MetadataStore.register_capture` là bước đăng ký khác. Bất biến:

- RAW được commit không được đọc rồi ghi đè khi chỉ xem hoặc kiểm tra; `read_raw` phải từ chối thiếu/sai file, payload length và checksum.
- SQLite có foreign key, transaction và schema version; một database đã có bảng nhưng không rõ version không được tự `create_all` để “sửa”.
- Nếu RAW đã commit mà đăng ký SQLite thất bại, cần khôi phục có kiểm soát; **không có atomic transaction chung** qua hai hệ.
- Schema RAW Capture v1/v2, SQLite schema v1/v2 và **Storage Layout v1/v2** là **ba khái niệm khác nhau**. Mã thư mục `P/S/T/C/R` là alias có scope, không thay immutable IDs trong metadata.

### ProcessingRun và giới hạn dữ liệu dẫn xuất

Một `ProcessingRun` có `run_id`, `stage`, `algorithm`, `version`, các `input_capture_ids`, `parameters`, `state`, `output_files`. Đó là hợp đồng **truy vết metadata**; việc ghi `succeeded` không tự chứng minh dữ liệu đầu ra có metric/trust được kiểm định. Khi GĐ2 triển khai thuật toán, cần kiểm test đầu ra và gắn source/artifact ID rõ ràng.

## 6. PLY/OBJ đi vào Viewer như thế nào?

`SceneSource` chứa path và SHA tùy chọn. Reader/host nạp PLY point-only, PLY có mặt hoặc OBJ mesh, tạo `SceneDescriptor` với `source_sha256`, `geometry_kind`, `point_count`, `face_count`, `bounds`, `has_rgb`. Contract `SceneDescriptor.from_result` giới hạn nguồn tối đa **256 MiB**, **1.500.000 vertices**, **3.000.000 faces**; đây là **giới hạn kiểm soát đầu vào**, không phải benchmark năng lực GPU.

`units` và `coordinate_frame` luôn `unknown` trong contract Scene từ file ngoài nếu không có provenance được hệ thống chứng nhận. Một bounding box hoặc giá trị XYZ không tự đổi thành milimét; lưới Oxy và gizmo XYZ chỉ là biểu diễn để quan sát.

Khi người dùng click, `SceneSelectionRef` gồm `source_sha256`, `scene_revision`, `kind=point|face`, `element_id`, `xyz`. Selection mặt trả điểm giao cắt trên mặt; không được suy đó là một điểm đỉnh CAD. `scene_revision` và frame revision ở IPC giúp từ chối picking/ảnh từ nguồn đã bị thay đổi.

## 7. Những loại bằng chứng không được tráo đổi

| Dữ liệu/biểu hiện | Đủ để kết luận | Chưa đủ để kết luận |
|---|---|---|
| `measured=True` từ camera | Có provenance cảm biến | Metric accuracy, pose thực |
| SHA-256 RAW/PLY khớp | Byte/tệp nguồn không thay so với manifest | Vật thể/đơn vị chính xác |
| `COMMITTED` và SQLite record | Tệp đã được công bố / metadata tồn tại | Chống mất điện tuyệt đối; algorithm đã chạy |
| Giao diện thấy model/XYZ | Viewer dựng được dữ liệu và trả lựa chọn | Tọa độ robot hoặc feature tin cậy |
| Pytest/CTest PASS | Hợp đồng trong môi trường kiểm thử đạt | DPI/GPU/native crash/FPS vật lý PASS |
| R4 benchmark completed render | Render workload hoàn thành trong host | Input-to-physical-present latency |

## 8. Kiểm tra và tài liệu liên quan

Kiểm tra contract RAW với `tests/unit/raw/test_raw_rgbd_contract.py`, lưu trữ với `tests/unit/raw/test_raw_storage.py`, registry với `tests/integration/storage/`; scene/interaction với `tests/native/viewer/`, `tests/ui/viewer/`. Runner tự động: `scripts/verify.ps1 -Profile Full` (Windows + build CTest phù hợp). Cổng tổng thể HMI/native theo [R6 acceptance](../07-nghiem-thu/records/GD1_R6_ACCEPTANCE_STATUS.md) vẫn có khoản `NOT_TESTED`.

**Giới hạn chính:** công thức chiếu/chuỗi frame ở đây là tiêu chuẩn thiết kế cho GĐ2+, không phải bằng chứng thư viện geometric đã tích hợp. Thông tin version/điều kiện cơ khí ngoài Git phải được xác minh bằng quyết định kỹ thuật trước khi thay đổi hợp đồng.
