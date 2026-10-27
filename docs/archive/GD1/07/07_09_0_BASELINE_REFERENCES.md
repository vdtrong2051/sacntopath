# GĐ1 — 07.9-0: Nhật ký và tài liệu tham chiếu

## Baseline đã khóa

- Repository: `vdtrong2051/sacntopath`; branch `feat/gd1-desktop-ui`.
- Accepted HEAD: **`19e950c9a3bcd5ed08decb59f8d1fd1b203536ba`**, `test(gd1-07.8): certify project workspace integrated acceptance`.
- Nghiệm thu Windows 07.8 do người dùng cung cấp: 14/14 integrated tests; 341 passed, 2 skipped (Windows symlink privilege); CTest 2/2; native self-test `hardware_access=false`.
- 07.8 bao gồm project forms, numbered storage, SQLite project explorer, Capture/ProcessingRun/Audit, kiểm tra RAW và 07.7 migration opt-in.
- Hình tham chiếu do người dùng cung cấp ở cuộc trò chuyện 24/10/2026: cửa sổ ứng dụng (dark HMI có thanh điều hướng lớn, tab vuông, chữ xám nhạt); terminal VS Code (QFont::setPointSize: Point size <= 0 (-1)). Ảnh là căn cứ thị giác, **không phải phép đo DPI hay proof rendering**.

## Các vấn đề có bằng chứng

| ID | Phát hiện | Nguồn baseline | Tiêu chí kết thúc |
|---|---|---|---|
| UI-01 | Màu nền/panel/tab gần nhau; trạng thái disabled và text thiếu phân cấp | QSS `ui/theme/hmi_panel.qss` + ảnh | Contrast text chính ≥ 4.5:1, focus/selection rõ |
| UI-02 | Border radius chưa nhất quán, tab/dock/control vuông | QSS và ảnh | radius 6–11px cho button/tab/card/panel nơi Qt hỗ trợ |
| UI-03 | Sidebar nav chiếm 172–194 logical px theo 06.5A | `ui/shell/main_window.py:_initialize_dock_layout` | compact mặc định 76px, expanded 178px theo yêu cầu |
| UI-04 | Dashboard project/processing vẫn ghi chưa triển khai sau nghiệm thu 07.8 | `ui/workspaces/pages.py` | phân biệt tính năng qua dock với viewer/capture còn dự kiến |
| UI-05 | Cảnh báo `QFont::setPointSize(-1)` trong terminal Windows | Ảnh người dùng | font baseline point-size >0 và QT cảnh báo cần được kiểm tra lại trên máy thật |
| ARCH-01 | Window/controller và service có nhiều phương thức | `main_window.py`, `application/projects/service.py` | audit với bằng chứng, kế hoạch refactor nhỏ sau baseline |
| ARCH-02 | Project feature bị chia theo technical layer | `ui/projects`, `application/projects`, `metadata`, `storage` | chốt mapping modular MVC, KHÔNG mass move trong patch HMI |

## Quy ước trách nhiệm

- **Phiên 07.9-0:** nhật ký, inventory, nguồn tham chiếu, điều kiện rollback.
- **Phiên 07.9:** chỉ thay QSS + giao diện/UX có liên quan; không sửa pipeline, camera, storage hay schema.
- **Phiên 07.10:** audit tĩnh bằng AST và nhận định kiến trúc; không áp refactor lớn ngay trong patch này.

## Quy tắc giữ nguyên

- 07.1–07.8 là baseline chức năng; thay đổi UI không được sửa metadata, SessionStore, NumberedStorageRegistry, RAW bytes, camera driver, C++ hoặc VTK.
- Mở app không tự mở SQLite/camera; mở kho mới thông qua lựa chọn của người dùng.
- Mã P/S/T/C/R và ID nội bộ không đổi, read-only v1, v2 write, migration 07.7 opt-in.
- Không tự merge `main`; không tự tạo project/capture giả khi mở giao diện.
- Kỳ vọng test UI cũ về width/nhãn placeholder được cập nhật CÓ LÝ DO; các test nghiệp vụ 07.1–07.8 không chỉnh sửa.

## Mốc xác minh

Nhật ký nguồn được đối chiếu với Git blob 19e950c: `main_window.py`, `pages.py`, `ui/main.py`, `hmi_panel.qss` và các test 06.3/06.5A/06.6. Bản vá áp dụng yêu cầu đúng blob và working tree sạch, tránh sai SHA do LF/CRLF.
