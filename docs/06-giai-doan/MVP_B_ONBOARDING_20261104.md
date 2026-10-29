# MVP-B — Hợp đồng sản phẩm demo onboarding 04/11/2026

> `owner: PRODUCT_SCOPE_OWNER / ACCEPTANCE_OWNER` · `specified_at: 2026-10-29` · `status: TARGET_REQUIRED, NOT_EXECUTED`  
> `deadline_target: 2026-11-04` · `evidence_level: USER_REQUIREMENT / NO_RUNTIME_RECEIPT`  
> **Không** đồng nhất đạt demo MVP-B với hoàn thành GĐ3. Không cho phép giảm phạm vi demo một cách âm thầm.

## 1. Mục tiêu và thao tác người dùng

Người dùng cầm **Orbbec Gemini 2** quét một vật thật; phần mềm hiển thị preview RGB-D với **khung bao vật thể động**, cho phép chọn/điều chỉnh ROI; ghi các keyframe multi-view; tạo nhiều cloud XYZRGB đã tách nền; ước lượng pose và ghép vào **point cloud tổng**, dựng **triangle mesh 3D gần đúng**, xem, đo và xuất trong desktop Qt hiện tại. Bắt buộc có dữ liệu quan sát **mặt trên, xung quanh và mặt dưới** được ghép về một hệ tọa độ nếu tuyên bố MVP-B PASS.

## 2. Đối tượng và hạn chế demo

Ứng dụng hướng tới hộp, cốc, tượng nhỏ, phôi cơ khí và về dài hạn đối tượng lớn/người; **không hardcode theo loại vật**. Mẫu ưu tiên kiểm chứng: hộp có họa tiết (kích thước/planar/multi-face) và tượng nhỏ (surface cong), chọn **ít nhất một** mẫu đạt trọn cổng MVP-B, mẫu thứ hai để đo khả năng khái quát. Cốc trơn, phôi bóng hoặc người có độ khó cao; không lấy một lần fail ngoài điều kiện để phủ định toàn pipeline.

Đối với người: cần cân nhắc đối tượng chuyển động, vùng khuất, quyền riêng tư/đồng ý khi chụp; **không** đưa vào gate bắt buộc 04/11.

## 3. Định nghĩa thành công

| Gate | Kết quả bắt buộc |
|---|---|
| `MB-01` | Gemini 2 **cầm tay** tạo RAW RGB-D thật của nhiều keyframe có thời điểm và Capture ID |
| `MB-02` | Live RGB-D, bbox vật thể động, fallback ROI thủ công; không đóng băng Qt |
| `MB-03` | XYZRGB từ depth/color đúng intrinsics + D2C, đơn vị `m`, source có checksum |
| `MB-04` | Tách nền/object mask, giữ raw scene và object cloud phân biệt |
| `MB-05` | Đăng ký nhiều view có pose/residual/overlap và ghi view rejected, tạo merged object cloud |
| `MB-06` | Dữ liệu mặt trên, quanh và mặt dưới có **bằng chứng được đăng ký**; không biến underside giả thành PASS |
| `MB-07` | Dựng mesh từ dữ liệu thu nhận, nhận ra hình dạng; khai báo vùng inferred/missing |
| `MB-08` | Đo ít nhất các kích thước được chọn, từng chiều có `abs_error_mm ≤ 10` so với đối chứng thực |
| `MB-09` | Viewer có thể mở lại, orbit/zoom/đo sơ bộ, export artifacts; không tạo renderer mới |
| `MB-10` | Tất cả keyframe/pose/parameters/artifacts có ProcessingRun và provenance có thể truy vết |

`10 mm` là mục tiêu **tuyệt đối** cho các chiều được đo, không tương đương `5%` hoặc tỷ lệ đúng trên toàn bộ vật. Chiều dài, chiều cao, chiều sâu/độ dày phải được đo ở các hướng có nghĩa đối với mẫu. Đối với vật không có trục chính rõ, định nghĩa hướng đo trước khi đánh giá. Không thể dùng một bounding box trong camera frame của một view để coi đã đo kích thước đầy đủ của vật.

## 4. Pipeline thực thi và phương án dự phòng

`Project → Live/Replay → Object ROI/Mask → Capture Keyframes → Single-view XYZRGB → Per-view Filter → Pose/Registration → Fusion → Mesh → Dimension Check → ProcessingRun + Viewer + Export`.

- Có thể phát triển offline replay trước live stream, miễn demo cuối thực hiện thu thật với camera.
- Nếu không ghép được underside: báo `MB-06 FAIL`, lưu dữ liệu nhóm mặt dưới và lý do; không được bịa phần lấp trong mesh hoặc công bố đạt MVP-B.
- Nếu object tracking tự động thất bại: fallback manual ROI được phép, **nhưng gate khung bao động không PASS** nếu chưa chứng minh nó hoạt động.
- Nếu mesh chứa vùng nội suy, được phép hiển thị **khi được gắn nhãn inferred**, không khẳng định vùng này đã quét.
- Nếu không đạt sai số: ghi `MB-08 FAIL`, hiển thị số đo thật và sai lệch, không thay ngưỡng sau khi thấy kết quả.

## 5. Quan hệ với roadmap

MVP-B là đường tích hợp demo **bắc qua GĐ2 + phần GĐ3 + surface reconstruction**, không mở GĐ4 và không thay scope các gate chính. GĐ2 Done không bắt buộc multi-view. GĐ3 Done đòi metric/trust benchmark đầy đủ và độc lập với ngày demo. Zigzag/Contour không nằm trong MB-01–10; được giữ làm nhánh kế thừa V1 sau khi có mesh đủ tin cậy.

## 6. Rủi ro và khả thi

Hạn chế chính: không có pose vật lý đo sẵn; cần overlap/feature hoặc mốc; lật vật thể đổi frame; camera preview là bổ sung mới lên one-shot; tính toán fusion/mesh chưa nằm trong source hiện tại. Phạm vi này vượt xa ngân sách GĐ2 gốc; lịch 04/11 có nguy cơ không hoàn thành ngay cả khi agent code nhanh. **Không đổi baseline hoặc bỏ gate để đạt lịch.**

## 7. Hồ sơ chứng cứ sau thực thi

Ghi ngày/giờ, commit, OS/Python/SDK/Gemini2 firmware, source RAW IDs/hash, số keyframe/các nhóm, lỗi registration, exported point counts, mesh stats, các chiều thực/model/sai số, ảnh/quay màn hình/UI, test report, mọi ngoại lệ. Trước đó toàn bộ `MB-*` = `NOT_TESTED`.
