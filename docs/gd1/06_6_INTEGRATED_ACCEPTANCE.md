# GĐ1 — 06.6: Tổng nghiệm thu Desktop UI Foundation

**Bản vá chỉ bổ sung kiểm thử và hồ sơ nghiệm thu.** Không thay đổi mã ứng dụng, QSS, SQLite, RAW, camera, VTK, CMake hoặc `pyproject.toml`.

- Nhánh làm việc: `feat/gd1-desktop-ui`.
- Commit nguồn đã kiểm tra: `7248b4fd53cc6c698ba7570049703c0dd42c462d` (đã gồm 06.5A).
- Trình tự đã triển khai: 06.1 thiết kế → 06.2 DTO/service → 06.3 cửa sổ → 06.4 panel → 06.5 worker → 06.5A QSS HMI.
- Trạng thái lúc soạn: **CHỜ NGHIỆM THU WINDOWS**. Tuyệt đối không tự ghi kết quả kiểm thử hoặc nghiệm thu màn hình vật lý là PASS.

## 1. Ranh giới sản phẩm được nghiệm thu

Chỉ nghiệm thu **Desktop UI Foundation**, chưa nghiệm thu GĐ1 hoàn chỉnh. Các phiên 07 (Project Workspace + SQLite) và 08 (VTK PLY Viewer) vẫn chưa triển khai. Phiên 06 chỉ có bốn workspace UI, điều hướng qua `NavigationViewModel`, ba dock, nguồn gốc/selection DTO, giao diện HMI tiếng Việt, TaskManager queue/cooperative cancel/GUI-thread bridge.

`TaskSnapshot` thử nghiệm ≠ `ProcessingRun` SQLite. `measured` ≠ metric validated. Không tồn tại camera pose ước lượng, RGB-D replay, VTK cloud hay độ chính xác hình học trong đợt nghiệm thu này.

## 2. Ma trận nghiệm thu và bằng chứng

| Gate | Yêu cầu | Bằng chứng phải lấy | Trạng thái hiện tại |
|---|---|---|---|
| A01 | Import và khởi động PySide6 UI tiếng Việt, 4 workspace, menu/phím tắt | Qt offscreen + Windows launch/close | Chờ Windows |
| A02 | ProjectExplorer/Inspector đồng bộ lựa chọn, đổi workspace xóa selection | `test_gd1_06_6_qt_integration.py` + 06.4 tests | Chờ Windows |
| A03 | 3 dock ẩn/hiện lại từ menu Hiển thị | Qt test + thao tác trực tiếp | Chờ Windows |
| A04 | HMI QSS tối giản, sidebar compact, cuộn dọc 4 workspace | QSS tests + kiểm tra màn hình thực | Chờ Windows |
| A05 | Tác vụ demo chạy nền, tiến độ thật, GUI không đơ | 06.5/06.6 Qt tests + tương tác trực tiếp | Chờ Windows |
| A06 | Hủy queued/running; yêu cầu hủy khác với confirmed cancel | 06.5 core + Qt tests | Chờ Windows |
| A07 | Đóng khi worker đang chạy: không block, không kill thread | 06.5/06.6 Qt tests + thực tế | Chờ Windows |
| A08 | App startup không tự tạo SQLite, gọi camera hoặc tải VTK | import isolation, 06.6 static/dynamic Qt tests | Chờ Windows |
| A09 | Python regression 06.1–06.6 và GĐ0 | `pytest -q -rs tests` log Windows | Chờ Windows |
| A10 | C++ regression | CTest `2/2` | Chờ Windows |
| A11 | Native binding không mở hardware | `native --self-test`, exit code 0 | Chờ Windows |
| A12 | `git diff --check`, đúng 3 tệp docs/tests mới, commit sạch | git output | Chờ Windows |

### Điểm kiểm tra đặc biệt: laptop 14 inch

Không dùng kích thước đường chéo màn hình làm tiêu chí pixel. Người dùng ghi **độ phân giải màn hình**, **Scale Windows**, **kích thước cửa sổ** đang sử dụng (logical pixels của Qt có thể khác physical pixels). Phải kiểm tra:

1. Cửa sổ không khuất sau taskbar; title bar/menu/status bar còn truy cập được.
2. Ở mỗi workspace, chữ, card, nhãn `CHƯA TRIỂN KHAI` và nội dung mô tả không đè nhau; nội dung dài được cuộn dọc.
3. Khi giảm chiều ngang, Inspector có thể ẩn và mở lại từ `Hiển thị`; không có panel nào mất vĩnh viễn.
4. Task Panel và cả hai nút `Chạy tác vụ KIỂM THỬ` / `Yêu cầu hủy tác vụ` dùng được, có thể resize dock để xem.
5. Điều hướng bốn workspace không làm mất cửa sổ, treo GUI, giả dữ liệu đo hoặc mở thiết bị.

Test `QT_QPA_PLATFORM=offscreen` không chứng minh tự động các điều kiện hiển thị trên màn hình 14 inch thật. **Phải có xác nhận trực tiếp của operator.**

## 3. Thao tác nghiệm thu trên Windows

Trong nhánh `feat/gd1-desktop-ui`, trạng thái clean tại `7248b4f`: áp dụng `apply.ps1`, chạy `verify.ps1`, kiểm tra Qt UI thật, sau đó mới chạy `publish.ps1`. Không chạy lại bản vá 06.5A.

```powershell
# Chạy thật (không ở chế độ offscreen):
Remove-Item Env:\QT_QPA_PLATFORM -ErrorAction SilentlyContinue
& .\.venv\Scripts\python.exe -m scantopath.ui.main

# Kiểm tra đổi workspace bằng Ctrl+1..Ctrl+4, các dock, thao tác task,
# cuộn trang, đóng khi task đang chạy, scaling của laptop 14 inch.
```

Tại thời điểm nghiệm thu, ghi dưới đây bằng log Windows và nhận xét thực tế, **không tự đánh dấu từ dữ liệu dự kiến**:

| Bằng chứng | Kết quả nhập bởi operator |
|---|---|
| HEAD trước patch | `7248b4f` (cần xác nhận lại) |
| Qt acceptance 06.6 | Chưa có log Windows |
| Full Python regression | Chưa có log Windows |
| CTest | Chưa có log Windows |
| Native self-test | Chưa có log Windows |
| Windows resolution / scale | Chưa cung cấp |
| Các dock + scroll không che nội dung | Chưa xác nhận trên thiết bị |
| Background job, cancel, shutdown | Chưa xác nhận qua thao tác thật |
| SHA commit 06.6 sau publish | Chưa có |

## 4. Điều kiện đóng phiên 06

Chỉ đánh dấu phiên 06 là **ACCEPTED** sau khi tất cả A01–A12 đạt; ngoại lệ duy nhất có thể ghi nhận là bài symlink Windows bị skip do quyền hạn, phải ghi rõ `SKIPPED`, không tính là `PASSED`. Nếu Qt test skip vì thiếu PySide6, **không đạt**. CTest phải đạt 2/2; native self-test exit 0; Windows UI smoke phải chạy.

Commit/push 06.6 chỉ có nghĩa là **lưu bộ kiểm thử và hồ sơ** trên nhánh GĐ1, không đồng nghĩa tất cả gate đã đạt. Chưa merge `main`; sau khi phiên 06 được nghiệm thu, mới xin xác nhận bắt đầu **phiên 07**.

## 5. Ghi chú từ kiểm tra độc lập

Code source các patch GĐ0–06.5A được dựng lại offline và chạy toàn bộ `pytest` không có PySide6: 129 passed và 4 nhóm Qt skipped (môi trường thử nghiệm, **không** phải Windows/branch nghiệm thu). Bài Qt 06.6 có thể skip khi PySide6 không được cài trong môi trường developer tùy chọn, nhưng script `verify.ps1` trên Windows **bắt buộc kiểm tra PySide6 trước**, vì đây là gate nghiệm thu không được skip.
