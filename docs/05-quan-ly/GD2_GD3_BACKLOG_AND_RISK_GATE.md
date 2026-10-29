# Đề xuất backlog GĐ2–GĐ3 và cổng xử lý nợ kỹ thuật

> `owner: PROJECT_COORDINATOR` · `as_of: 2026-10-29` · `status: DRAFT_FOR_TASK_REGISTER, NOT_IN_PROGRESS`  
> Trang này mô tả scope/acceptance của task **đề xuất**; chỉ Task Register hiện hành mới có quyền sở hữu trạng thái công việc.

## 1. Định nghĩa ưu tiên

- `P0/BLOCKER`: sai dữ liệu, đơn vị, phép biến đổi, hỏng/mất RAW hoặc artifact, crash native, vi phạm hợp đồng nền hoặc không thể đạt gate.
- `P1/STAGE`: cần hoàn thành trước Done giai đoạn, nhưng không chặn các bước độc lập ở đầu.
- `P2/DEFERRED`: polish/UI minor, benchmark chưa có vấn đề thực, test lịch sử redundant; có lý do và vị trí sẽ xử lý.
- `P3/OPTIONAL`: AI/ROS2/simulator/PCL/robot/3DGS nếu chưa có nhu cầu được chứng minh.

## 2. Task units kế hoạch

| Candidate task | Scope | Depends on | Mandatory gates |
|---|---|---|---|
| `GD2-09-REPLAY-LIVE` | RAW v2 replay, live capture, bbox/ROI | GĐ1 closed, SDK device available for manual | G2-09-A/B/C |
| `GD2-10-XYZRGB` | Color/depth projection + measure | 09 RAW metadata | G2-10-A/B/C |
| `GD2-11-OBJECT` | Segmentation, filter | 10 singleview cloud | G2-11-A |
| `GD2-12-NORMAL` | Normals | 11 object cloud | G2-12-A |
| `GD2-13-INTEGRATE` | Artifact, ProcessingRun, Viewer | 09–12 | G2-13-A/B/C |
| `GD3-14-METRIC` | Gauge/measurement | 10/13 output + vật chuẩn | G3-14-A/B |
| `GD3-15-POSE` | Keyframes/registration/rejection | 10/11 + metric policy | G3-15-A/B |
| `GD3-16-FUSION` | Fusion/coverage/trust | 15 accepted poses | G3-16-A/B/C |
| `MVPB-MESH-DEMO` | Multi-view mesh, underside, UI, dimensional check | 10/11/13 + 15/16 phần cần thiết | MB-01..MB-10 |

Không thêm các hàng này vào Task Register dưới trạng thái `DONE`/`IN_PROGRESS` khi chưa kickoff. **`GD2-09` cũ vẫn là task gốc**; các candidate trên có thể được ghi làm subtask sau khi chốt nhánh và người thực thi.

## 3. Tồn đọng kế thừa GĐ1 — quyết định

| Vấn đề | Ảnh hưởng | Lịch xử lý |
|---|---|---|
| External Viewer scene units/frame hiện unknown | Không thể tự đưa metric provenance từ artifact nội bộ vào Viewer | P0 trong 13, giữ external unknown |
| `finish_processing_run` nhận output file paths nhưng không verify SHA | Có thể ghi succeeded khi output chưa hoàn chỉnh nếu orchestration gọi sai | P0 trong 13 |
| GĐ0 one-shot chưa có native live pipeline | Bắt buộc cho MVP-B preview keyframe | P0 trong 09 |
| C++ unproject đơn điểm, chưa batch geometry binding | Có thể là bottleneck | P1/P2 theo benchmark 10; không bắt buộc rewrite Open3D |
| Tests/scripts R7/R8 khóa một số lịch sử | Có thể cản refactor test cũ | Viết test GĐ2 mới; không đổi historical tests chỉ để PASS |
| GĐ1 NT-01 busy close, VRAM/present waived | Chưa có physical PASS | Giữ waiver; nếu workload mới làm lộ lỗi thì fix đúng module, không mở lại GĐ1 |
| Không có `main` branch protection/workflows baseline | Nợ quy trình CI | P1 trước merge GĐ2 nếu có điều kiện; không phá quy trình Windows local |
| `HW-CURRENT-BASELINE` cần physical evidence | Cầm tay đã được người dùng xác nhận, ảnh/receipt chưa có | Capture record trong 09, gauge 14; không tự ghi task DONE |

## 4. Quy trình xử lý incident

Mỗi bug: `steps_to_reproduce / observed / expected / affected_contract / severity / failing_test / patch_scope / regression / residual_risk`. Nếu không có bằng chứng, giữ `RISK_UNVERIFIED`, không tạo vòng R chung. Chỉ sửa module liên quan. Không chạy full test ở mỗi dòng code; chạy relevant tests rồi stage integration.

## 5. Giới hạn

Đây chưa là task ledger, không sở hữu trạng thái dự án; đừng cập nhật lịch sử GĐ1 trong tài liệu này. Độ chính xác demo 10 mm và Multi-view/mesh chưa có thực nghiệm.
