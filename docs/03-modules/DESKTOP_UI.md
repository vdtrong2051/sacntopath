# Desktop UI — Qt Shell, điều hướng và vòng đời ứng dụng

> **owner:** `ui/shell` và feature presentation · **as_of_commit:** `0557c0d4fed9a3df3b180fc9872c6d3293b5f0d5` · **verified_at:** 2026-10-28  
> **scope:** Qt Widgets/PySide6 GĐ1, bốn workspace, dock/Inspector, task state, viewer lazy-load và đóng ứng dụng · **implementation:** IMPLEMENTED trong source · **manual HMI/DPI:** NOT_TESTED mới trong DOC-03B; R6 overall PENDING.  
> **source-of-truth:** `src/scantopath/ui/`, `modules/project_workspace/presentation/`, `modules/viewer3d/presentation/` và UI tests.

## 1. Mục đích và người dùng

Desktop UI là lớp điều khiển công việc kỹ thuật: chọn dự án, duyệt metadata/RAW, xem file hình học 3D, theo dõi task và phản hồi lỗi. Nó **không** chứa thuật toán xử lý nặng và không tự mở camera/SQLite khi khởi chạy. Ví dụ: người dùng mở ứng dụng, chọn không gian Dự án và chủ động chọn kho; khi chuyển sang Kiểm tra 3D, Viewer mới được tạo theo nhu cầu.

Một ứng dụng nhìn đẹp nhưng bị block khi nạp PLY lớn hoặc đóng cửa sổ làm treo child process chưa đạt hợp đồng kỹ thuật. Vì thế vòng đời và trạng thái bất đồng bộ quan trọng ngang bố cục HMI.

## 2. Khả năng đã có và chưa có

| Tính năng | Có trong source | Giới hạn |
|---|---|---|
| `ScanToPathMainWindow` + QMainWindow/QToolBar | Có, điều hướng 4 workspace | không khẳng định mọi màn hình/DPI đều đã nghiệm thu |
| Project Explorer, PropertyInspector, Task/Event dock | Có các components chung | phụ thuộc người dùng mở kho/Viewer riêng |
| Recent Projects / dashboard / form metadata | Có ở Project presentation | không tự tạo SQLite ở startup |
| Viewer live khi chọn `INSPECT3D` | Có, lazy create | native VTK ở child process, không chạy trực tiếp trong Qt thread |
| Qt offscreen/minimal preview | Có fallback | test offscreen **không** chứng minh giao diện native thực |
| Xử lý point cloud/mesh từ RAW, đường robot | **Chưa tích hợp** | trang Processing không phải thuật toán đã chạy |

## 3. Cấu trúc và source

```text
python -m scantopath.ui.main
  → QApplication → ScanToPathMainWindow (QMainWindow)
      ├─ NavigationViewModel → QStackedWidget: PROJECTS/CAPTURE/INSPECT3D/PROCESSING
      ├─ project_explorer + property_inspector + task_event_panel (docks)
      ├─ ProjectWorkspaceController → workflows read/write/check
      ├─ QtTaskController → tiến độ/thông báo
      └─ lazy viewer_bootstrap.create_viewer_controller()
               ├─ Qt offscreen/minimal → Viewer3DController (fallback)
               └─ Qt màn hình thật → InteractiveViewer3DController
                                      ↕ CoalescingRenderSession → Render Host
```

| File | Trách nhiệm |
|---|---|
| `src/scantopath/ui/main.py` | tạo `QApplication`, font baseline, window và event loop |
| `src/scantopath/ui/shell/main_window.py` | composition root: toolbar, dock, menu, routing, closeEvent |
| `src/scantopath/ui/shell/viewer_bootstrap.py` | chọn live native/fallback theo Qt platform |
| `src/scantopath/ui/shell/viewer_inspector_bridge.py` | chuyển descriptor/selection Viewer vào Inspector chung |
| `src/scantopath/ui/components/` | Explorer, Inspector, TaskAndEventPanel |
| `src/scantopath/ui/workspaces/pages.py` | trang, metadata hiển thị và placeholder có nhãn |
| `src/scantopath/ui/viewmodels/navigation.py` | navigation state |
| `src/scantopath/ui/tasks/controller.py` | hiện trạng Task và command trên Qt |
| `src/scantopath/modules/project_workspace/presentation/` | các workflow nghiệp vụ, không dồn trong shell |

## 4. Input/output và hợp đồng UI

| Đầu vào | Đầu ra | Ranh giới |
|---|---|---|
| `WorkspaceId` (`projects`, `capture`, `inspect3d`, `processing`) | workspace hiển thị + status | chỉ điều hướng UI; không tự tạo data |
| `CommandRequest` / `CommandOutcome` | lệnh, trạng thái, error code | JSON DTO bất biến ở application/contracts |
| `TaskSnapshot` / `TaskState` | tiến độ/busy/error/cancelled | không biến task UI thành ProcessingRun chạy thuật toán |
| Project selection | DTO/Inspector Project | không đồng nhất với scene selection |
| `SceneSelectionRef` (point/face) | Inspector XYZ, nguồn SHA/scene revision | tọa độ theo file ngoài, units/frame `unknown` |
| UI action (mouse/keyboard) | command đến controller | thao tác VTK native ở Render Host, không trong Qt |

`UiDataState` có các giá trị `not_implemented`, `fixture`, `measured`, `estimated`, `validated`, `insufficient_evidence`. Đây là **nhãn nguồn/giao diện**, không phải tự chứng nhận mét/độ chính xác. Một button placeholder phải hiển thị rõ chưa thực hiện; không tạo Project/RAW giả để làm đẹp dashboard.

## 5. Luồng vận hành bình thường

1. `ui.main.main()` tạo/reuse `QApplication`, bảo đảm font có point size hợp lệ rồi tạo `ScanToPathMainWindow`.
2. Shell tạo toolbar, status bar, dock, QStackedWidget và các controller, giữ `viewer3d=None` lúc khởi tạo. `QTimer.singleShot(0, _initialize_dock_layout)` áp preset khi Qt event loop sẵn sàng.
3. Khi người dùng nhấn Dự án, controller mới mở dialog chọn kho; dữ liệu được nạp qua worker/service. Thanh trạng thái/Inspector cập nhật theo tín hiệu từ workflow.
4. Khi chuyển `inspect3d`, `_ensure_viewer3d()` gọi `create_viewer_controller()`, thay placeholder trong stack; trên Windows thật tạo controller live và Render Host cô lập. Lúc test `QT_QPA_PLATFORM=offscreen`, dùng preview phù hợp thay vì giả làm native process đã được kiểm.
5. Lệnh từ toolbar Viewer đi vào presenter/async session; Qt nhận một **bản sao RGB** qua frame transport, không giữ buffer mà child có thể ghi đè.
6. Khi đóng cửa sổ, `closeEvent` điều phối dừng worker/Viewer không chặn quá mức; nếu còn shutdown pending, không được hủy child trái hợp đồng.

## 6. Bất biến UI và kiến trúc

- Chỉ Qt main thread được thao tác QWidget; IO/SDK/VTK nặng phải qua lớp xử lý riêng.
- Qt shell không import VTK runtime hoặc mở Orbbec SDK khi import.
- Không tự mở/migrate SQLite và không tạo RAW lúc startup.
- Không giả nguồn measured/metric; fallback offscreen là fallback, không là native live proof.
- Khi đổi workspace/scene, kết quả cũ không được cập nhật lại Inspector như thể thuộc lựa chọn mới.
- `objectName` được các UI tests bảo vệ; đổi tên widget có thể phá hợp đồng tự động hóa/HMI.
- Qt layout dựa vào `availableGeometry` và logical pixels, không hardcode màn hình 14 inch; vẫn cần kiểm DPI thực tế.

## 7. Vòng đời, trạng thái và đóng

```text
APP_START → SHELL_READY (camera/DB chưa mở)
  ├─ CHOOSE_PROJECT → PROJECT_LOADING → PROJECT_READY/PROJECT_ERROR
  ├─ ENTER_INSPECT3D → VIEWER_CREATING → VIEWER_IDLE/READY/ERROR
  └─ CLOSE_REQUEST → stop project/task + viewer shutdown
                   ├─ outstanding shutdown → CLOSE_DEFERRED
                   └─ children stopped → APP_CLOSED
```

`ScanToPathMainWindow.closeEvent()` và `LiveViewer3DController.begin_shutdown()` phải phối hợp: nếu Render Host/worker đang dừng, shell không giả định việc gọi `close()` là đã giải phóng tiến trình. `QTimer.singleShot(...)` chỉ phục vụ lịch event loop, không là bằng chứng real HMI khi native đang bận. Kết quả test offscreen không bảo đảm vòng đời xử lý lỗi C++ thật.

## 8. Lỗi và phục hồi

| Sự kiện | UI thấy gì | Hành động đúng | Test |
|---|---|---|---|
| User chọn DB không tồn tại | trạng thái lỗi, không tạo DB | chọn lại root đã có | `tests/ui/project/test_gd1_07_8_qt.py` |
| Viewer/VTK child chết | báo lỗi/retry hoặc fallback phù hợp | retire session và clear stale frame/selection | `tests/ui/viewer/test_gd1_r5_2_live_viewer.py` |
| UI chưa có frame ACK | công cụ pick bị disable | chờ frame thật; không bỏ guard | `tests/ui/viewer/test_gd1_r5_3_qt.py` |
| Cửa sổ nhỏ/DPI cao | dock phải điều chỉnh; nút/tooltip không bị ép cắt | dùng screen geometry, HMI thủ công 100/125/150% | `tests/ui/shell/test_gd1_r2_2_3b_actual_dock_geometry.py` |
| Close khi worker bận | phải dọn/lùi đóng theo trạng thái | trace lifecycle thay vì kill tùy tiện | acceptance R6: NOT_TESTED real native busy |
| Command timeout | task error có ngữ cảnh | retry hoặc cancel theo hợp đồng | `tests/unit/task/test_gd1_06_5_core.py` |

## 9. Ví dụ an toàn

Tại repo Windows, `.venv` đã có PySide6 và VTK theo các optional dependencies. **Chạy màn hình thật**, không đặt `QT_QPA_PLATFORM=offscreen`:

```powershell
Remove-Item Env:QT_QPA_PLATFORM -ErrorAction SilentlyContinue
& .\.venv\Scripts\python.exe -X utf8 -m scantopath.ui.main
```

Ứng dụng chạy và hiện QMainWindow, chưa cần camera/DB. Tác dụng phụ: mở cửa sổ; chỉ kết nối nguồn khi user yêu cầu. Nếu muốn kiểm tự động (không mở UI thật), dùng môi trường offscreen **chỉ cho pytest**:

```powershell
$env:QT_QPA_PLATFORM = 'offscreen'
& .\.venv\Scripts\python.exe -X utf8 -m pytest -q `
  tests/ui/shell/test_gd1_06_3_ui.py `
  tests/ui/shell/test_gd1_07_9b_polish_qt.py `
  tests/ui/viewer/test_gd1_r5_3_qt.py
Remove-Item Env:QT_QPA_PLATFORM -ErrorAction SilentlyContinue
```

Điều kiện PASS của pytest không thay thế tương tác thật với DPI/native/gpu.

## 10. Hiệu năng và độ đo HMI

Kiến trúc có worker/Render Host nhằm hạn chế block Qt event loop. Benchmark Render Host 1K/100K/1M là chỉ số hoàn thành workload render, **không** tương đương FPS vật lý hoặc input-to-display-present. Cần đo thêm: DPI 100/125/150, reopen/close nhiều vòng, native busy close, lỗi C++ thật, RAM+VRAM của cả Qt và child process. R6 tổng thể vẫn `PENDING`, dù Full regression tự động PASS.

## 11. Mở rộng giao diện

Tính năng mới bắt đầu ở module/controller/service tương ứng; `main_window.py` chỉ thêm wiring, không nhét logic SQL/VTK vào shell. Khi thêm dock/shortcut phải kiểm tương thích `objectName` và navigation UI tests; khi thêm tác vụ phải định nghĩa progress/cancel/error lifecycle. Thay viewer bootstrap cần thử cả nhánh live và offscreen; không cắt test để đạt giới hạn dòng tĩnh. Sửa UI/UX phải nghiệm thu màn hình thật nếu ảnh hưởng DPI/bố cục.

## 12. Test tự động và thủ công

| Mảng | Test gợi ý hiện hành |
|---|---|
| Shell/toolbar/navigation | `tests/ui/shell/test_gd1_06_3_ui.py`, `test_gd1_r2_1a_native_navigation.py` |
| Dock/compact layout | `tests/ui/shell/test_gd1_r2_2_3b_actual_dock_geometry.py`, `test_gd1_r2_2_3c_header_hierarchy.py` |
| Project UI | `tests/ui/project/test_gd1_r3_5_integrated_ux.py` |
| Viewer UI | `tests/ui/viewer/test_gd1_r5_2_live_viewer.py`, `test_gd1_r5_3_qt.py` |
| Task | `tests/ui/task/test_gd1_06_5_qt.py` |

Sử dụng `scripts/verify.ps1 -Profile Quick` cho phản hồi nhanh, `-Profile Full` trước commit và `Acceptance` chỉ cho các gate tự động. Bản nghiệm thu visual HMI phải được operator ghi phương pháp, DPI, video/ảnh và trạng thái theo từng ca; DOC-03B không thực hiện những thao tác đó.

## 13. Quyết định và tồn đọng

Kiến trúc desktop theo Qt/PySide6 + modular monolith + các lớp controller và worker (ADR-001). Viewer VTK tách tiến trình theo lựa chọn có điều kiện R4.5; thiết kế này không loại bỏ nhu cầu tiêm lỗi native C++ thật hoặc đo close-while-busy. Không chuyển kế hoạch Capture Streaming/Scan-to-Path thành nút UI giả đã hoàn thành. Xem [Viewer 3D](VIEWER_3D.md) cho vòng đời frame/ACK và [Project](PROJECT_WORKSPACE.md) cho DB workflow; nội dung giao diện cốt lõi đã đủ ở trang này.
