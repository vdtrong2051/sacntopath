# Đối chiếu 20 phiên cũ → lộ trình UI-first mới

Bảng đối chiếu dựa **đúng tên phiên trong bản `ROADMAP_V1_ARCHIVED.md`**; map theo năng lực, không ngầm xem một phiên cũ đã được nghiệm thu chỉ vì trùng thuật ngữ. 01–05 đã được kết thúc trong GĐ0/PRE-01–06 và không bị đánh lại số.

| Phiên cũ | Mục tiêu cũ | Phiên/khả năng mới | Quyết định / khác biệt |
|---|---|---|---|
| 01 | Project skeleton | GĐ0 giữ nguyên; **06** UI Foundation | Tiếp tục phần UI thay vì viết lại nền |
| 02 | Project / Specimen | GĐ0 giữ; **07** Project Workspace | Thêm UI cho MetadataStore đã nghiệm thu |
| 03 | ScanSession / Capture | GĐ0 giữ; **07, 09** | Hiển thị quản lý và phát lại dữ liệu |
| 04 | Raw storage | GĐ0 giữ; **09** | Dùng lại `read_raw()`, không migrate RAW |
| 05 | ProcessingRun / traceability | GĐ0 giữ; **07, 13** | UI timeline/progress và dữ liệu dẫn xuất |
| **06** | 3D core | **10, 14** | Projection/transform cho cloud một góc, kiểm chứng metric tách riêng |
| **07** | VTK viewer | **08** | UI viewer đến sớm hơn |
| **08** | Coordinate frames / measurements | **06 (contract), 10, 14** | Frame/unit contract từ sớm; đo thật chỉ sau metric gate |
| **09** | RGB-D to cloud | **09–10** | Replay/UI trước, projection đúng camera model sau |
| **10** | Point cloud processing | **11–12** | ROI/crop/filter + normals, undo, provenance |
| **11** | Multi-view registration / fusion | **15–16** | BỎ giả định encoder/stage; estimate actual handheld pose có kiểm chứng |
| **12** | Calibration / metric validation | **14** | Gauge objects và sai số/độ lặp lại bắt buộc |
| **13** | Quality / trust | **06, 10, 14, 16–18, 20+** | Trạng thái/provenance từ đầu; per-view/point/feature trust từ 16 |
| **14** | Feature extraction | **17** | Plane/cylinder/hole/axis + residual/uncertainty |
| **15** | Relations | **18** | Feature graph/constraints và nguồn bằng chứng |
| **16** | Digital replica | **18** | As-is vs nominal candidate + human acceptance gate |
| **17** | Technical export | **13, 18** | PLY/CSV/JSON sớm; handoff CAD/inspection khi có feature/metric |
| **18** | MVP-0 | **14–18** | Mốc Engineering MVP-C/D/E, không gộp thành 1 phiên khó kiểm soát |
| **19** | MVP-1 / integrated camera + controllable stage | **09, 19, 20** và tương lai rig tùy chọn | Camera thật đã có ở GĐ0; **stage/encoder không thuộc handheld baseline** |
| **20+** | Advanced research / task-specific NBV | **20+** | Task-specific uncertainty-driven rescanning sau metric/trust/pose |

## Những thứ thay đổi cố ý

- **GĐ1 cũ = sessions 06–08 hình học trước. GĐ1 mới = sessions 06–08 UI/Viewers trước.** UI được nghiệm thu theo chức năng thật; geometry vẫn phải được test trước khi hiện số đo chính thức.
- **GĐ2 cũ 09–11 = pipeline/registration. GĐ2 mới 09–13 = replay, single-view pipeline và công cụ nhanh.** Registration chuyển sang 15–16 vì cần metric foundation và pose estimate thật cho Gemini 2 cầm tay.
- **Quality/trust là trục xuyên suốt**, không bị rút gọn thành một màn hình riêng: RAW provenance sẵn từ GĐ0, UI status 06, metric 14, source/coverage 16, feature confidence 17–18, task sufficiency 20+.
- **Active Acquisition được chia:** perception (19), guided handheld (20), task-specific next-best-view (20+). Vùng thiếu không được suy ra từ một bức ảnh đẹp hoặc mesh kín.
- **CAD/CAM/path:** xuất kỹ thuật khi dữ liệu có nguồn/đơn vị/độ tin cậy; downstream robot/path planning không phải prereq cho lõi nghiên cứu.

## Kiểm soát tính đầy đủ

Mọi thay đổi tương lai phải kiểm tra đủ các nhánh: Acquisition → Metric → Registration → Quality/Trust → Feature → Relation → Replica → Technical Output → Task-specific Reacquisition. Nếu một feature mới không đóng góp vào chuỗi này hoặc UX của chuỗi này, đưa vào sandbox thay vì mặc định tăng scope.
