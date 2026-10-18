# ScanToPath — Kiến trúc sau nghiệm thu GĐ0 (UI-first baseline)

**Cập nhật:** 2026-10-18. **Đây là mô tả kiến trúc hiện có + kiến trúc mục tiêu, không phải chứng nhận tất cả module đã triển khai.** Đọc cùng [`ROADMAP.md`](ROADMAP.md) và [ADR-001](decisions/ADR_001_UI_FIRST.md).

## 1. Hiện trạng đã có / chưa có

| Thành phần | Hiện trạng cuối GĐ0 |
|---|---|
| C++20 + OrbbecSDK v2.10.6 + pybind11 | Đã nghiệm thu một shot Gemini 2 RAW thực, source/buffer lifetime |
| RAW v2 | MJPEG/Y16 lưới độc lập, calibration metadata/scale/time, SHA-256, `COMMITTED`, readback |
| RAW v1 synthetic | Còn hỗ trợ đọc, không dùng để giả lập color-depth alignment từ camera thật |
| SQLite + SQLAlchemy | Metadata Project → Specimen → Session → Capture → ProcessingRun, audit events và CLI |
| UI PySide6 | Shell tối thiểu; **chưa** có Project Workspace thật, VTK viewer, replay UI |
| 3D geometry | C++ geometry smoke; **chưa** có application cloud pipeline/metric validation/registration/fusion |
| AI tracking/guidance | Chưa triển khai; hardware hiện tại là **camera cầm tay**, không có actuator |

Bằng chứng: [`PRE_06_GD0_ACCEPTANCE.md`](PRE_06_GD0_ACCEPTANCE.md) là hồ sơ viết trước merge; PR #3 đã merge lên `main` tại `8bf33591389dcdff82f0fbd5bf5932a22547c984`. Python Windows 80 passed/1 skipped (symlink privilege); CTest 2/2; native self-test 0; camera thu/đọc RAW được người dùng kiểm thử. Không gán `validated metric` chỉ vì `measured=True`.

## 2. Kiến trúc mục tiêu — modular monolith, UI-first theo lát cắt

```text
┌────────────────────────────── Qt 6 / PySide6 Widgets (UI main thread) ──────────────────────────┐
│ Window/Shell → Projects | Capture & Replay | Inspect 3D (VTK) | Processing & Results             │
│ Navigation / Command Bar / Property Inspector / Event-Run Panel / Status, Progress, Errors       │
└─────────────────────────┬──────────────────────────────────────────────┬─────────────────────────┘
                          │ ViewModels/commands & typed DTO              │ Qt-safe UI signals
                          ▼                                              ▼
             Python Application Services                          Worker Scheduler
             - projects/sessions/registry                         - IO/native/acquisition
             - capture/replay commands                            - 3D processing jobs
             - processing runs / event journal                    - optional AI sandbox
             - artifact & provenance (future)                     - cancel/progress/errors
                          │                                              │
               ┌──────────┼──────────────────────────────────────────────┼──────────┐
               ▼          ▼                                              ▼          ▼
           SQLite       SessionStore                                 VTK adapter   Native adapters
       MetadataStore    immutable RAW files                         render-only   C++20/pybind11
                                                                                      │
                                                                              Orbbec / Geometry
```

**Adapter là ranh giới**, không mặc định mọi node ở hình trên đã có code. Tầng UI không biết chi tiết SQLAlchemy, OrbbecSDK hoặc Open3D. Service trả trạng thái + payload có thể kiểm thử. Renderer VTK update chỉ ở luồng thích hợp; một background worker không thao tác VTK widget trực tiếp.

### Định hướng source tree (chưa tạo thư mục nếu chưa dùng)

```text
src/scantopath/
├─ ui/                 # currently shell; future shell/workspaces/components/viewmodels
├─ application/        # future commands, task orchestration, DTOs, errors
├─ metadata/           # existing SQLite + SQLAlchemy / CLI
├─ storage/            # existing SessionStore v1/v2
├─ domain/             # existing typed RAW contracts; future geometry contracts
├─ acquisition/        # existing Orbbec adapter / native loader / replay CLI
└─ geometry/           # FUTURE algorithms and 3D artifact adapter
cpp/                    # existing acquisition/geometry/native build
```

Không tạo thêm subsystem hoặc new dependencies cho tới đúng phiên cần sử dụng. Dùng `ProcessingRun` của GĐ0 làm lưu lịch sử ở mức metadata; các phiên tương lai muốn lưu artifact state phải có migration/contract được duyệt riêng, không tự thêm cột trực tiếp.

## 3. Data contract và nguồn sự thật

```text
Project → Specimen → ScanSession → RAW Capture (v1/v2, immutable)
                                                │
                                                └→ ProcessingRun → Derived Artifact (future)
                                                                         │
                                                              Quality / Feature / Relation
                                                                         │
                                                           Engineering Digital Replica
```

- **RAW và calibration:** payload không bị edit/crop/filter in place. Derived result lưu source capture IDs, algorithm/version, parameters, checksum, local path, acquisition provenance.
- **Depth projection:** camera **depth** optical frame, `z = uint16 * depth_scale_m_per_unit` (m), `(x,y,z) = ((u-cx)z/fx, (v-cy)z/fy, z)` chỉ là pinhole formula; distortion/invalid-depth và calibration model phải kiểm tra trước khi phát hành cloud/measurement.
- **Color/Depth:** RGB MJPEG 1920×1080, depth Y16 1280×800 theo baseline, chưa đăng ký với nhau. D2C extrinsic translation mm trong RAW; unit conversion về m chỉ ở geometry processing có kiểm thử.
- **Handheld camera:** `T_world_camera(t)` hiện unknown. `PoseEstimate` tương lai phải mang `frame_from`, `frame_to`, `timestamp`, `source`, `quality`, `validity`, `uncertainty`. Nominal scan path không thay thế actual pose estimate.
- **Trust:** `measured` = dữ liệu có nguồn cảm biến; `validated` = đã chứng minh theo tiêu chí metric và reference; `estimated/inferred` = kết quả thuật toán. `missing` không được tô kín rồi coi là quan sát. UI phải biểu diễn khác nhau.
- **Provenance:** liên kết SQLite→RAW là tham chiếu filesystem, không phải atomic transaction chung. V1 read compatibility vẫn bắt buộc; dữ liệu giả không được trộn vào dữ liệu measured.

## 4. UI/worker: luồng xử lý phải giữ responsive

1. UI tạo command có ID và input DTO, service kiểm tra precondition và sinh ProcessingRun nếu cần.
2. Tác vụ dài chạy QThreadPool/worker hoặc subprocess riêng; cập nhật progress/error qua Qt signals, không block UI main loop.
3. Native camera/geometry trả dữ liệu owned, không trả dangling pointer/lifetime camera phụ thuộc PySide6.
4. App Services tạo hoặc đọc artifact; UI chỉ hiển thị results, không tự ghi SHA-256/DB bypass.
5. Hủy/lỗi phải trả trạng thái có nghĩa; không biến RAW hỏng/pose unknown thành default success hoặc geometry filled.
6. VTK/Qt renderer độc lập processing core; benchmark frame time và memory ngay từ session 08.

## 5. Stack theo mức cam kết

**Đang có:** Python 3.12, Pydantic, SQLite/SQLAlchemy, Qt/PySide6 shell, C++20/MSVC/CMake/pybind11/OrbbecSDK v2 và RAW stores.

**Được chọn để triển khai khi đến phiên:** VTK + Qt (08), OpenCV + NumPy (09), Open3D (10–16), Eigen/C++ hot path (khi profiling cho thấy cần). vcpkg được dùng khi thêm native package mà build hiện tại không cung cấp, không nâng ngay chỉ vì lập kế hoạch.

**Tùy chọn/ngoài core:** PCL thay thế có chứng cứ benchmark, RF-DETR hoặc YOLO/ SAM / DINOv3 / Depth Anything 3 / LocateAnything / LingBot-Map trong sandbox riêng theo `roadmap/TECHNOLOGY_SCOPE.md`. Không buộc GPU hoặc framework AI để chạy Projects/RAW/Viewer.

## 6. Ranh giới các giai đoạn (đã thay đổi có chủ đích)

- **GĐ0**: khóa qua PR #3 và PRE-06; không mở lại chức năng foundation trong PR roadmap.
- **GĐ1 (06–08)**: UI Foundation → Project Workspace → VTK Viewer.
- **GĐ2 (09–13)**: RAW Replay → Single-view Geometry → ROI/Filter → Export.
- **GĐ3 (14–16)**: metric calibration/validation → relative pose & registration → fusion & trust.
- **GĐ4 (17–18)**: features/relations → engineering replica.
- **GĐ5 (19–20+)**: object perception, scan guidance và uncertainty/task-specific rescan.

Thứ tự phiên cũ và các mục còn cần được giữ để truy vết ở [`roadmap/SESSION_CROSSWALK.md`](roadmap/SESSION_CROSSWALK.md). Không có motor/turntable/encoder/Raspberry Pi/ESP32 trong current acceptance. Nếu sau này có rig, viết ADR riêng cho pose provider và phần cứng.
