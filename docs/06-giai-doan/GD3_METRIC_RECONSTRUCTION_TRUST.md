# GĐ3 — Metric Reconstruction & Trust (phiên 14–16)

> `owner: STAGE_OWNER` · `as_of_commit: main@9e32daf` · `specified_at: 2026-10-29` · `implementation: NOT_STARTED`  
> `scope: PROPOSED_EXECUTION_CONTRACT` · `evidence_level: ROADMAP + POST_GD1_DECISIONS`  
> GĐ3 **không** được ghi PASS chỉ vì MVP-B tạo được mesh trình diễn.

## 1. Mục tiêu

Từ nhiều single-view cloud có đơn vị và metadata, xác định pose, đăng ký nhiều view, hợp nhất và đánh giá sai số/độ phủ/độ tin cậy. Khác V1: không coi yaw người nhập, kết quả ICP hay mesh đẹp là bằng chứng đo chính xác.

### Điều kiện đầu vào
- Ít nhất GĐ2 có Capture/XYZRGB/ROI/normal với provenance, timestamps và các phép transform có định nghĩa.
- Camera hiện hành **Gemini 2 cầm tay**; chưa có rig, encoder hoặc bàn quay; không suy pose từ fixture khi xử lý RAW thật.
- Chọn một mẫu đối chứng kích thước bằng thước hoặc thước cặp; xác nhận vật tĩnh khi quay camera; dải khoảng cách trong vùng cảm biến hoạt động phù hợp.

## 2. Phiên 14 — Metric gate

- Ghi mẫu chuẩn, kích thước đối chứng, phương pháp đo, điều kiện ánh sáng/chất liệu/distance.
- Xác minh depth scale và intrinsics theo đúng Capture; nếu có ChArUco, phân biệt calibration RGB với kiểm chứng depth/ngoại tại.
- Đo các chiều được chọn (dài/rộng/cao/đường kính bán kính khi xác định được), báo `measured_mm`, `model_mm`, `abs_error_mm`, `relative_error_percent`, số lần lặp.
- Báo thêm residual RMSE/P95 khi có ground truth phù hợp; không thay sai số kích thước bằng reprojection error 2D.
- Gate demo `|error| ≤ 10 mm` trên chiều đã chốt; **không** đặt mặc định `5%` tương đương 10 mm.
- Gate GĐ3 đầy đủ phải có benchmark, repeatability và giới hạn đo được chốt bằng evidence riêng.

## 3. Phiên 15 — Handheld pose / registration

- Ưu tiên keyframe có chồng lấp; lưu cả `scene cloud` (có thể hỗ trợ camera pose) và `object cloud` (phục vụ dựng vật thể).
- Phương pháp có thể gồm RGB-D odometry, global feature matching/RANSAC, ICP coarse-to-fine, marker/chArUco khi khả dụng; chọn theo benchmark trên dữ liệu thực, không hardcode thuật toán duy nhất.
- Ký hiệu `T_A_B` ánh xạ `p_B → p_A`, ma trận 4×4, mét và quy ước thứ tự nhân rõ. Lưu `source_frame`, `target_frame`, seed/initialization, thuật toán, residual, overlap, status.
- Từ chối registration nếu overlap thiếu, transform suy biến, residual vượt cổng đã định, vật đối xứng gây nhiều nghiệm không phân biệt được.
- Nếu camera quét khi vật đứng yên, nền có thể hỗ trợ pose; **khi lật vật thể**, nền/scene không còn là frame chung của vật. Phải có bước đăng ký hai nhóm và bằng chứng riêng.

## 4. Phiên 16 — Fusion, coverage và trust

- Hợp nhất khi các view có pose hợp lệ, lưu origin Capture của các điểm/vùng và loại bỏ điểm trùng mà không mất provenance.
- Định nghĩa voxel/TSDF nếu lựa chọn, occlusion/outlier rejection và registration drift; định lượng `covered / missing / inferred`, không chỉ báo phần trăm điểm.
- Kết quả phải có khả năng từ chối fusion hoặc xuất `PARTIAL` khi một view hay nhóm underside không đủ đăng ký.
- Dựng mesh nằm trong nhánh **MVP-B surface reconstruction**; không xem mesh 'đóng kín' là mặt đã đo. Đánh dấu vùng dự đoán/nội suy/thiếu.
- Có bản so sánh với vật mẫu thật, lỗi registration, kích thước theo mesh/cloud, repeatability để nghiệm thu.

## 5. Trình tự nhóm quét đối với vật cầm tay

1. Nhóm A: vật đứng yên, camera di chuyển theo vòng xung quanh; lưu keyframe có overlap (không suy pose từ chỉ số góc chụp).
2. Nhóm B: thêm view trên cao để phủ vùng trên, không trộn vào nhóm A khi registration chưa đạt.
3. Nhóm C: lật/định vị vật thể và quét mặt dưới; xử lý như **nhóm frame mới**, chỉ fuse về nhóm A/B khi có chứng cứ biến đổi.
4. Mỗi nhóm có `registration_status`, `accepted/rejected_views`, `quality_stats`, và provenance. Nếu nhóm C thất bại, cổng underside của MVP-B phải `FAIL`, không sinh đáy giả để che lỗi.

## 6. Ngoài phạm vi

Không yêu cầu robot control, PLC, động cơ, camera 2 trục, AI generative 3D, feature graph hoặc Digital Replica GĐ4. Không hứa quét người đứng chuyển động đạt metric threshold 10 mm; đối tượng động là nghiên cứu riêng.

## 7. Giới hạn đã biết và nghiệm thu

Không thể cam kết tự động thành công với vật thể đối xứng, nhẵn, đen/bóng/trong suốt, thiếu overlap. Việc chọn ICP/odometry/marker chưa được nghiệm thu. Xem [pose/fusion contract](../02-kien-truc/HOP_DONG_GD3_POSE_FUSION_MESH_V1.md) và [acceptance](../07-nghiem-thu/GD2_GD3_MVPB_ACCEPTANCE_MATRIX.md). Dự báo công sức GĐ3 với dữ liệu và mẫu chuẩn sẵn sàng khoảng 35–66 giờ; không bao gồm chờ phần cứng.
