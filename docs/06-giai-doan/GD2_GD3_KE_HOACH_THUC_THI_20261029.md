# Kế hoạch thực thi GĐ2/GĐ3 và đường ưu tiên MVP-B — 29/10/2026

> `owner: STAGE_OWNER / ENGINEERING_OWNER` · `planning_status: APPROVED_SCOPE_NOT_STARTED` · `baseline: main@9e32daf`  
> `schedule_target: onboarding 2026-11-04` · `source-of-truth: kế hoạch kỹ thuật; Task Register chỉ chuyển trạng thái khi kickoff chính thức`.

## 1. Nguyên tắc vận hành

- Giữ GĐ1 closed, không phát sinh R9 chung; mỗi phiên là **một vertical slice** có input/output/UI/cancel/error/test/evidence.
- P0 sửa trước khi pass phiên liên quan; P1 xử lý trước Done giai đoạn; P2 deferred có lý do; P3 không chặn MVP.
- Không bỏ ground truth, dữ liệu thật, safety/stop behavior hoặc artifact verification để đạt deadline.
- Mỗi phiên có **thiết kế đã duyệt → agent thực thi → test module → operator UI/device → ghi receipt → chốt**. Chỉ Full Regression tại cổng tích hợp và khi sửa nền rộng; không chạy lại vô hạn test không liên quan.
- Không tự tạo branch/commit/merge/deploy bởi gói lập kế hoạch.

## 2. Bản đồ phụ thuộc

```text
GD1 CLOSED
    |
    v
09 RAW replay + live/capture
    |
    v
10 XYZRGB / units / color registration
    |
    v
11 object mask / filters
    |
    v
12 normals / local quality
    |
    v
13 export + ProcessingRun + Viewer  ---> GD2 acceptance
    |
    +----------------------------+
                                 v
14 metric gauge / error  --> 15 pose/registration --> 16 fusion/trust
                                 |                     |
                                 +------ MVP-B mesh ---+--> 04/11 target gates
```

MVP-B là overlay trên stage tasks, không lén đánh dấu Done của 14–16 khi mới hoàn thành demo.

## 3. Công sức ước tính (giờ tập trung, không phải cam kết)

| Work package | Điều kiện | Ước tính |
|---|---|---:|
| GD2-09 | Offline replay + live worker + bbox preview | 8–14 h |
| GD2-10 | Single-view XYZRGB + color projection + measurement preview | 7–12 h |
| GD2-11 | ROI/segmentation/background removal/filter | 5–9 h |
| GD2-12 | Normals + quality | 3–5 h |
| GD2-13 | ProcessingRun, artifact, Viewer, integration | 6–10 h |
| GD2 regression/physical fix allowance | Không miễn lỗi P0 | 6–10 h |
| **GĐ2 (expanded)** | **35–60 h** | **35–60 h** |
| **GĐ3** | 14–16 metric, pose, fusion, coverage/trust (mẫu/RAW sẵn) | **35–66 h** |
| **MVP-B mesh integration** | Surface reconstruction, preview/export/measurement | **12–25 h** |
| **Tổng dự báo hai giai đoạn + mesh** | Tránh double-count trong từng gói; rủi ro camera/pose chưa phản ánh hết | **82–151 h** |

Khoảng là **estimation from scope/source**, không đo trực tiếp velocity agent; gần mốc 04/11 không đủ cơ sở bảo đảm toàn bộ cổng PASS. Việc phát sinh platform/native build failure, calibration hoặc data capture có thể tăng thêm.

## 4. Thứ tự kiểm chứng rủi ro cho mốc 04/11

1. **Feasibility gate:** RAW real Gemini 2 còn dùng được; depth/color calibration có thể tạo XYZRGB; native/live camera không crash.
2. **Object gate:** ROI/mask tạo object cloud đúng, sai lệch kích thước đơn view không quá bất hợp lý (chưa gọi accuracy pass).
3. **Multi-view gate:** chọn keyframes có overlap để đăng ký một vòng xung quanh bằng pose đã kiểm chứng.
4. **Underside gate:** chụp nhóm mặt dưới sau lật và chứng minh transform về nhóm chính; đây là blocker cao nhất.
5. **Mesh gate:** reconstruction, đo 3 chiều đối chứng, độ lệch ≤ 10 mm/chiều được xác định trước.
6. **Product gate:** UI, ProcessingRun, replay, Viewer, export; Full regression/Windows acceptance.

**Không** hoán đổi trình tự để làm UI đẹp trước khi kiểm chứng pose/underside. Các bước GĐ2 vẫn Done theo thứ tự 09–13; risk feasibility có thể được thử độc lập/offline như spike nhưng không dùng kết quả spike để đánh dấu một stage Done.

## 5. Mẫu handoff bắt buộc cho mỗi phiên

| Field | Bắt buộc |
|---|---|
| `session_id`, `scope IN/OUT` | Một phiên, không mở mơ hồ |
| `branch/base_sha` | Baseline/branch đúng, git diff không lẫn việc khác |
| `inputs/outputs/units/frames` | Cụ thể, bám contracts |
| `UI screenshots/interaction` | Màn nào/panel nào, state, fallback, errors |
| `modification map` | File/module được đụng vào; file bị cấm đổi |
| `automated tests` | Synthetic/contract/integration/CTest khi có native |
| `physical/manual` | Điều kiện camera/hardware và receipt |
| `failure/recovery` | Replay, cancel, interrupt, invalid input, retry |
| `definition of done` | Gate ID PASS với evidence hoặc BLOCKED có lý do |
| `non-goals/backlog` | Gỡ tính năng không cần, không âm thầm mở rộng |

## 6. Khoản nợ kỹ thuật phân phối theo phiên

| Risk ID | Gate bắt buộc | Hoãn khi nào |
|---|---|---|
| `RISK-RGBD-GRID` | 09/10: hai grid, correct K/distortion/scale/D2C | Không hoãn nếu tạo XYZRGB |
| `RISK-ARTIFACT-TRUST` | 13: file verify trước succeeded | Không hoãn khi export |
| `RISK-VIEWER-UNITS` | 13: internal metric provenance được Viewer phân biệt | Không hoãn nếu đo bằng UI |
| `RISK-POSE-UNKNOWN` | 15: pose cầm tay được ước lượng và reject kém | Không hoãn khi fusion |
| `RISK-UNDERSIDE` | MVP-B: after-flip registration | Không hoãn nếu tuyên bố MB-06 PASS |
| `RISK-HW-EVIDENCE` | 09 live test; 14 gauge | Nhánh offline GĐ2 có thể phát triển trước |
| `RISK-GD1-WAIVERS` | Không mở lại GĐ1; nếu workload mới tái hiện native busy, sửa tại module liên quan | VRAM/present profiling hoãn nếu không chặn workload |
| `RISK-TEST-HISTORY` | Không sửa baseline R7/R8 gate để fake PASS | Dọn test lịch sử riêng ở P2 nếu thật sự gây blocker |

## 7. Trách nhiệm C++ / Python

Python điều phối workflow/Qt/storage/params/report; C++/OrbbecSDK giữ camera native và có thể thêm batch geometry khi benchmark cần. Ưu tiên Open3D/OpenCV native thông qua Python, không viết lại ICP/filter chỉ vì muốn có nhiều code C++. Điều chỉnh C++ ABI/build cần CTest/binding smoke và rollback.

## 8. Giới hạn và ra quyết định

Plan này **không thực hiện lệnh Git**, không tạo branch và không nâng trạng thái. Khi bắt đầu, người vận hành phải duyệt scope phiên 09, chọn nguồn test RAW thật; giao việc agent theo phạm vi đã khóa. Nếu lỗi P0 nghiêm trọng, đánh FAIL/BLOCKED với evidence; không miễn hoặc bỏ gate vì lịch 04/11.
