# Đối chiếu phiên cũ và lộ trình GĐ1–GĐ5 mới

> `owner: STAGE_OWNER` · `as_of_commit: 81da5d2050324b1dc4a65ffbca9a38ed1ebba10a` · `verified_at: 2026-10-28`  
> `scope: khả năng và lịch sử đánh số, không là progress/task ledger` · `source-of-truth: ADR-001 + lịch sử roadmap và crosswalk` · `evidence_level: DOCUMENTARY_CROSSWALK_ONLY`

## 1. Vì sao cần crosswalk?

Roadmap đầu tiên ưu tiên 3D Core, phiên 06/07/08; ADR-001 về sau áp dụng **UI-first theo vertical slices**, đưa Qt/Projects/Viewer lên 06–08 và dịch geometry/metric sang các phiên sau. Đánh số trùng không có nghĩa phiên cũ đã được làm hoặc phạm vi từng file được rename thành hiện trạng. Bảng này kế thừa [crosswalk lịch sử](SESSION_CROSSWALK.md) nhưng đủ ý tại một trang giai đoạn.

## 2. Ma trận năng lực

| Phiên cũ | Năng lực cũ | Đối chiếu mới và lý do |
|---|---|---|
| 01 | Skeleton | GĐ0 giữ foundation; UI vào 06 |
| 02 | Project/Specimen | GĐ0 metadata; 07 Project UI |
| 03 | ScanSession/Capture | GĐ0 giữ; 07 quản lý, 09 replay |
| 04 | RAW storage | GĐ0 byte contract; 09 replay |
| 05 | ProcessingRun | GĐ0 audit; 07 UI, 13 derived output |
| 06 | 3D core | 10 projection; 14 metric gate riêng |
| 07 | VTK Viewer | 08 Viewer GĐ1 |
| 08 | Coordinate/measurement | Contract từ 06; 10 projection; 14 validation |
| 09 | RGB-D→cloud | 09 replay và 10 unprojection |
| 10 | Point cloud processing | 11 ROI/filter, 12 normals |
| 11 | Registration/fusion | 15 pose estimation, 16 fusion+trust |
| 12 | Calibration/metric | 14 calibration/metric validation |
| 13 | Quality/trust | 06 status, 10 provenance, 14 metric, 16–18 trust, 20+ sufficiency |
| 14 | Feature extraction | 17 feature/residual/uncertainty |
| 15 | Relations | 18 feature graph/constraints |
| 16 | Digital replica | 18 as-is/nominal + acceptance |
| 17 | Technical export | 13 PLY/CSV/JSON; 18 engineering handoff |
| 18 | MVP-0 | 14–18 engineering gates, không dồn một phiên |
| 19 | MVP-1 + stage | 09 replay, 19 perception, 20 guidance; rig/encoder cần quyết định riêng |
| 20+ | Next-best-view / advanced | 20+ task-specific active acquisition |

## 3. Giai đoạn và các gate không được bỏ

**GĐ0:** Software Skeleton/RAW/metadata, không chứng nhận metric. **GĐ1:** phiên 06–08 Qt/Project/Viewer, final HMI 08.06.6 còn mở. **GĐ2:** phiên 09–13 replay, cloud single-view, ROI/normal/export, cần unit/frame/provenance. **GĐ3:** 14–16 metric/pose/fusion/trust, cần gauge/RMSE/drift. **GĐ4:** 17–18 features/replica, cần residual/uncertainty/human review. **GĐ5:** 19–20+ perception/guidance, AI nếu có phải benchmark, không tự có actuator/robot.

Giữ mục tiêu nghiên cứu Scan Pipeline → Metric Geometry → Trusted Geometry → Feature → Digital Replica → Active Acquisition; thay đổi thứ tự để UI kiểm thử được sớm **không xóa yêu cầu khoa học**. `Open3D/OpenCV/Eigen` có thể nằm trong thiết kế, nhưng không tự coi là pipeline đã có.

## 4. Nơi tìm task, trạng thái và bằng chứng

Khi cần ai làm/đang ở trạng thái gì: [TASK_REGISTER](../05-quan-ly/TASK_REGISTER.md). Khi cần implementation/verification: [TRANG_THAI_DU_AN](../05-quan-ly/TRANG_THAI_DU_AN.md). Khi cần cổng: [GD1 acceptance](../07-nghiem-thu/GD1_ACCEPTANCE.md). Chi tiết quyết định UI-first giữ nguyên ở [ADR-001](../99-lich-su/ADR/ADR_001_UI_FIRST.md). Không sao chép trạng thái `DONE` vào crosswalk.

## 5. Giới hạn đã biết

Mapping theo **năng lực**, không phải bằng chứng completion hoặc baseline phần cứng cố định. Phần cứng hiện hành chưa có hồ sơ ký riêng trong Git và nằm tại task `HW-CURRENT-BASELINE`; không suy diễn stage từ lịch sử handheld.


<!-- SCANTOPATH_GD2_GD3_PLANNING_20261029_BEGIN -->
## Phụ lục crosswalk sau GĐ1 — 29/10/2026

Phiên 09–13 tương ứng RAW replay, single-view XYZRGB, segmentation/filter, normals, export; phiên 14–16 tương ứng metric, handheld pose/registration, fusion/trust. **MVP-B 04/11** lấy khả năng từ cả hai giai đoạn và thêm surface mesh, nhưng không nhập mesh hoặc multi-view vào điều kiện Done của GĐ2. [GĐ2](GD2_RAW_REPLAY_SINGLE_VIEW_GEOMETRY.md), [GĐ3](GD3_METRIC_RECONSTRUCTION_TRUST.md), [MVP-B](MVP_B_ONBOARDING_20261104.md).
<!-- SCANTOPATH_GD2_GD3_PLANNING_20261029_END -->
