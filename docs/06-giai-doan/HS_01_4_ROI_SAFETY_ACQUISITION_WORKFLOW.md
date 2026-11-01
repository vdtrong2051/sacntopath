# HS-01.4 — ROI Safety & Acquisition Workflow

## Phạm vi

Checkpoint này bổ sung **bộ kiểm soát độ tin cậy trước khi đề xuất Auto Capture** trên luồng Gemini 2 hiện có. Bộ kiểm soát không tạo object mask, không nhận diện hộp và không tính camera pose; các việc đó thuộc HS-02.

## Quyết định kiến trúc

- Trước `AutoCaptureSession.observe`, `RoiSafetyEvaluator` nhận Depth ROI (tọa độ native Y16) và `LiveRgbdFrame` đã có từ Live Worker.
- Nếu không đủ tin cậy, **không gửi yêu cầu camera capture**, không tăng `proposals`, `saved` hoặc `failures`. Tăng `evaluated`, đặt reason code và hủy baseline preview của selector để tránh so sánh với ROI cũ.
- Nếu hợp lệ, **chỉ đánh dấu `READY_PROXY`**, không đánh đồng với nhận diện vật thể hay ước lượng pose. Vẫn phải qua HS-01.2 (chất lượng/ổn định/novelty), preflight, RAW v2 commit, replay.
- Không chạm Native SDK, SQLite, RawCapture, worker/mailbox, đường Manual Capture và C++.

## Guard mặc định (khởi tạo thực nghiệm, không phải ngưỡng chuẩn SDK)

| Tham số | Mặc định | Vai trò |
|---|---:|---|
| `min_depth_m` | 0.20 m | Bảo vệ ngưỡng vận hành camera được người vận hành đặt ra; không phải xác nhận sai số/giới hạn chính thức |
| `max_depth_m` | 2.50 m | Giới hạn phân tích preview |
| `max_width_fraction` | 75% | Chặn bbox phủ gần trọn chiều ngang |
| `max_height_fraction` | 85% | Chặn bbox quá cao |
| `max_area_fraction` | 48% | Chặn ROI phủ phần lớn cảnh |
| `border_margin_fraction` | 1% | Bắt ROI sát/chạm mép Depth |
| `min_valid_fraction` | 30% | Bắt vùng Depth thiếu dữ liệu |
| `sample_grid` | 16×16 | Lấy mẫu hữu hạn, không giữ bản sao ảnh lớn |
| `near_depth_fraction_limit` | 15% | Chặn nhiều điểm đo gần hơn 20 cm |

Bbox quá rộng thực tế `(201, 582, 1079, 214) / 1280×800` → `width=84.3%` → **`ROI_TOO_WIDE`**. Đây là hành vi fail-closed, không phải sửa thuật toán tách hộp.

## Trên Qt Capture

- Chọn **Scan Session `OPEN`** → kết nối Gemini 2 → kiểm tra Depth/ROI → bật **Auto Keyframe**.
- Dòng `ROI Safety: BLOCKED | <reason>`: **tạm ngừng đề xuất chụp tự động**, RGB-D live vẫn hiển thị, camera không bị ngắt. Operator có thể điều chỉnh khoảng cách và **Chọn ROI thủ công**.
- Dòng `ROI Safety: READY_PROXY`: được qua guard nhưng **không chứng minh ROI là vật thể**; vẫn phụ thuộc HS-01.2 để tạo `SELECT`.
- ROI thủ công là hình chữ nhật cố định theo ảnh Depth; khi camera cầm tay di chuyển, vị trí hộp trong ảnh thay đổi, operator cần kiểm tra lại. Không tự gán nhãn “theo dõi vật thể”.
- Dừng Auto Keyframe khác Dừng Camera. Các chế độ Manual Capture/RAW Replay hiện tại vẫn còn nguyên.

## Reason codes

`ROI_REQUIRED`, `ROI_GRID_MISMATCH`, `ROI_TOO_SMALL`, `ROI_TOO_WIDE`, `ROI_TOO_LARGE`, `ROI_NEAR_BORDER`, `ROI_DEPTH_INSUFFICIENT`, `DEPTH_TOO_NEAR`, `DEPTH_TOO_FAR`, `ROI_FRAME_INVALID`, `ROI_MANUAL_VALID_PROXY`, `ROI_SUGGESTED_VALID_PROXY`.

**Giới hạn:** Depth nhỏ hơn vùng đo hữu ích của cảm biến có thể trả 0/missing thay vì số đo dưới 0.20 m; hệ thống khi đó chặn bằng `ROI_DEPTH_INSUFFICIENT`. ROI qua guard vẫn có thể là mặt bàn; HS-02 chịu trách nhiệm tách vật thể và lượng hóa coverage.

## Nghiệm thu dự kiến

1. Không có Project/Session đang mở → Auto Keyframe không cho bật.
2. ROI toàn ảnh hoặc bbox 1079/1280 px → `BLOCKED | ROI_TOO_WIDE`, không ghi RAW tự động.
3. Depth khoảng 0.15 m → `DEPTH_TOO_NEAR`, không ghi RAW; Depth mất dữ liệu → `ROI_DEPTH_INSUFFICIENT`.
4. ROI thủ công vừa đủ, không chạm biên, Depth hữu ích → `READY_PROXY`, vẫn cần hai frame ổn định để đề xuất chụp.
5. Chuyển Session, Stop/Reopen hoặc storage error → trạng thái hiện có không bị phá vỡ.
6. Không cần thực hiện ghép cloud/ICP/pose ở HS-01.4.

## Cổng PASS

- `OFFLINE`: focused unit + Qt offscreen + architecture + compile PASS trên Windows.
- `HARDWARE`: Gemini 2 thật thử bbox rộng, ROI thủ công và khoảng cách thiếu Depth; số RAW không tăng khi `BLOCKED`; chọn đúng Session; dừng và Replay được.
- **Không** gọi `HS-01.4 FULL PASS` từ test giả lập hoặc từ `ROI Safety: READY_PROXY`.
