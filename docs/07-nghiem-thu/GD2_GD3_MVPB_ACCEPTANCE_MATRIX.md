# Acceptance Matrix — GĐ2, GĐ3 và MVP-B 04/11/2026

> `owner: ACCEPTANCE_OWNER` · `specified_at: 2026-10-29` · `source_baseline: main@9e32daf`  
> `all_results: NOT_TESTED` · `purpose: tiêu chí dự kiến, chưa phải receipt`.  
> **KHÔNG ghi PASS** tại thời điểm tạo tài liệu, kể cả với thuật toán V1/GĐ0 đã từng chạy.

## 1. Quy tắc trạng thái

`PASS` khi đủ method + môi trường + thực thi + receipt + reviewer; `FAIL` nếu kết quả không đạt; `BLOCKED` nếu thiếu phụ thuộc; `NOT_TESTED` chưa thử; `WAIVED_WITH_APPROVAL` chỉ khi có quyết định đích danh (không tự dùng cho gate bắt buộc MVP-B). Các gate phiên và gate demo **độc lập**, không ghi `GD3_DONE` từ `MVPB_PASS`.

## 2. GĐ2 — Gate 09–13

| Gate | Kết quả cần đạt | Phương pháp | Status |
|---|---|---|---|
| `G2-09-A` | RAW v2 replay đúng bytes/hash, RGB/depth riêng, không overwrite | Fixture + real RAW read-back/hash | NOT_TESTED |
| `G2-09-B` | Live Gemini2 open/preview/capture/stop/reopen, Qt không block | Windows + Gemini 2 thật, có video/log | NOT_TESTED |
| `G2-09-C` | Bbox động + manual ROI, không tự suy pose | Operator workflow trên mẫu demo | NOT_TESTED |
| `G2-10-A` | XYZ depth→cloud đúng K/scale/frame; invalid rejection | Synthetic ground truth, reprojection | NOT_TESTED |
| `G2-10-B` | XYZRGB ánh xạ màu hợp lệ, D2C mm→m và occlusion policy | Synthetic + Gemini2 real color test | NOT_TESTED |
| `G2-10-C` | Đo sơ bộ có đơn vị/hướng đo/cảnh báo chưa certified | UI + fixture + vật mẫu | NOT_TESTED |
| `G2-11-A` | Tách object khỏi nền, filter không phá RAW, non-empty cloud | Mẫu đã chốt + before/after + hash | NOT_TESTED |
| `G2-12-A` | Normals hữu hạn, định hướng theo policy, stats rõ | Synthetic plane/curved surface + real cloud | NOT_TESTED |
| `G2-13-A` | ProcessingRun/manifest/artifact verified trước succeeded | Corrupt/missing/crash/recovery integration | NOT_TESTED |
| `G2-13-B` | Viewer reopen XYZRGB, metric internal provenance; external vẫn unknown | Windows UI + regression | NOT_TESTED |
| `G2-13-C` | End-to-end real RAW → point cloud → normals → export → reopen | End-to-end operator receipt | NOT_TESTED |

## 3. GĐ3 — Gate 14–16

| Gate | Kết quả cần đạt | Phương pháp | Status |
|---|---|---|---|
| `G3-14-A` | Có mẫu chuẩn, đo thật, error_mm, relative%, repeatability | Thước/thước cặp + nhiều thử, ghi độ không đảm bảo tham chiếu | NOT_TESTED |
| `G3-14-B` | Quy trình metric có accuracy/limitation hợp lệ | RMSE/P95 khi có ground truth và report | NOT_TESTED |
| `G3-15-A` | Các pose accepted có transform đúng chiều, kiểm overlap/residual | Synthetic known transforms + real keyframes | NOT_TESTED |
| `G3-15-B` | Bad pose/symmetric/low overlap bị reject có lý do | Negative tests và failure modes | NOT_TESTED |
| `G3-16-A` | Fusion accepted views không scale drift, có provenance | Synthetic + real multi-view | NOT_TESTED |
| `G3-16-B` | Coverage/trust measured/inferred/missing và drift report | Ground truth/inspection | NOT_TESTED |
| `G3-16-C` | GĐ3 full physical/automated evidence sau integration | Stage acceptance receipt riêng | NOT_TESTED |

## 4. MVP-B — Demo bắt buộc 04/11 (một vật mẫu chính)

| Gate | Tiêu chí | Phép thử | Status |
|---|---|---|---|
| `MB-01` | RAW Gemini 2 cầm tay nhiều keyframe | Capture IDs/manifest/log camera | NOT_TESTED |
| `MB-02` | Bbox động/ROI fallback và RGB-D preview | Operator HMI trên Windows | NOT_TESTED |
| `MB-03` | XYZRGB có màu đúng và đơn vị/frame | Reprojection, color sanity, capture lineage | NOT_TESTED |
| `MB-04` | Object extraction/background removal | Cloud object + scene cùng nguồn | NOT_TESTED |
| `MB-05` | Multi-view point cloud được đăng ký đáng tin | Pose graph, accepted/rejected views | NOT_TESTED |
| `MB-06` | Dữ liệu trên/xung quanh/dưới, sau lật được đăng ký | Evidence transforms, underside point support | NOT_TESTED |
| `MB-07` | Triangle mesh gần đúng, không gán inferred thành measured | Mesh preview + region/holes report | NOT_TESTED |
| `MB-08` | Mỗi kích thước đã chọn sai số tuyệt đối **≤ 10 mm** | Thước đối chứng, ghi `real_mm/model_mm/abs_error_mm/relative%` | NOT_TESTED |
| `MB-09` | Viewer có đo/xoay/zoom và export/reopen | Windows HMI/real mesh | NOT_TESTED |
| `MB-10` | ProcessingRun/metadata/pose/artifacts truy vết | Audit + SHA/integrity/recovery | NOT_TESTED |

**Kết luận MVP-B:** PASS chỉ nếu MB-01..10 PASS trên ít nhất một mẫu thí nghiệm đã định và có reviewer; nếu một gate FAIL thì `MVP_B_OVERALL=FAIL/INCOMPLETE`, không tự chuyển xuống MVP-A mà vẫn gọi MVP-B.

## 5. Report template của phép đo kích thước

| Mẫu | Hướng/đặc trưng | Reference mm | Model mm | Absolute error mm | Relative % | Gate |
|---|---|---:|---:|---:|---:|---|
| `TBD` | chiều cao | CHƯA ĐO | CHƯA ĐO | CHƯA ĐO | CHƯA ĐO | NOT_TESTED |
| `TBD` | chiều dài/rộng/sâu | CHƯA ĐO | CHƯA ĐO | CHƯA ĐO | CHƯA ĐO | NOT_TESTED |

Tính `abs_error = abs(model-reference)` và `relative% = abs_error/reference*100` với reference>0. Không sửa reference sau khi xem kết quả model. Cần quy định hướng đo và chỗ đặt thước; không nhầm envelope của cloud trong camera frame với kích thước thực khi view chưa fusion.

## 6. Mẫu receipt cần tạo khi thực thi (không có sẵn)

`gate_id`, `executed_at`, `operator/reviewer`, `git_sha`, `OS/Python/CMake/SDK`, `Gemini2 firmware/profile`, `specimen dimensions`, `camera distance/lighting`, `capture hashes`, `algorithm+params`, `pose/mesh metrics`, `screenshots/log/junit/ctest paths`, `result`, `residual_risk`, `next_action`.

## 7. Giới hạn đã biết

Không có ảnh/video/log/mẫu chuẩn đo ngày 29/10 được đưa vào gói; do vậy toàn bộ cổng là NOT_TESTED. GĐ1 waiver không mở rộng sang GĐ2/GĐ3.

<!-- SCANTOPATH_GD2_10_CLOSURE_20261031_BEGIN -->
## Cập nhật riêng các gate phiên 10 — 31/10/2026

Bảng `NOT_TESTED` phía trên là **kế hoạch snapshot 29/10**, không phải trạng thái cuối phiên 10. Dưới đây là quyết định sau khi phát triển và operator thử dữ liệu thật/UI tại baseline `292c9d8`.

| Gate | Trạng thái cập nhật | Bằng chứng / phần không được suy diễn |
|---|---|---|
| `G2-10-A` | `PASS` (numerical) | Synthetic ground truth, depth scale / validity / `depth_optical` |
| `G2-10-B` | `PASS` (single-view integration) | K6 corrected; H6 C0001/C0002 RAW SHA/XYZRGB PASS |
| `G2-10-C` | `ACCEPTED_WITH_LIMITATIONS` (provisional functionality) | API m/mm, UI A/B hai Capture; **physical accuracy / reference specimen NOT_TESTED**, `metric_validated=False` |
| `GD2-10.08.3` | `NOT_RUN_BY_OWNER_DECISION` | Test cuối lặp lại bị bỏ theo owner; không tự chuyển thành PASS |
| `GD2-10 overall` | `CLOSED_ACCEPTED_WITH_LIMITATIONS` | Chỉ phiên 10, không áp dụng cho GĐ2 11–13, GD3 hoặc MVP-B |

Xem [hồ sơ đóng phiên 10](GD2_10_20261031_SESSION_CLOSURE.md). Các gate còn lại giữ nguyên theo matrix kế hoạch cho đến khi có receipt tương ứng.
<!-- SCANTOPATH_GD2_10_CLOSURE_20261031_END -->
