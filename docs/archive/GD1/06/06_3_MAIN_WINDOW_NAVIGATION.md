# GĐ1 — Bước 06.3: MainWindow và điều hướng UI tiếng Việt

**Nhánh dùng chung:** `feat/gd1-desktop-ui` (KHÔNG tạo nhánh mới theo bước).
**Commit đầu vào đã kiểm tra:** `c736d007202e4ae0e14d7671cb3d8159305c9b90` (06.2).
**Trạng thái:** đã xây dựng bản vá mã nguồn; **chưa nghiệm thu Qt/Windows** khi soạn tài liệu này.
**Nguồn thiết kế:** [06.1 Audit](06_1_UI_AUDIT_AND_DESIGN.md) · [06 Delivery Gates](06_DELIVERY_GATES.md) · [Roadmap](../../../ROADMAP.md).

## 1. Phạm vi giao hàng

Đã thay shell `QTabWidget` 7 nhãn tĩnh bằng một `QMainWindow` duy nhất:

- Thanh điều hướng bên trái và `QStackedWidget` đúng **4** workspace: **Dự án**, **Thu nhận và phát lại**, **Kiểm tra 3D**, **Xử lý và kết quả**.
- Menu **Tệp → Thoát**, **Không gian làm việc → 4 lựa chọn**, **Trợ giúp → trạng thái**; phím tắt `Ctrl+1`, `Ctrl+2`, `Ctrl+3`, `Ctrl+4`, `Ctrl+Q`.
- Status bar hiển thị workspace hiện tại và `Dữ liệu: Chưa tải`.
- Dùng đúng `NavigationViewModel.select_workspace()` của 06.2. Nếu lệnh điều hướng thất bại thì không tự chuyển trang hoặc ghi thành công giả.
- Tất cả văn bản hướng tới người dùng bằng **tiếng Việt**, trừ tên sản phẩm, tên công nghệ/ID và ký hiệu kỹ thuật.
- Mỗi trang gắn trạng thái **CHƯA TRIỂN KHAI**, cho biết phiên dự kiến và nguồn dữ liệu chưa tải. Trang 06.3 không đo, không quét và không tạo ProcessingRun.
- Bố cục có thể resize, không thêm asset/font ngoài, không phụ thuộc GPU.

### Cây mã nguồn thay đổi

```text
src/scantopath/ui/main.py                      [MODIFY] entrypoint cũ được giữ nguyên
src/scantopath/ui/shell/__init__.py             [NEW]
src/scantopath/ui/shell/main_window.py          [NEW] QMainWindow + navigation
src/scantopath/ui/workspaces/__init__.py        [NEW]
src/scantopath/ui/workspaces/pages.py           [NEW] bốn placeholder minh bạch
tests/test_gd1_06_3_ui.py                       [NEW] Qt smoke/regression
docs/gd1/06_3_MAIN_WINDOW_NAVIGATION.md        [NEW] tài liệu nghiệm thu
```

**KHÔNG sửa** GĐ0 (`metadata/`, `storage/`, `acquisition/`, `domain/`, `cpp/`), `application/contracts` 06.2 hoặc `pyproject.toml`. Không tự thêm VTK, Open3D, PCL, AI hay camera SDK vào giao diện.

## 2. Ranh giới trách nhiệm

```text
QMainWindow / nav QPushButton / QAction
      ↓ NavigationViewModel.select_workspace(workspace)
      ↓ CommandService.execute(workspace.select)
      ↓ NavigationService.select(workspace)
      ↓ CommandOutcome(success/fail)
QStackedWidget + nav/action checked + QStatusBar
```

Không gọi ORM hoặc thao tác filesystem từ `QWidget`. `UiDataState.NOT_IMPLEMENTED` mô tả trạng thái trang; không gán `measured`, `validated`, pose hay kích thước 3D khi chưa có bằng chứng.

## 3. Những gì *không* triển khai ở 06.3

- Explorer, Inspector, TaskAndEventPanel: **06.4**.
- Worker scheduler và progress/cancel thực: **06.5**.
- Project/Specimen/Session/Capture CRUD bằng UI kết nối SQLite: **phiên 07**.
- Trình xem VTK/nhập PLY: **phiên 08**.
- Color/depth RAW replay: **phiên 09**.
- RGB-D → point cloud: **phiên 10**.

Không nhầm placeholder với tích hợp backend thật; `main.py` không mở Gemini 2 hoặc SQLite khi import/chạy.

## 4. Kiểm thử và nghiệm thu trên Windows

Với Python 3.12 `.venv` đã cài PySide6 (nếu thiếu, cài `python -m pip install -e '.[ui,test]'` trước khi chạy):

```powershell
$pyExe = (Resolve-Path '.\.venv\Scripts\python.exe').Path
$env:QT_QPA_PLATFORM = 'offscreen'
& $pyExe -m pytest -q -rs .\tests\test_gd1_06_3_ui.py
& $pyExe -m pytest -q -rs .\tests
Remove-Item Env:\QT_QPA_PLATFORM -ErrorAction SilentlyContinue
ctest --test-dir .\build-orbbec -C Release --output-on-failure
$env:SCANTOPATH_ORBBEC_SDK_BIN = 'E:\1_BigProject\scantopath\_sdk\OrbbecSDK_v2.10.6\bin'
& $pyExe -u -X faulthandler -m scantopath.acquisition.native --self-test
& $pyExe -m scantopath.ui.main
```

Bản vá kèm `verify.ps1` kiểm soát exit code và restore biến môi trường QT sau khi chạy. **Trên container Linux tạo bản vá không có PySide6**, do đó không có bằng chứng Qt offscreen pass ở đó; GUI phải được nghiệm thu trên Windows của người dùng.

### Gate 06.3

1. Qt offscreen test **không có fail hoặc skip** (nếu PySide6 thiếu thì bước không đạt).
2. App Windows mở/đóng được, 4 trang + chữ tiếng Việt chính xác, menu/shortcut hoạt động.
3. Thử thay đổi kích thước 1366×768 và 1920×1080; điều hướng và trạng thái còn dùng được.
4. Mở UI không khởi động SDK, không tạo `scantopath-data/metadata.sqlite3` ngoài ý muốn.
5. Toàn bộ Python GĐ0/06.2 không fail; có thể một bài Windows symlink skip; CTest 2/2 và native self-test exit 0.
6. `git diff --cached --check` đạt, commit và push đúng **nhánh GĐ1 hiện tại**, **không merge**.

Sau khi đạt: chuyển sang 06.4, bổ sung dock Explorer/Inspector/Task Panel dựa trên shell này; không viết lại navigation layer.
