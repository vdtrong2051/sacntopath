# Kiến trúc ScanToPath — GĐ1 đang triển khai

**Scope:** audit read-only trên GitHub `ff45ccf87ce770e25eedf6e12df6bb5aaa958734` + nhật ký kiểm thử R6 do người vận hành cung cấp. Không thay thế [tài liệu GĐ0](../../GD0/ARCHITECTURE.md), không tự tuyên bố toàn bộ SOLID/clean architecture đã chứng minh.

## Thành phần chạy thực

```text
Qt 6 / PySide6 Desktop (main thread)
  ├── ui/shell/main_window.py: composition root, navigation, dock lifecycle
  ├── ui/shell/viewer_bootstrap.py: chọn live/fallback, inject provider
  ├── modules/project_workspace/presentation/: QObject controller & workflows
  │     └── application services → metadata SQLite / RAW registry (explicit open)
  └── modules/viewer3d/presentation/: live tools + inspector bridge
        │ request/typed DTO (không import VTK)
        ▼
      infrastructure/resident_poc/async_session.py
        │ queue + IPC + shared-memory frame (copy/ACK)
        ▼
      Resident VTK subprocess: geometry reader, camera, picking, grid, actors

Native C++20 (CMake) / Gemini2 (OrbbecSDK v2.10.6) → acquisition/RAW GĐ0
```

- Qt GUI không đọc/parse PLY trong paint/event loop. VTK thuộc **tiến trình con cô lập**, tránh biến crash renderer thành crash Qt trực tiếp.
- `SceneSource`, `SceneDescriptor`, `SceneSelectionRef` là DTO không phụ thuộc renderer; liên kết `source_sha256` + `scene_revision`, loại điểm/mặt và XYZ được kiểm tra trước khi hiển thị.
- `frame_revision`, `input_revision`, `scene_revision` chống frame cũ. Shared memory frame được copy trước khi ACK; coalescing ưu tiên input mới.
- `.ply` chứa vertex-only hiển thị **points**; `.ply` có faces và `.obj` hiển thị **mesh**. Import hình học ≠ tạo mesh từ dữ liệu camera. Không tự bịa units/coordinate_frame; `unknown` cho tệp bên ngoài chưa có chứng cứ.
- Grid Oxy, triad, bounding box, selection là công cụ **hiển thị**, không xác lập mặt chuẩn đo lường hay world pose.
- GĐ0 thu nhận Gemini 2 đã có RAW và persistence; GĐ1 Viewer chưa phải scan/filter/normal/path pipeline. Lộ trình tích hợp xem [ROADMAP](../../../ROADMAP.md).

## Ranh giới sở hữu và bất biến

| Ranh giới | Chủ sở hữu | Hợp đồng |
|---|---|---|
| UI ↔ ứng dụng | Qt controller / typed DTO | Qt thread không chạy SQL/VTK/blocking IPC |
| Project ↔ metadata | Feature application service | SQLite chỉ mở/ghi theo command tường minh; không tự tạo kho lúc startup |
| Acquisition ↔ RAW | GĐ0 storage | RAW bất biến, bytes/manifest SHA-256, không tự sửa/align dữ liệu gốc |
| Qt ↔ renderer | Asynchronous session | Child lifecycle và timeout; frame/pick phải đúng scene; child mất thì không dùng stale frame |
| Geometry ↔ kết quả | Scene contracts | Không tự gán metric/pose/calibration hoặc cell ID theo CAD |
| Fallback ↔ live | Viewer bootstrap | PNG compatibility vẫn tồn tại; không trộn dữ liệu của hai chế độ |

## Giới hạn kiến trúc và khoản nợ kỹ thuật

1. `ui/shell/main_window.py`, `modules/viewer3d/presentation/{controller,view,interactive_controller}.py`, `ui/workspaces/pages.py` là các điểm phải kiểm tra khi sửa UI; không coi độ dài file là bằng chứng duy nhất của SOLID.
2. Các re-export compatibility `ui/projects/*`, `application/projects/*` **chưa được xác nhận không có caller**; không xóa ở R7. R8 sẽ lập map hợp đồng/import rồi đề xuất xử lý nếu cần.
3. Đóng Qt khi native **thật sự đang bận**, native C++ crash injection, GPU/VRAM và actual display-present latency **chưa có bằng chứng hoàn chỉnh**. R4.5 chỉ quyết định kiến trúc B có điều kiện.
4. R6 automated 14/14 từ log được cung cấp: đây là kết quả **kiểm thử**, không chứng minh mọi nhánh bảo vệ native hay HMI đã được thử.

**Nguồn:** [R4.5 decision](../../GD1/R1-R5/R4_05_RENDERER_ARCHITECTURE_DECISION.md) · [R5.1](../../GD1/R1-R5/R5_01_SCENE_GEOMETRY_CONTRACTS.md) · [R5.3](../../GD1/R1-R5/R5_03_INTERACTION_INSPECTOR_UX.md) · [07.12 Risk Register](../../GD1/07/07_12_CONSOLIDATION_RISK_REGISTER.md).
