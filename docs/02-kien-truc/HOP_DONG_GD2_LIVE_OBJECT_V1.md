# CT-GD2-02 — Hợp đồng live stream, bounding box, tách vật thể và bán tự động

> `owner: ACQUISITION + APPLICATION + UI` · `specified_at: 2026-10-29` · `implementation: NOT_STARTED`  
> `current_physical: Gemini 2 HANDHELD (operator stated)` · `source: DEC-GD2-GD3-20261029`.

## 1. Phân biệt ba dữ liệu

| Dữ liệu | Ý nghĩa | Không chứng minh |
|---|---|---|
| `bbox_2d` | Hình chữ nhật bao object trong ảnh, phục vụ hướng dẫn/quy hoạch ROI | Phân vùng pixel chính xác hoặc 6DoF pose |
| `object_mask` | Pixel/point được chọn thuộc vật thể; từ depth, nền, cluster hoặc user edit | Pose giữa keyframes |
| `camera_pose` | Biến đổi giữa camera frames được estimated/validated ở GĐ3 | Không tự sinh từ bbox/tracking 2D |

Không dùng AI bắt buộc. Bbox có thể được đề xuất từ depth segmentation + 2D tracking; nếu môi trường khó thì user được sửa ROI và dùng manual object selection. Tự động cập nhật box khi stream phải xử lý jitter/hysteresis và báo confidence/`manual_override` nếu không đủ ổn định.

## 2. Vòng đời live camera

`IDLE -> OPENING -> STREAMING -> CAPTURING -> STREAMING -> STOPPING -> CLOSED`; mọi trạng thái có thể vào `FAILED` kèm error code. Từ `FAILED` phải dispose camera trước retry; không tự restart vô hạn. Qt event loop **không** sở hữu frame SDK. Worker/native giữ SDK, Python nhận buffer-owned copy, UI dùng preview copy nhẹ; bounded queue, bỏ preview frame cũ nhưng **không** bỏ keyframe đã được xác nhận.

### Các nguyên tắc
- Camera không tự mở khi vào workspace hoặc mở Project.
- Không capture khi chưa có Session hợp lệ hoặc capture slot/metadata chưa sẵn sàng.
- `capture` là hành động riêng có timestamp/frame metadata; không lấy tùy tiện frame preview không có cùng provenance.
- Capture original RAW v2 bất biến; overlay bbox không ghi đè `color.mjpg`.
- `frame_sync_requested` không đảm bảo cùng exposure/clock; điều kiện stability/quality cần riêng.
- Hủy: hoàn tất/hủy tại ranh giới an toàn; close khi worker bận cần xử lý lifecycle, không giả GĐ1 waiver là chứng cứ mới.

## 3. Tách object và giữ dữ liệu gốc

`RAW RGB-D → scene cloud → mask/ROI derivation → object cloud → filters`. Lưu scene cloud hoặc đủ provenance để tính lại khi GĐ3 cần background feature. Bước object extraction không được xóa nền khỏi RAW. Không chọn cluster tự động nếu có hai ứng viên không phân biệt được; yêu cầu người dùng chọn.

Nhãn output đề xuất: `segmentation_method`, `roi_xywh`, `mask_source`, `confidence`, `valid_depth_pixels`, `object_points`, `background_points`, `manual_adjusted`, `source_capture_id`.

## 4. UI reuse / không mở kiến trúc mới

- Project Workspace: chọn specimen/session/capture, audit/history.
- Processing Workspace: pipeline step status + preset Basic/Advanced, 2D preview, action bar, retry.
- Viewer hiện có: cloud/mesh 3D, không mở Qt VTK embedded thứ hai.
- Inspector hiện có: thông tin độ dài/đơn vị/Capture source; panel cung cấp results before/after.
- Nếu cần công cụ lựa chọn bbox, gắn component vào panel hiện có hoặc phần preview của Processing Workspace, không tạo workspace song song.

## 5. Gate và lỗi

| ID | Điều kiện |
|---|---|
| `LV-01` | Live stream khởi động, preview cập nhật trong Qt không block, stop/reopen an toàn |
| `LV-02` | Bounding box động bám vật thể **trong điều kiện demo đã khai báo**; UI hỗ trợ manual ROI |
| `LV-03` | Object mask/cloud không rỗng, background removal có trước/sau và khả năng xác nhận người dùng |
| `LV-04` | Capture saved/registered đúng ID, RAW SHA giữ nguyên khi replay/filter/preview |
| `LV-05` | Disconnect/timeout/cancel không để sót worker hoặc orphaned partial output |

Đối tượng chuyển động, che khuất quá mức, người, vật đen/bóng không thuộc bảo đảm tự động chung; benchmark riêng.

## 6. Giới hạn đã biết

Native hiện có `capture_once` qua OrbbecSDK, chưa xác nhận worker live và tracking đã được lập trình. Không dùng mô hình nhận diện khuôn mặt để suy mục tiêu trên vật bất kỳ; khung bao có thể tính từ depth, hoặc AI chỉ khi được phê duyệt riêng.
