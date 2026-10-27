# GĐ1 — 06.4: Explorer, Inspector, Task & Event Panels

**Nền:** `feat/gd1-desktop-ui` tại commit `25a61036e976537365ee7dc0c960db49d6754c90` (đã có 06.3).
**Phạm vi:** bổ sung ba `QDockWidget` có thể ẩn/hiện, dữ liệu tham chiếu, trạng thái rỗng, lựa chọn và thông báo UI. **Chưa thực hiện 06.5 (workers), 07 (SQLite UI), 08 (VTK) và QSS cải tiến.**

## 1. Thay đổi

| Tệp | Chức năng |
|---|---|
| `src/scantopath/ui/components/project_explorer.py` | Cây dự án nhận `tuple[ExplorerNode, ...]` được truyền vào; chọn mục trả `SelectionRef`. Mặc định rỗng, không đọc DB. |
| `src/scantopath/ui/components/property_inspector.py` | Hiển thị **chỉ** loại đối tượng, mã định danh và mã nguồn có thực trong `SelectionRef`; chưa truy xuất metadata hay phép đo. |
| `src/scantopath/ui/components/task_event_panel.py` | Hiển thị `TaskSnapshot` được truyền vào; `progress=None` thành “Không xác định”; lưu tối đa 200 thông báo **trong RAM của UI**. Không tạo task hay `ProcessingRun`. |
| `src/scantopath/ui/components/__init__.py` | Export public classes và `ExplorerNode`. |
| `src/scantopath/ui/shell/main_window.py` | Gắn dock trái/phải/dưới; menu **Hiển thị** để ẩn/hiện, đồng bộ SelectionRef với `NavigationViewModel`. |
| `tests/test_gd1_06_4_ui.py` | 18 trường hợp Qt offscreen (bắt buộc chạy trên máy Windows có PySide6). |

## 2. Giao diện và ngữ nghĩa dữ liệu

```text
QMainWindow
├─ Central: thanh navigation 06.3 + 4 workspace 06.3 (giữ nguyên)
├─ Left QDockWidget: Cây dự án
│    ├─ Chưa tải dữ liệu dự án (trạng thái ban đầu)
│    └─ QTreeWidget (chỉ hiển thị khi có ExplorerNode thực/fixture được cấp)
├─ Right QDockWidget: Thuộc tính
│    ├─ Chưa chọn đối tượng (ban đầu)
│    └─ Loại + mã định danh + mã nguồn nếu có, KHÔNG tự suy ra thuộc tính
└─ Bottom QDockWidget: Tác vụ và thông báo
     ├─ Tác vụ: QTreeWidget nhận TaskSnapshot; không chạy task
     └─ Thông báo UI: lịch sử thao tác chuyển workspace trong phiên hiện tại
```

- Cây dự án được **tiêm dữ liệu**, chưa kết nối SQLite tới phiên 07; trên màn hình khởi động không có bất kỳ Project/Specimen/Capture giả nào.
- Khi chọn một nút có `SelectionRef`, Inspector và `NavigationViewModel.selection` phải cùng tham chiếu đó.
- Đổi workspace phải xóa selection nhưng **không hủy cây dữ liệu**. Người dùng tự ẩn/hiện panel thông qua menu **Hiển thị**.
- Không hiển thị metric units, độ chính xác, sensor pose hay geometry khi chỉ có ID; tránh gán `measured` hoặc `validated` không có bằng chứng.
- Bảng `TaskSnapshot` chỉ là presenter cho 06.5, không truy cập `ProcessingRun` SQLite và không tạo tiến độ giả; không có nút “Hủy” chưa hoạt động.
- Bảng thông báo chỉ lưu sự kiện điều hướng đã diễn ra trong UI, **không** phải Audit Log GĐ0. Không tự ghi database.
- Không thay đổi stylesheet 06.3, không thêm QSS, VTK, Open3D, Orbbec SDK, worker hoặc dependency.

## 3. Kiểm thử và acceptance gate

**Kiểm thử tự động:**

1. 3 dock đúng vị trí; tiêu đề tiếng Việt; `Hiển thị` ẩn/hiện dock.
2. Empty/disabled states chính xác; không có dữ liệu mẫu mặc định.
3. Chấp nhận `ExplorerNode` và `SelectionRef` được cung cấp có chủ đích; từ chối dữ liệu sai kiểu.
4. Chọn đối tượng -> ViewModel + Inspector đồng bộ; thay cây, clear selection và đổi workspace không để selection cũ.
5. Bảng task nhận `TaskSnapshot`; hiển thị state/progress theo dữ liệu; unknown progress không được gán 0%.
6. UI event bị giới hạn 200 dòng, không ghi database; menu/bốn workspace không regression.
7. Phóng to/thu nhỏ ở 1366×768 và 1920×1080; đóng/mở panel; bàn phím/focus; font tiếng Việt hiển thị đúng trên máy Windows.
8. Full pytest (bao gồm 06.2/06.3), CTest 2/2, native self-test exit 0, `git diff --cached --check` sạch.

**Kỳ vọng số kiểm thử khi PySide6 hoạt động trên Windows:** 18 bài 06.4; toàn bộ Python **148 passed, 1 skipped** nếu không thay đổi lượng test GĐ0 và Windows vẫn skip symlink. Đây là **kỳ vọng**, không phải kết quả đã chạy trên Windows.

**Kiểm chứng có thể làm trên môi trường không có PySide6:** 31 unit tests 06.2 pass, 06.3/06.4 skip; static Python compile pass. Kiểm tra này **không thay thế** smoke GUI thật.

## 4. Việc cố ý để lại

- **06.5:** worker hữu hạn, progress/error/cancel thật, shutdown, UI task state transitions.
- **06.6:** nghiệm thu tổng hợp và sửa các lỗi tích hợp phát sinh.
- **07:** giao diện quản lý Project/Specimen/Session/Capture/ProcessingRun trên SQLite thông qua Application Service; cây từ 06.4 sẽ được cấp dữ liệu thật.
- **08:** trình xem PLY trong VTK.
- **QSS hoàn thiện:** thực hiện riêng khi người dùng yêu cầu **sau 06.5**, không pha trộn với patch 06.4.

Không merge `feat/gd1-desktop-ui` vào `main` ở bước 06.4.
