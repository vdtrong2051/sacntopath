# GĐ2 — RAW Replay & Single-view Geometry (phiên 09–13)

> `owner: STAGE_OWNER` · `as_of_commit: main@9e32daf` · `specified_at: 2026-10-29` · `implementation: NOT_STARTED`  
> `scope: APPROVED_REQUIREMENTS / PROPOSED_IMPLEMENTATION` · `source-of-truth: phạm vi GĐ2 + DEC-GD2-GD3-20261029`  
> Không tuyên bố chức năng mô tả dưới đây đang chạy. Điều kiện nghiệm thu tại [ma trận](../07-nghiem-thu/GD2_GD3_MVPB_ACCEPTANCE_MATRIX.md).

## 1. Mục tiêu sản phẩm

Dữ liệu RGB-D thật từ Gemini 2 được lưu RAW v2 hoặc mở lại từ Capture, chuyển thành point cloud **XYZRGB có tọa độ theo mét**, tách vật thể trong điều kiện quét có kiểm soát, lọc, ước lượng normals, đo sơ bộ và lưu artifact có thể mở lại trong Viewer 3D. Người dùng nhìn rõ tiến trình và quyết định ở những điểm quan trọng.

**Đầu vào:** RAW v2 Gemini 2 (chính), RAW v1 tương thích chỉ theo luồng đã được xác minh; live preview/capture qua Gemini 2 cầm tay (mở rộng GĐ2 theo quyết định 29/10). File PLY/OBJ ngoài có thể xem bằng Viewer GĐ1; không coi là RAW replay. **Không** mặc định hỗ trợ PCD/XYZ import vào pipeline GĐ2.

**Đầu ra:** decoded RGB/Depth previews, object ROI/mask, cloud raw XYZRGB, cloud filtered XYZRGB, normals, measurement preview, ProcessingRun, file PLY và manifest/metadata JSON. CSV chỉ cho dữ liệu dạng bảng cần thiết, không bắt buộc xuất toàn bộ cloud dưới dạng CSV.

## 2. Ranh giới GĐ2 / MVP-B / GĐ3

| Trong GĐ2 | Không thuộc nghiệm thu GĐ2 |
|---|---|
| Replay RAW, live preview và capture có chủ đích; object bbox/ROI; single-view XYZRGB; filter/normals; đo cơ bản; export/provenance | Pose nhiều góc đã kiểm chứng, fusion, mesh kín, đánh giá coverage đa góc, metric calibration với mẫu chuẩn có PASS, robot path/actuation |

**Dữ liệu metric:** `depth_optical` + `m` biểu thị phép tính tọa độ với scale/intrinsics của Capture; **không đồng nghĩa kích thước đạt 10 mm** nếu chưa đối chiếu vật chuẩn.

## 3. UX bán tự động trên hạ tầng GĐ1

1. **Project Workspace:** chọn Project → Specimen → ScanSession → Capture. Không tạo project ngầm khi vào trang; không ghi SQLite chỉ vì mở màn hình.
2. **Processing Workspace:** pipeline từng bước `Capture/Replay → ROI/Mask → XYZRGB → Filter → Normals → Export`. Mỗi bước có `NOT_READY / READY / RUNNING / SUCCEEDED / FAILED / CANCELLED` trong transient job state (chưa phải schema DB hiện hành); không dùng fake ProcessingRun.
3. **Viewer 3D:** tái sử dụng Render Host hiện có, hiển thị raw/clean cloud, normals hoặc layer đã hỗ trợ, đo sơ bộ; không dựng viewer thứ hai trong Qt.
4. **Panel/Inspector:** trước–sau số điểm, đơn vị, camera frame, depth scale, số pixel hợp lệ, source Capture/Run, mức tin cậy chưa hiệu chuẩn; đừng để bảng tham số chiếm UI chính.
5. **Live Preview:** mở camera có chủ đích; hiển thị RGB + Depth song song, bounding box động, nút chọn ROI thủ công; người dùng nhấn chụp. Camera không auto-open khi khởi động desktop.
6. **Bán tự động:** bước đã có dữ liệu đầu vào hợp lệ có thể chạy nối tiếp sau xác nhận; không tự động lưu hoặc thay thế RAW khi thay ROI. `Run All` chỉ là thiết kế có thể bổ sung sau, không mặc nhiên là gate 04/11.

**Quy tắc trạng thái:** UI không bị khóa event loop; cancel tại điểm hủy an toàn, không hủy tùy tiện giữa SQLite transaction/rename; lỗi camera, SDK DLL, timeout hoặc native crash phải có thông báo và khả năng retry có kiểm soát.

## 4. Phiên 09 — RAW Replay + Live capture entry

### Phạm vi
- Chọn Capture từ SQLite; xác minh RAW v2 bằng `SessionStore.read_raw()` và `COMMITTED`/SHA-256 trước decode.
- Decode `color.mjpg` và `depth.y16` đúng width/height/pixel encoding; không thay RAW trên disk.
- Hiển thị RGB/Depth cạnh nhau; phân biệt hai pixel grid và timestamps `sdk_reported_unverified`.
- Mở luồng live Gemini 2 có vòng đời `IDLE→OPENING→STREAMING→CAPTURING→STOPPING→CLOSED/ERROR`; preview chỉ dùng bản copy an toàn; lưu keyframe với metadata nguyên thủy và nhận diện Capture ID.
- Khung bao động: nguồn thuật toán và độ tin cậy phải hiển thị; fallback chọn ROI thủ công. Việc stream/tracking là mở rộng đáng kể so với GĐ0 `capture_once`.

### Gating
Offline RAW fixture PASS trước; on-device live/one-shot phải có log; close/reopen/stop khi worker đang chạy; RAW không đổi SHA khi chỉ xem; mất camera không làm hỏng Project.

## 5. Phiên 10 — Depth → XYZRGB và đo kích thước sơ bộ

- Dùng intrinsics **depth** theo đúng frame, `depth_scale_m_per_unit` từ Capture, không suy đoán mm bằng heuristics kiểu V1.
- Loại depth 0, out-of-range, NaN/Inf nếu có ở kết quả tính; định nghĩa distortion model theo SDK/capture trước khi áp dụng hiệu chỉnh.
- Tạo XYZ trong `depth_optical`; màu từ depth-to-color transform với `translation_mm / 1000`, camera intrinsics/distortion color và phép visibility/occlusion hợp lệ; không dùng tọa độ pixel trùng chỉ số khi hai ảnh khác resolution.
- Khi không thể ánh xạ RGB hợp lệ, trạng thái phải phản ánh `COLOR_MAPPING_UNAVAILABLE`, **không** gắn RGB giả. Nếu XYZRGB là gate bắt buộc, bước này chưa PASS.
- Thử synthetic ground truth, projected/reprojected points, consistency Python reference/C++ nếu có native batch.
- Đo khoảng cách/hộp bao từ **vùng vật đã lọc** theo frame có đơn vị; hiển thị 'ước tính/chưa metric-validated', không quảng cáo một bbox camera view là kích thước vật thể đầy đủ.

## 6. Phiên 11 — Object extraction, ROI, filter

- ROI/Depth mask thủ công hoặc bán tự động; tách foreground với lựa chọn depth range, RANSAC plane removal, clustering khi dữ liệu thật yêu cầu.
- **BBox 2D ≠ segmentation mask ≠ camera pose**. Không xem bounding box như bằng chứng đã tách hoàn toàn vật thể.
- Giữ cloud scene trước tách vật để có thể dùng đặc trưng nền cho camera odometry GĐ3; giữ cloud object làm đầu vào mesh.
- Filters: voxel/SOR/radius (khi có), tham số có version, không mutate RAW hoặc input cloud; sinh artifact mới.
- So sánh số điểm và cloud before/after; fail khi object mask trống, cloud quá thưa hoặc filtering loại hết điểm.

## 7. Phiên 12 — Normals

- Ước lượng normals trên cloud sạch; định nghĩa neighbourhood radius/k, cách orient theo view hoặc reference; cờ `orientation_uncertain` nếu không có cơ sở.
- Reject non-finite, zero-length; kiểm tra `norm≈1`; không suy ra phía ngoài/phía trong của vật khi thiếu bề mặt đủ thông tin.
- Lưu params, stats và provenance; không tự xuất mesh ở phiên 12.

## 8. Phiên 13 — Export & Project/Viewer integration

- `ProcessingRun` thực sự gắn Capture IDs, algorithm version, params, source hashes; ghi artifact tạm, verify output, commit và xuất manifest trước khi đánh dấu `succeeded`.
- **Internal artifact** có `units=m`, `coordinate_frame=depth_optical` hoặc frame từ phép biến đổi hợp lệ; **external PLY/OBJ** Viewer vẫn giữ `units/frame=unknown` cho tới khi có provenance.
- Viewer mở lại PLY, inspector hiển thị đo cơ bản; đo đúng đơn vị và nguồn, không tự coi mesh là CAD truth.
- Xử lý filesystem commit thành công nhưng SQLite thất bại: ghi trạng thái recoverable, không xóa RAW.
- Kiểm thử toàn luồng `RAW thật → replay → XYZRGB → segment/filter → normals → artifact → Viewer → reopen`.

## 9. Source map dự kiến

| Trách nhiệm | Nền hiện hành / điểm mở rộng |
|---|---|
| Capture/RAW | `src/scantopath/acquisition/`, `storage/session_store.py`, `domain/raw_rgbd.py` |
| Camera native | `cpp/src/acquisition/`, `cpp/python/orbbec_bindings.cpp`; hiện chủ yếu one-shot |
| Geometry | `cpp/src/geometry.cpp` hiện có unproject **một điểm**, chưa có batch cloud |
| Orchestration | `src/scantopath/modules/project_workspace/` và service/module **mới có thiết kế**, chưa có code GĐ2 |
| Viewer | `src/scantopath/modules/viewer3d/` và `ui/shell/viewer_inspector_bridge.py` |
| Metadata | `src/scantopath/metadata/repos/processing.py`; hiện `output_files` chưa tự verify checksum |

## 10. Điều kiện Done tổng thể

Xem [GD2_GD3_MVPB_ACCEPTANCE_MATRIX](../07-nghiem-thu/GD2_GD3_MVPB_ACCEPTANCE_MATRIX.md). Cần PASS fixture ground truth + RAW Gemini 2 thật + acceptance manual UI + provenance/round trip. Mọi cổng thất bại được ghi FAIL/BLOCKED; không tự thêm waiver vì deadline.

## 11. Giới hạn đã biết

Độ đúng cấp 10 mm cho multi-view/mesh chưa được xác nhận; live preview có thể cần thêm SDK worker và tối ưu tài nguyên. GĐ2 chỉ cover single-view. Số giờ dự báo mới là 35–60 giờ tập trung cho phạm vi đã mở rộng, chưa phải lịch khả thi chắc chắn trước 04/11.
