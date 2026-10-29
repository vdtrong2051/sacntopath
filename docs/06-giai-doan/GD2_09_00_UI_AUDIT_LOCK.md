# ScanToPath — GD2-09.00: Qt UI Inventory & Reuse Map (DESIGN LOCK)

- **Ngày:** 29/10/2026
- **Source baseline:** `vdtrong2051/sacntopath`, `main@c890b0bee1a43546e0aa0e76484efeb050c86334`
- **Phạm vi:** kiểm kê tĩnh source Qt, kiểm tra luồng lắp ráp, signal/slot và các test GĐ1 liên quan; **không chỉnh sửa repository**.
- **Kết luận:** `SOURCE_AUDIT_COMPLETE`, `UI_REUSE_DESIGN_LOCKED`; `WINDOWS_RUNTIME_VISUAL_VERIFICATION=NOT_RUN`. Không thay thế gate G2-09-A/B/C.
- **Thứ tự:** 09.00 là pre-implementation design gate; 09.01–09.09 giữ nguyên thứ tự phát triển và nghiệm thu.

## 1. Danh mục UI đã kiểm tra

| ID | Thành phần / `objectName` | Nguồn chính | Hiện trạng source | Quyết định |
|---|---|---|---|---|
| UI-01 | `ScanToPathMainWindow`, `workspaceStack`, `workspaceToolbar` | `src/scantopath/ui/shell/main_window.py` | Một QMainWindow; toolbar 4 navigation button, QStackedWidget 4 page; Qt status bar | **KEEP**; composition root chỉ lắp controller/hook lifecycle cần thiết |
| UI-02 | `workspace_projects` | `ui/workspaces/pages.py`, `modules/project_workspace/presentation/dashboard.py`, `store_management.py` | Host scroll + Recent Store và Project Dashboard được Presenter lắp; không tự mở DB | **KEEP**; không làm lại màn quản lý Project |
| UI-03 | `workspace_capture`, `workspaceScroll_capture`, `workspaceScrollContent`, `workspacePanel` | `ui/workspaces/pages.py` | Placeholder có host Qt thực, chưa có preview/live behavior | **EXTEND** ngay trong host; giữ định danh và layout chung |
| UI-04 | `workspace_processing`, `processingWorkspace` | `modules/project_workspace/presentation/processing_workspace.py` | Bảng ProcessingRun thật, filter theo Project/State, Presenter quản lý UI; `workspacePanel` cũ ẩn nhưng giữ để tương thích | **UNTOUCHED** về giao diện phiên 09 |
| UI-05 | Workspace `inspect3d` | `ui/shell/viewer_bootstrap.py`, `modules/viewer3d/presentation/` | Đã có real/fallback viewer, lazy `create_viewer_controller`, Render Host | **UNTOUCHED**; cấm dựng renderer/preview 3D khác |
| UI-06 | `explorerDock`, `projectExplorer`, `projectExplorerTree` | `ui/components/project_explorer.py` | Cây Project/Specimen/ScanSession/Capture + selection signal | **KEEP**; context source, không nhân bản cây trong Capture |
| UI-07 | `inspectorDock`, `propertyInspector` | `ui/components/property_inspector.py` | Metadata theo selection; verify RAW action chuyên biệt | **EXTEND MINIMAL** chỉ bằng fields/DTO đã xác minh; không nhét camera console vào Inspector |
| UI-08 | `taskDock`, `taskAndEventPanel`, `taskEventTabs` | `ui/components/task_event_panel.py`, `ui/shell/task_dock_chrome.py` | Tác vụ, UI events, SQLite audit; có TaskDockChrome | **KEEP**; tái sử dụng trạng thái/sự kiện, không tạo log pane khác |
| UI-09 | `projectDashboard` + tabs `specimen`,`scan_session`,`capture`,`processing_run` | `modules/project_workspace/presentation/dashboard.py` | Data table + actions, selection sync với Explorer | **KEEP**; không tạo danh mục Capture trùng trong UI thu nhận |
| UI-10 | Project create/edit dialogs | `modules/project_workspace/presentation/edit_dialog.py`, `ui/projects/` | Lệnh tạo/sửa Project/Specimen/Session đã có | **KEEP**; không tạo dialog thứ hai cho cùng metadata |
| UI-11 | `CaptureInspectionController` | `ui/projects/inspection_controller.py`, `project_workspace/presentation/workflows/capture.py` | Kiểm tra RAW bằng worker/QThread; chỉ read-only | **KEEP**; không tái sử dụng làm controller live camera |
| UI-12 | `QtTaskController` | `ui/tasks/controller.py` | Task snapshots / cancel / notices; lifecycle của task system | **REUSE VIA PUBLIC API** nếu đáp ứng; không tạo global task registry thứ hai |
| UI-13 | `hmi_panel.qss` / existing dock chrome | `ui/theme/hmi_panel.qss`, `ui/shell/task_dock_chrome.py` | Theme GĐ1 và chiều cao dock có kiểm thử | **KEEP**; chỉ thêm style selector cho widget mới nếu thực sự cần |

**Số lượng chốt:** 1 main window; 4 workspace; 3 dock. 0 main window mới; 0 workspace mới; 0 dock mới; 0 side-navigation mới; 0 viewer mới.

## 2. Chức năng cần thêm và nơi sở hữu

| Tính năng 09 | UI/container có sẵn | Thành phần mới tối thiểu | Trạng thái |
|---|---|---|---|
| 09.02 RAW Replay | `workspace_capture` + Explorer selection | Action mở Capture từ `SelectionRef`/Capture ID qua application service; không file browser tự ý đọc RAW | **EXTEND** |
| 09.03 RGB-D decode | Không cần Qt mới | Không (decoder ở infrastructure) | **NO_UI_CHANGE** |
| 09.04 Replay Preview | `workspaceScroll_capture` | Một panel capture trong host và một composite RGB/Depth preview; 2 ảnh với resolution độc lập | **NEW CHILD ONLY** |
| 09.05 Native worker | Không cần Qt mới | Không (worker/adapters riêng) | **NO_UI_CHANGE** |
| 09.06 Camera lifecycle | Capture panel + Task/Event Panel | Action group Kết nối/Ngắt/Chụp; trạng thái rõ; events qua API có sẵn | **NEW CHILD ONLY** |
| 09.07 BBox/ROI | RGB/depth preview child | Overlay 2D có thể tùy chỉnh, manual override; confidence/nguồn gợi ý | **NEW CHILD ONLY** |
| 09.08 Capture persist | Existing Project Explorer/Dashboard + Inspector | Action chụp có xác nhận ScanSession; refresh cây sau SQLite register; không tạo bảng Capture mới | **EXTEND VIA SERVICE** |
| 09.09 Integration | MainWindow composition root + navigation/Task lifecycle | Một `CaptureController` của feature (khác `CaptureInspectionController`); shutdown hook | **MINIMAL EXTEND** |

**Không tạo trước hàng loạt widget:** Chỉ tạo skeleton/placeholder thật sự cần để bắt đầu phát triển khi đã có implementation pack được duyệt. `PreviewWidget` có thể sở hữu cả hai image pane và overlays; không bắt buộc 3 class cho 3 QLabel nếu không có lý do test/reuse.

## 3. Bố cục chức năng chốt

```text
MainWindow / existing toolbar (4 tabs)
  LEFT:  explorerDock — Project / Specimen / ScanSession / Capture
  CENTER: workspace_capture (existing QScrollArea + workspaceScrollContent)
    [Context strip: selected Project/Specimen/ScanSession/Capture, readiness]
    [RGB preview] [Depth preview]  (never implicitly align grids)
    [BBox/ROI overlay + manual adjustment + source/confidence]
    [Action row: Open/Replay | Connect | Capture | Stop | Retry]
    [Camera and RAW status: ID, frame timestamps, resolution, encoding]
  RIGHT: inspectorDock — metadata for actual selected entity only
  BOTTOM: taskDock — tasks, UI events and SQLite audit
```

Không tạo ROI popup/window độc lập; điều chỉnh ROI tại preview. Không làm lại Project tree hay duplicate Capture list. `Capture Workspace` phải sử dụng host theo pattern Presenter của GĐ1, giữ `workspace_capture`, `workspaceScroll_capture`, `workspaceScrollContent`, `workspacePanel` và các `objectName` tương thích; tránh thay trực tiếp cả page bằng object làm mất GĐ1 test expectations.

## 4. Điểm xung đột hiện hữu và quyết định khóa

1. **Navigation clears selection:** `main_window._navigate()` gọi `project_explorer.clear_selection()` và `property_inspector.set_selection(None)` khi đổi workspace; các bài `test_gd1_06_4_ui.py` xác nhận hành vi này. **Không sửa rule này.** Để chuyển context sang Capture: tạo `CaptureContext` snapshot có kiểu và ID rõ, lấy từ selection/loaded DTO hợp lệ trước navigation hoặc qua hành động rõ từ Project; phải validate lại khi capture. Context này không phải global Explorer selection giả và phải invalidated khi đổi/mất Project store hoặc session đóng.
2. **Presenter insertion:** Project Dashboard và ProcessingWorkspace đã được Presenter gắn vào existing `workspaceScrollContent`; giữ cách lắp đó. Capture feature sử dụng host `workspace_capture`; không cần đặt thêm `QStackedWidget` toàn ứng dụng. Chỉ dùng child state control nội bộ nếu thực sự giúp giảm widget duplication.
3. **`workspacePanel` compatibility:** Processing Presenter chủ ý giữ/ẩn placeholder cũ; các UI tests kiểm tra objectName/action. Capture nên ẩn/thay nội dung placeholder bằng child panel có lifecycle rõ, nhưng không xóa `objectName` contract trong gói skeleton nếu chưa cập nhật tests được review.
4. **`CaptureInspectionController` là RAW inspector, không phải live camera controller:** không nhập trách nhiệm SDK/lifecycle vào controller này. New feature controller chỉ điều phối application ports; GUI không trực tiếp import storage, sqlite hoặc native DLL.
5. **Task panel is not ProcessingRun:** `TaskSnapshot` chỉ là trạng thái UI, không phải record SQLite `ProcessingRun`. Không ghi fake job history hoặc tái sử dụng ProcessingWorkspace để biểu diễn capture stream.
6. **On-open resource policy:** mở Desktop, chọn workspace Capture, hoặc mở kho Project không được tự bật Gemini 2 hay ghi SQLite. Chỉ operator action mới mở camera/capture.
7. **Preview separation:** Qt process render RGB/Depth ảnh 2D bằng Qt widgets; không kéo VTK child host vào live camera preview và không sửa Viewer 3D.
8. **Close behavior:** add Capture worker into `begin_shutdown` aggregation, nhưng không làm mất các checks project loader/writer/inspector/Viewer đang có; no GUI freeze/abandoned worker.

## 5. File ownership cho GD2-09.01–09.09

| File / folder | Quyết định | Cho phép thay đổi gì |
|---|---|---|
| `src/scantopath/modules/capture/` (new) | **NEW** | Một feature module theo domain/application/infrastructure/presentation, adapter/ports/service/view/controller tối thiểu |
| `src/scantopath/ui/shell/main_window.py` | **EXTEND_MINIMAL** | Wire feature controller, context handoff và close hook; không thêm camera/SQL logic |
| `src/scantopath/ui/workspaces/pages.py` | **EXTEND_MINIMAL** | Giữ workspace host & stable IDs; trạng thái/label khi feature đã thực thi |
| `src/scantopath/ui/components/property_inspector.py` | **EXTEND_ONLY_IF_NEEDED** | Bổ sung metadata qua typed fields; giữ verify RAW behavior |
| `src/scantopath/modules/project_workspace/presentation/controller.py` và `workflows/reading.py` | **EXTEND_ONLY_IF_NEEDED** | Public context handoff/signal từ selection; không nhân bản pipeline project |
| `src/scantopath/ui/tasks/controller.py` | **KEEP_FIRST** | Reuse existing snapshots/notices; đề xuất API mới chỉ khi có gap được chứng minh |
| `src/scantopath/ui/components/task_event_panel.py`, `ui/shell/task_dock_chrome.py` | **KEEP** | Không thay UI layout/dock trong phiên 09 |
| `src/scantopath/modules/project_workspace/presentation/dashboard.py` và `processing_workspace.py` | **KEEP** | Không động đến trừ khi gap tích hợp có bằng chứng và được review |
| `src/scantopath/modules/viewer3d/`, `ui/shell/viewer_bootstrap.py` | **UNTOUCHED** | Không sửa 09 |
| `src/scantopath/ui/theme/hmi_panel.qss` | **EXTEND_ONLY_IF_NEEDED** | Selector cho Capture widget mới; không đổi token/theme chung |
| `src/scantopath/acquisition/`, `storage/`, `metadata/`, `cpp/` | **REUSE_API_FIRST** | 09.05/09.08 gọi APIs; sửa nền chỉ khi blocker được chứng minh qua test và được duyệt |
| `tests/ui/capture/` / `tests/unit/capture/` (new) | **NEW** | Test riêng cho feature và contracts; không rewrite test GĐ1 |

## 6. Kiểm tra ranh giới và regression bắt buộc

- **UI-09-00-A** `SOURCE_PASS`: Source inventory 4 workspace/3 docks + widget names + owners đã lập.
- **UI-09-00-B** `DESIGN_PASS`: Mỗi yêu cầu 09.02–09.09 có host + owner.
- **UI-09-00-C** `DESIGN_PASS`: Mọi NEW child có lý do không thể tái dùng (RGB-D preview/ROI camera actions chưa có).
- **UI-09-00-D** `DESIGN_PASS`: Không có new main window/dock/nav/renderer; tiếp tục kiểm tra thực tế sau code.
- **UI-09-00-E** `DESIGN_PASS / WINDOWS_RUNTIME_PENDING`: Đã khoanh đúng navigation, source invalidation, close dependencies; không có bằng chứng chạy/quan sát UI trên Windows trong phiên kiểm kê tĩnh.
- **UI-09-00-F** `SOURCE_PASS`: Map file KEEP/EXTEND/NEW/UNTOUCHED đã khóa.

**GĐ1 regression phải bảo toàn (ít nhất):**
- `tests/ui/shell/test_gd1_06_4_ui.py`: 3 docks, navigation clear selection, no implicit data/camera.
- `tests/ui/shell/test_gd1_07_9_hmi_qt.py`: one horizontal toolbar, 4 workspace, shortcuts, existing actions.
- `tests/ui/project/test_gd1_r3_2_project_dashboard.py`: Project Dashboard, recent store, selection sync.
- `tests/ui/project/test_gd1_r3_4_processing_workspace.py`: ProcessingRun table, hidden legacy card, no fake record.
- `tests/ui/project/test_gd1_r3_5_integrated_ux.py`: cross-workspace selection, invalid store clears all, read-only historical provenance.
- `tests/ui/shell/test_gd1_r2_2_2_chrome_polish.py`, `test_gd1_r2_2_3c_header_hierarchy.py`: task dock chrome/height.
- `scripts/check_architecture_boundaries.py`: feature import and cross-layer protection; **không sửa gate để né lỗi**.

**New UI tests khi thực thi:** Capture page has existing workspace identity; no camera/DB opened on import/navigation; replay preview correct independent sizes; invalid selection/invalidation disables Capture; ROI interaction; lifecycle close/stop/failed/retry; event panel reuse; no Qt blocking. Video/screenshots từ Windows + Gemini 2 thật là evidence của G2-09-B/C, không thay bằng kết quả kiểm kê source.

## 7. Khóa phạm vi / điều kiện thay đổi quyết định

- `DEC-09-UI-01`: Reuse-first; 1 main window + 4 workspace + 3 dock.
- `DEC-09-UI-02`: Capture module owns **only** new 2D replay/live preview + ROI + controls inside existing workspace.
- `DEC-09-UI-03`: Project selection passes a verified explicit context; global navigation selection-clear remains unchanged.
- `DEC-09-UI-04`: Inspector shows selected entity metadata; Task & Event provides progress/log; ProcessingRun remains reserved for persistent processing (GĐ2-13).
- `DEC-09-UI-05`: Viewer 3D, HMI layout/toolbar and Project/Processing workspaces remain unmodified absent a documented blocker.
- `DEC-09-UI-06`: No changes to RAW/SQLite/C++ API solely for UI convenience.
- `DEC-09-UI-07`: One initial pack after **user explicitly commands implementation**, then code/test/commit individual checkpoints inside VS Code; **no apply-per-step**.

Deviations require a brief design review recording `evidence of gap / affected component / simpler alternative / test impact / user approval` before code.

## 8. Nghiệm thu hiện tại và bước kế tiếp

**Thiết kế đã khóa từ source:** `GD2-09.00 SOURCE_AUDIT_COMPLETE / UI_REUSE_MAP_LOCKED`. **Không tuyên bố** `WINDOWS_VISUAL_PASS`, `GD2-09_DONE` hoặc `G2-09-A/B/C_PASS`. Manual UI proof cần thực thi khi 09.04/09.09 hoàn tất. Kế hoạch 09.01–09.09 vẫn giữ nguyên, chưa tạo implementation pack và chưa viết code.

Khi có lệnh thực thi riêng của user: tạo **một pack khung tối thiểu** có docs + cấu trúc module + scaffold tests, apply **một lần** vào feature branch, sau đó dev/test nhỏ/commit từng bước trong VS Code. Không tự push/PR/merge ở 09.00.

## 9. Source reference

- [MainWindow](https://github.com/vdtrong2051/sacntopath/blob/main/src/scantopath/ui/shell/main_window.py)
- [Workspace factory](https://github.com/vdtrong2051/sacntopath/blob/main/src/scantopath/ui/workspaces/pages.py)
- [Project Dashboard](https://github.com/vdtrong2051/sacntopath/blob/main/src/scantopath/modules/project_workspace/presentation/dashboard.py)
- [Processing Workspace](https://github.com/vdtrong2051/sacntopath/blob/main/src/scantopath/modules/project_workspace/presentation/processing_workspace.py)
- [Explorer](https://github.com/vdtrong2051/sacntopath/blob/main/src/scantopath/ui/components/project_explorer.py)
- [Inspector](https://github.com/vdtrong2051/sacntopath/blob/main/src/scantopath/ui/components/property_inspector.py)
- [Task UI](https://github.com/vdtrong2051/sacntopath/blob/main/src/scantopath/ui/components/task_event_panel.py)
- [GĐ1 UI tests](https://github.com/vdtrong2051/sacntopath/tree/main/tests/ui)
