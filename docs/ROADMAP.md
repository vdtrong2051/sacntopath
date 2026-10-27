# ScanToPath — Lộ trình phát triển UI-first (baseline từ 18/10/2026)

**Trạng thái:** Roadmap được chốt cho giai đoạn **sau GĐ0**, triển khai vào repository qua thay đổi tài liệu riêng. **Bản này thay thế thứ tự chức năng của phiên 06–20+**, không viết lại lịch sử của phiên 01–05/PRE-01–06. Xem [bản cũ nguyên văn](archive/ROADMAP_CU/ROADMAP_V1_ARCHIVED.md) và [bảng ánh xạ](roadmap/SESSION_CROSSWALK.md).

**Mốc xuất phát đã xác minh:** PR #3 đã merge GĐ0 vào `main` ở `8bf33591389dcdff82f0fbd5bf5932a22547c984`. Windows PRE-06 báo cáo `80 passed, 1 skipped`, CTest `2/2`, native self-test exit `0`, Gemini 2 thực lưu/đọc lại RAW và SQLite. **Không** suy ra rằng toàn bộ công việc GĐ1 đã được triển khai. Kết quả hậu-merge trên `main` chưa được trình ra riêng.

## 1. Mục tiêu khoa học — tiêu chí không được phá vỡ

**Vật thể thật → RAW có nguồn gốc → hình học metric → đánh giá sai số/độ phủ/độ tin cậy → đặc trưng và quan hệ hình học → bản sao số kỹ thuật → dữ liệu phục vụ công việc kỹ thuật → yêu cầu đo bổ sung.**

Không lấy việc «mô hình nhìn giống» làm bằng chứng «đúng kích thước», không đồng nhất vùng mesh nội suy với vùng đã đo, không biến bounding box/mask AI thành đặc trưng cơ khí đáng tin. Phun phủ/CAD/CAM/CNC/robot là nhánh ứng dụng/đích nhận dữ liệu, **không** tự động trở thành lõi ScanToPath.

**Ba loại công việc:** (A) nghiên cứu: độ tin cậy, tính đủ của dữ liệu theo nhiệm vụ, bản sao số kỹ thuật, đo bổ sung; (B) kế thừa: ICP, RANSAC, KD-tree, calibration, Open3D; (C) kiểm chứng: chi tiết cơ khí, mẫu chuẩn, thiết kế ngược, kiểm tra, xử lý bề mặt. Xem [TECHNOLOGY_SCOPE](roadmap/TECHNOLOGY_SCOPE.md).

## 2. Quy tắc triển khai đã chốt

1. **UI-first nhưng không UI-only:** hoàn thiện bố cục, trạng thái, command/query và trải nghiệm trước; tích hợp logic thật theo *lát cắt dọc* ngay trong từng phiên. Mock chỉ được phép có nhãn, không dùng để khẳng định phép đo.
2. **Dễ và kiểm chứng được trước:** project UI → viewer → RAW replay → cloud một góc → ROI/filter/export. Ngoại lệ ưu tiên sớm: quy ước tọa độ/đơn vị/provenance, VTK–Qt event loop và workers.
3. **Hình học làm nguồn chuẩn:** sensor data, camera intrinsics, distortion, extrinsics, timestamps, frame conventions, artifact source IDs bất biến/truy vết được. `measured` ≠ `metric_validated`; `inferred` ≠ `observed`.
4. **Không bịa pose:** Gemini 2 **cầm tay**; `T_world_camera(t)` chưa biết cho đến khi có estimator và validation. Kế hoạch dẫn hướng ≠ quỹ đạo/pose đo được. Không yêu cầu bàn quay, motor, encoder, Raspberry Pi hoặc ESP32.
5. **Giữ 2 lưới RAW độc lập:** Color MJPEG 1920×1080; Depth Y16 1280×800 trong baseline đã kiểm thử. Depth scale lưu bằng m/unit; D2C translation lưu bằng mm. Không auto-align, resize hoặc đưa RGB v2 RAW vào contract v1 đã aligned.
6. **Một công nghệ chính cho mỗi vai trò:** Python 3.12/PySide6/VTK/Open3D/C++20/SQLite; PCL và AI chạy sandbox đến khi có A/B benchmark và xét license.
7. **Không làm nghẽn UI:** camera/native/IO/geometry/AI trong worker có cancel, error, progress; Qt main thread chỉ cập nhật giao diện/render một cách an toàn.
8. **GĐ0 không bị sửa trong PR này:** toàn bộ mã C++, RAW Storage, MetadataStore, tests PRE-01–06 giữ nguyên; roadmap là thay đổi tài liệu có chủ đích.

## 3. Phân chia các giai đoạn sau GĐ0

| Giai đoạn | Phiên | Trọng tâm và mốc nghiệm thu |
|---|---|---|
| **GĐ1 — Desktop Experience & 3D Viewing** | **06–08** | UI foundation, Project Workspace trên SQLite thật, VTK viewer PLY |
| **GĐ2 — Replay & Single-view Geometry** | **09–13** | RAW replay, unprojection, ROI, filter, export/ProcessingRun |
| **GĐ3 — Metric Reconstruction & Trust** | **14–16** | calibration/gauge, registration có pose thật, fusion + trust/coverage |
| **GĐ4 — Feature & Engineering Replica** | **17–18** | fit feature, relation graph, as-is vs nominal có bằng chứng |
| **GĐ5 — Intelligent Handheld Acquisition** | **19–20** | perception tùy chọn, tracking/mask, hướng dẫn quét cầm tay theo vùng thiếu |
| **GĐ5+ — Advanced Research** | **20+** | task-specific next-best-view, yêu cầu đo bổ sung, benchmark AI/CAx |

Đây là *tái sắp thứ tự* chức năng theo quyết định UI-first, không phải đổi tên rồi xem những phiên cũ đã xong. Mỗi phiên yêu cầu bằng chứng nghiệm thu và commit/PR riêng hoặc một nhóm nhỏ được duyệt.

## 4. Trình tự 06–20+ và tiêu chí nghiệm thu tối thiểu

| Phiên | Nhóm | UI/workflow làm trước | Core/tích hợp trong cùng phiên | Điều kiện đạt (gate) |
|---|---|---|---|---|
| **06** | P0 | Khung ứng dụng, 4 workspace, điều hướng, action/status/errors, task panel | ViewModel/DTO/service boundaries, worker/cancellation skeleton | Mở/đóng app; không block main thread; mock gắn nhãn; hồi quy GĐ0 |
| **07** | P0 | Project tree/Inspector/Session/Capture/ProcessingRun timeline | Kết nối MetadataStore thực, validation và event log | Dữ liệu GĐ0 hiện đúng, reopen bền vững, không viết lại RAW |
| **08** | P0 | VTK viewer: PLY, orbit/zoom/pan, axes, pick, layer/state | VTK–Qt adapter và lifecycle bộ nhớ/render | Point count, tọa độ fixture, UI không đơ/crash |
| **09** | P0 | Color/depth replay; metadata, timestamps, scrub một Capture | `read_raw()`/MJPEG decode/Y16 visualization, no implicit RGB↔depth registration | Kiểm tra với Gemini 2 đã lưu, frame sizes độc lập; hash giữ nguyên |
| **10** | P0 | Nút Depth→Cloud một góc, overlay hệ tọa độ/scale | Back-projection depth K + distortion/valid depth, units m, derived artifact provenance | Synthetic geometric ground truth + replay cross-check; không bịa world pose |
| **11** | P0 | Point pick, ROI 2D/3D, crop, bounding volume, undo/reopen | Spatial masks và transform contract, save artifacts | ROI xác định, provenance/frames đúng, RAW bất biến |
| **12** | P0 | Filter presets + trước/sau và số điểm | Voxel/outlier, normal estimation căn bản; Open3D adapter | Parameter replay, invalid points handled, kết quả được version hóa |
| **13** | P0 | Export panel và ProcessingRun progress/history | PLY/CSV/JSON + units/frame/provenance, lưu/đọc roundtrip | Xuất/nhập lại không mất hệ đơn vị, thông số và nguồn |
| **14** | P0 bắt buộc | Wizard đo mẫu chuẩn, chọn 2 điểm/plane, kết quả kèm cảnh báo | Transform chain, calibration & distortion, sai số/độ lặp lại | Đo **mẫu chuẩn** với giới hạn sai số được chốt trước, không ghi số đo chưa kiểm chứng là tin cậy |
| **15** | P0 khó | So sánh A/B, manual seed, xem fitness/RMSE và trạng thái pose | Relative pose estimation + registration (feature/ICP) cho camera cầm tay; rejection | Không nhận/ghép pose không đủ chứng cứ; kiểm thử target/holdout và độ trôi |
| **16** | P0 khó | Multi-view/fusion, overlay per-view trust/coverage/missing | Fusion chỉ khi transform hợp lệ; source-to-point; quality/trust schema | Phân biệt observed/weak/inferred/missing; có số liệu sai số/độ phủ |
| **17** | P1 | Feature workspace: ROI, đề xuất plane/cylinder/hole/axis/boundary | Fitting RANSAC/least-squares, residuals, feature uncertainty | So với mẫu chuẩn; không biến mesh hole thành lỗ thực được xác nhận |
| **18** | P1 | Feature tree, relation editor, as-is/nominal hypothesis, technical handoff | Feature graph/uncertainty/provenance, bản sao số kỹ thuật | Người dùng biết dữ liệu nào đo/thay đổi/suy đo; chất lượng xuất được kiểm tra |
| **19** | P1 | Overlay object box/mask/tracking **offline trước**, manual fallback | Chọn **một** detector/segmenter qua benchmark; AI worker riêng | latency/memory/mAP/mIoU trên Gemini 2, không chặn camera; chưa đồng nhất AI với đo 3D |
| **20** | P1 | UI dẫn hướng quét tay, vùng thiếu, gợi ý hành động, trạng thái pose | Rules coverage/quality và actual pose validation đã có từ 15–16 | Guide planned ≠ actual; thiếu pose/quality thì `insufficient_evidence` |
| **20+** | P2 | Dashboard đo bổ sung theo mục tiêu kỹ thuật | Task-specific NBV/rescan, AI geometry A/B, uncertainty propagation | Chứng minh lợi ích trên feature/metric/trust thay vì chỉ hình ảnh đẹp |

**Nguyên tắc nghiêm ngặt:** phiên 14 là cổng tuyên bố độ chính xác; phiên 15 xác minh pose trước phiên 16 fusion; phiên 19 không có lý do để trở thành dependency của phiên 10–18.

## 5. Mốc sản phẩm

| Mốc | Phiên kết thúc | Có thể làm gì |
|---|---|---|
| UI MVP-A | 08 | Mở project, nhập và xem PLY trong VTK |
| UI MVP-B | 11 | Replay Gemini 2 đã lưu, tạo point cloud một góc và chọn ROI |
| Engineering MVP-C | 14 | Filter/export và đo mẫu chuẩn **sau metric gate** |
| Reconstruction MVP-D | 16 | Đăng ký/fusion nhiều góc có pose/quality chứng minh được |
| Engineering MVP-E | 18 | Feature + relation + replica, phân loại độ tin cậy |
| Guidance MVP-F | 20 | Overlay perceptual tùy chọn và hướng dẫn quét tay ở mức được kiểm chứng |

## 6. Phụ thuộc kỹ thuật phải khởi tạo sớm

**Từ phiên 06:** event loop UI/worker; app services (UI không gọi SQLAlchemy trực tiếp); task result/error/cancel; units/frame identity/provenance DTO; trạng thái `unimplemented`, `mock`, `measured`, `estimated`, `validated`, `insufficient_evidence`. Các tên là khái niệm UX; không ép thay schema GĐ0 khi chưa có migration.

**Từ phiên 08:** VTK lifecycle, render thread restriction, lớn điểm + pick/ROI benchmark.

**Trước phiên 10:** distortion convention, intrinsics depth camera, invalid depths; không dùng intrinsics màu để back-project depth.

**Trước phiên 15:** pose contract có `source`, `timestamp`, `frame_from/to`, `units`, `transform`, `quality`, `validity`; world pose không được auto-fill từ đường đi mong muốn.

**Từ phiên 16:** nguồn dữ liệu đo được và suy ra phải được phân biệt ở điểm/vùng/feature/mesh; không đánh đồng kín bề mặt với đủ độ phủ.

## 7. Quy trình một phiên

1. Chốt **một lát cắt UI nhỏ**: input/output, mock/real, trạng thái lỗi, đo thời gian và tiêu chí nghiệm thu.
2. Dựng component/layout & test UI bằng fixture; không giả lập kết quả vật lý mà không gắn nhãn.
3. Cắm service thực và kiểm thử contract, IO, provenance; chạy worker riêng.
4. Kiểm thử bằng bộ dữ liệu chuẩn, dữ liệu Gemini 2 hiện có hoặc mock **tùy phạm vi**; ghi lại limitations.
5. Hồi quy Python/native/CTest nếu mã liên quan; commit và làm review thay đổi nhỏ.
6. Chỉ chuyển phiên nếu gate đạt; giữ các vấn đề chưa kiểm chứng dưới dạng hạn chế rõ ràng.

**Đường lối sử dụng AI:** thử nghiệm sandbox có dữ liệu A/B, đo latency P95, memory, accuracy, licensing và khả năng chạy offline. Không cài đồng thời nhiều model lớn vào `.venv` ứng dụng chính. Xem [TECHNOLOGY_SCOPE](roadmap/TECHNOLOGY_SCOPE.md).

## 8. Nguồn và lịch sử quyết định

- [`docs/PRE_06_GD0_ACCEPTANCE.md`](archive/GD0/PRE/PRE_06_GD0_ACCEPTANCE.md) — báo cáo nghiệm thu GĐ0 **được tạo trước merge**, trạng thái checkbox trong đó là lịch sử tại thời điểm soạn; sau đó PR #3 đã merge lên `main`.
- [`docs/ARCHITECTURE.md`](https://github.com/vdtrong2051/sacntopath/blob/08ef856a04d61f20db1e26b2ceeb399065db902f/docs/archive/GD0/ARCHITECTURE.md) — baseline kiến trúc sau GĐ0 và ranh giới UI–core.
- [`docs/roadmap/ROADMAP_V1_ARCHIVED.md`](archive/ROADMAP_CU/ROADMAP_V1_ARCHIVED.md) — nguyên văn bản roadmap cũ (Git blob SHA `f64afcf5af6a59134fae7e08052434b755284209`).
- [`docs/roadmap/SESSION_CROSSWALK.md`](roadmap/SESSION_CROSSWALK.md) — ánh xạ kỹ thuật cũ→mới, không bỏ sót yêu cầu.
- [`docs/decisions/ADR_001_UI_FIRST.md`](decisions/ADR_001_UI_FIRST.md) — lý do đổi thứ tự.
- [Bản đồ nghiên cứu NCKH](https://drive.google.com/drive/folders/1Otz7om-m-4I56CklchqkmDuJDy5-L-ed), tài liệu `01_PHAM_VI_VA_BAN_DO_NGHIEN_CUU` (09/2026): metric/trust/feature/replica/task-specific acquisition; phân loại A/B/C.
- Các đường link nghiên cứu và công nghệ do nhóm cung cấp được liệt kê trong `roadmap/TECHNOLOGY_SCOPE.md`.

**Nguồn chưa truy cập được:** ghi chú chia sẻ `https://chatgpt.com/s/t_6ad4426520748191960a62b05772b311`. Không suy đoán nội dung; nếu chứa ràng buộc mới phải xem lại bằng chứng và đề xuất ADR tiếp theo, **không tự âm thầm thay roadmap**.
