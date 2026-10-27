# GĐ1 — 06.1: Rà soát và chốt thiết kế Desktop UI Foundation

**Trạng thái:** thiết kế hoàn thành trên commit `main` `93e5afb86081c2018987d86bf83d26b202a85f39` (18/10/2026). Chưa nghiệm thu Windows, chưa triển khai UI mới. **Phạm vi 06.1 chỉ có tài liệu, không sửa GĐ0.** Tham khảo: [Roadmap](../../../ROADMAP.md), [Architecture](../../GD0/ARCHITECTURE.md), [ADR-001](../../../decisions/ADR_001_UI_FIRST.md).

## 1. Kết quả audit repository hiện hành

| Thành phần | Đã xác minh trong source | Vấn đề / việc cần làm |
|---|---|---|
| `ui/main.py` | Một `QMainWindow` chứa `QTabWidget` bảy trang tĩnh: Project, Acquisition, Geometry, Quality, Features, Replica, Export | Chưa có workspace thật, navigation state, service injection, worker, dock hay status/error. Tạo shell mới ở 06.3. |
| `metadata/store.py` | `MetadataStore`: `list_projects`, `get_project_tree`, `get_capture(verify_raw)`, `get_processing_run`, `list_events`, CRUD + audit | Backend thực đã có; chỉ nối UI qua application service ở 07, **không** SQLAlchemy trong QWidget. |
| `storage/session_store.py` | Có v1/v2, `read_raw`, `read_capture`, SHA-256, `COMMITTED` | Không ghi lại RAW, không decode MJPEG/Y16 ở 06. |
| `acquisition/capture_once.py` | One-shot/verify CLI độc lập | Không mở camera khi mở UI, tránh thiết bị và SDK thành hard-dependency. |
| `pyproject.toml` | `ui` extra là `PySide6>=6.7,<7`; chưa có VTK | Giữ Qt Widgets, không thêm VTK/Open3D ở 06. |
| `cpp` | Geometry smoke + pybind11/Orbbec | Không sửa native C++ ở 06.1–06.6. |

Các chức năng GĐ0 đã có backend nhưng **chưa có UI vận hành**. Đặc biệt không được ghi “Projects UI kết nối SQLite” tại 06; đó là cổng phiên 07.

## 2. Bố cục và hành vi được chốt

Một cửa sổ `QMainWindow` dùng Qt Widgets, bốn workspace trong `QStackedWidget`, ba `QDockWidget` dùng chung và `QStatusBar`:

```text
QMainWindow
  QMenuBar / QToolBar: File, View, Help; workspace navigation
  central: QStackedWidget
    1. Projects                [06: placeholder; 07: SQLite thật]
    2. Capture & Replay        [06: placeholder; 09: RGB-D replay]
    3. Inspect 3D              [06: placeholder; 08: VTK PLY]
    4. Processing & Results    [06: UI task demo; 07/13: ProcessingRun]
  left QDockWidget:   ProjectExplorer     [06: trạng thái trống / disabled]
  right QDockWidget:  PropertyInspector   [06: không có selection]
  bottom QDockWidget: TaskAndEventPanel   [06.5: task demo/progress/cancel/error]
  QStatusBar: workspace, nguồn dữ liệu, trạng thái task, lỗi
```

- Không giữ bảy tab làm bảy sản phẩm độc lập. Quality/Features/Replica/Export sẽ là chức năng của các workspace khi tới phiên tương ứng.
- 06.3 xây navigation thật, 06.4 xây dock; phải resize, minimum-size hợp lý và kiểm tra 1366×768/1920×1080, high-DPI. UI nhãn tiếng Việt nhưng ID định danh bất biến.
- `main.py` vẫn là entrypoint `python -m scantopath.ui.main`. Không viết UI entrypoint thứ hai.
- Mặc định không mở SQLite/camera/VTK tại import, không chạy background task cho đến khi người dùng yêu cầu.
- Có thông báo `Chưa triển khai` thay vì nút trông như hoạt động; mock/fixture phải ghi rõ.

## 3. Ranh giới kiến trúc

```text
PySide6 widgets (GUI thread)
  -> presenter/viewmodel (selection, navigation, UI state)
     -> application service (validation, commands/queries)
        -> GĐ0 MetadataStore / SessionStore adapters (ở phiên 07/09)
        -> Viewer adapter (08)
        -> Camera adapter (sau 09)
        -> Workers (06.5; không thao tác QWidget trực tiếp)
```

**Điều cấm:** QWidget import SQLAlchemy/OrbbecSDK/Open3D, tự sửa RAW hoặc tự tạo giá trị tọa độ/độ chính xác từ dữ liệu chưa chứng minh. Không tạo dependency graph/hệ event bus mới khi PySide6 signals và Python service là đủ. Worker không cập nhật QWidget/VTK renderer ngoài GUI thread.

### Hợp đồng dữ liệu tối thiểu (thiết kế; **chưa phải module đã tạo**)

| Type | Fields / semantics | Phiên implement |
|---|---|---|
| `WorkspaceId` | enum `projects`, `capture`, `inspect3d`, `processing` | 06.2 |
| `UiDataState` | `not_implemented`, `fixture`, `measured`, `estimated`, `validated`, `insufficient_evidence` | 06.2 |
| `CommandRequest` | `request_id`, `command`, `parameters`, `source_context` | 06.2 |
| `CommandOutcome` | `request_id`, `status`, `value?`, `error_code?`, `message?`; status success/fail/cancel/not_implemented | 06.2 |
| `TaskSnapshot` | `task_id`, `title`, `state`, `progress?`, `can_cancel`, `error?`; terminal success/failed/cancelled | 06.2/06.5 |
| `SelectionRef` | `entity_type`, `entity_id`, `source_id?`; không có giả định pose/units | 06.2/07 |

`measured` chỉ nghĩa là nguồn cảm biến; **không đồng nghĩa** `validated`. `estimated/inferred` không được gắn nhãn observed. Planned handheld path không phải actual pose; Color MJPEG 1920×1080 và Depth Y16 1280×800 vẫn chưa aligned.

### Commands/API dự kiến — chưa tồn tại

```text
WorkspaceNavigation.select(WorkspaceId) -> UiNavigationState
TaskService.submit(CommandRequest) -> TaskHandle
TaskService.cancel(task_id) -> accepted/rejected
ProjectQueryService.list_projects() -> ProjectSummary[]   # 07
ProjectQueryService.get_project_tree(id) -> ProjectTree     # 07
CaptureQueryService.verify_capture(id) -> CaptureStatus   # 07/09
```

Tên class có thể được tinh giản ở 06.2 nhưng **không tạo service chưa có consumer**. Service không trả Qt Widget, SQLAlchemy Session hay con trỏ native trong DTO.

## 4. Interaction matrix / feature gates

| Tác vụ | Trạng thái tại 06 | Lúc hoạt động thật | Lỗi phải phân biệt |
|---|---|---|---|
| App launch + chuyển workspace | `enabled` | 06.3 | Init/close error |
| Explorer / xem Project | `not_implemented` | 07 | DB missing, empty projects, invalid project |
| Camera / RGB-D replay | `not_implemented` | 09 | No camera, corrupt RAW, timestamp mismatch |
| View PLY | `not_implemented` | 08 | Unsupported file, no viewer |
| Task demo GUI | `fixture` có nhãn | 06.5 | Fail, cancel, unknown progress |
| ProcessingRun history | `not_implemented` | 07/13 | Missing run, stale state |
| Metric/registration/fusion | `not_implemented` | 14–16 | Pose unknown, invalid scale, insufficient evidence |

Ở 06, không dùng mock để giả vờ đọc RAW, đo 3D hoặc chạy ML. Không đánh đồng UI task demo với `ProcessingRun` đã lưu trong SQLite.

## 5. Worker/shutdown safety contract (thực thi ở 06.5)

1. QWidget và VTK renderer chỉ được cập nhật trên thread UI.
2. Queue hữu hạn; mỗi job có đúng một trạng thái kết thúc: `succeeded`, `failed` hoặc `cancelled`.
3. `cancel_requested` không đồng nghĩa `cancelled`: worker xác nhận sau khi đã ngừng; tác vụ native block phải có chính sách rõ ràng.
4. Tiến độ unknown hiển thị indeterminate, không giả phần trăm.
5. Thoát ứng dụng khi có task chạy: dừng nhận job mới, gửi cancel hợp tác, shutdown giới hạn thời gian, không để dangling Qt signal.
6. Lỗi worker truyền qua outcome + log an toàn, không làm Qt event loop crash.
7. Tránh chuyển trực tiếp khung MJPEG/Y16 kích thước lớn qua signal khi chưa benchmark (09).

## 6. Target source tree — **không tạo thư mục rỗng ở 06.1**

```text
src/scantopath/
  ui/
    main.py               # hiện có, thay dần ở 06.3
    shell/                # main_window/navigation 06.3
    components/           # Explorer/Inspector/TaskPanel 06.4
    workspaces/           # 4 trang 06.3
    viewmodels/           # state/presenter 06.2+
  application/
    contracts/            # typed DTO 06.2
    tasks/                # worker 06.5
  metadata/               # GĐ0: giữ nguyên
  acquisition/            # GĐ0: giữ nguyên
  storage/                # GĐ0: giữ nguyên
  domain/                 # GĐ0: giữ nguyên
```

## 7. Nghiệm thu 06.1 trên Windows

- Source review trên `main` commit đã ghi: **đã làm**. UI audit, layout, interaction states, DTO seam và worker constraints: **đã lập**.
- Patch phải chỉ thêm `docs/gd1/06_1_UI_AUDIT_AND_DESIGN.md` và `docs/gd1/06_DELIVERY_GATES.md`; không sửa `src/`, `cpp/`, `tests/`, `pyproject.toml`, dữ liệu `scantopath-data/`.
- Smoke thủ công `python -m scantopath.ui.main` **với UI cũ**: mở/đóng bình thường (chưa chạy trên máy Windows tại thời điểm soạn).
- Hồi quy `pytest -q -rs tests` (Windows baseline 80 pass + một skip do quyền symlink), CTest `2/2`, native self-test exit 0; **chưa chạy ở máy Windows cho patch này**.
- Chỉ sau khi review/kiểm thử và commit trên nhánh chung GĐ1: chuyển sang **06.2**. Không ghi 06.1 là UI mới đã hoàn thành.
