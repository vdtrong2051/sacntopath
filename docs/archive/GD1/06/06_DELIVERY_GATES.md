# GĐ1 / Phiên 06 — Ma trận giao hàng từng bước

**Nguồn chuẩn:** [thiết kế 06.1](06_1_UI_AUDIT_AND_DESIGN.md), [ROADMAP](../../../ROADMAP.md), [ADR-001](../../../decisions/ADR_001_UI_FIRST.md).

**Một nhánh chung `feat/gd1-desktop-ui` cho toàn bộ GĐ1**, không tạo nhánh 06.2/06.3 riêng và không merge đến khi nghiệm thu GĐ1. Mỗi bước có commit riêng sau khi kiểm thử.

| Bước | Phạm vi thực thi | Acceptance gate | Không đưa vào |
|---|---|---|---|
| **06.1** Audit/UI design | Hai tài liệu GĐ1, source audit, interaction/services/worker contract | Review docs, smoke UI baseline, không sửa production | PySide6 UI mới / VTK / AI |
| **06.2** DTO/Service seam | `application/contracts`, presenter/state cần thiết | Unit tests không cần Qt/camera, strict command outcomes; backward regression | SQLite ORM trong QWidget, service chưa có consumer |
| **06.3** Window/navigation | Thay `ui/main.py`, shell và 4 pages | Qt offscreen smoke + Windows launch/close, switch 4 workspace, no auto SDK | VTK/PLY, Gemini live frame |
| **06.4** Reusable panels | Explorer, Inspector, TaskAndEventPanel, status | Resize, empty/disabled/selected states, keyboard/focus | SQLite thật trước 07 |
| **06.5** Worker | Bound queue, cooperative cancel, progress, errors, shutdown | UI timer không block, terminal signal một lần, no direct QWidget from thread | Native camera capture, AI / geometry jobs |
| **06.6** Integrated acceptance | Automated GUI tests và hồ sơ nghiệm thu, fix scope only | Python regression, CTest, native self-test, Qt GUI manual smoke; review commits | Tuyên bố phiên 07–08 đã xong |

## Lộ trình thực thi

```text
06.1 (docs, baseline) → 06.2 (typed contracts) → 06.3 (main window)
→ 06.4 (common docks) → 06.5 (worker system) → 06.6 (acceptance)
→ Phiên 07 (Project Workspace kết nối SQLite thật)
→ Phiên 08 (VTK Viewer mở PLY)
```

## Các biện pháp bảo vệ GĐ0

- Không sửa `metadata/store.py`, `storage/session_store.py`, RAW schemas, C++ Orbbec bindings hoặc CMake ở phiên 06; đề xuất ADR mới nếu bắt buộc thay đổi.
- Mặc định không tự mở camera hoặc khởi tạo SQLite khi import UI.
- `ProcessingRun` của GĐ0 vẫn là lịch sử xử lý metadata; task demo UI dùng `fixture` không ghi vào DB.
- Không yêu cầu GPU, PCL, SAM, Open3D hoặc VTK ở 06; VTK chỉ thêm ở phiên 08.
- Duy trì `python -m scantopath.ui.main` và các command line GĐ0.
- Kiểm thử offscreen không thay thế GUI smoke thực với high-DPI, focus, resize.
- Công việc đầu tiên sau khi nghiệm thu tài liệu **chỉ là 06.2**, không thực thi cả sáu bước cùng lúc.
