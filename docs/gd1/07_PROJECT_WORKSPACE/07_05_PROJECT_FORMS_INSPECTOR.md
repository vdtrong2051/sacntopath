# GĐ1 — 07.5: Biểu mẫu Project, Specimen và Scan Session

**Baseline Git:** `feat/gd1-desktop-ui` tại `63dd0c504ed4d4a8c9445a398201bed43a9671b2` (07.4 đã nghiệm thu). **Không merge main.**

## Phạm vi và UI

- Trong Cây dự án, `＋ Thêm…` chứa **Tạo dự án** (khi chọn kho v2), **Thêm vật mẫu** (khi chọn Project), **Tạo phiên quét** (khi chọn Specimen). Menu thay đổi enable theo lựa chọn.
- Trong Inspector, **Sửa…** cho Project/Specimen/ScanSession; **Đóng phiên** chỉ khi chọn phiên đang mở. Đóng phiên yêu cầu hộp thoại xác nhận, không có chức năng mở lại.
- Hộp thoại tiếng Việt gọn với tên và mô tả (Session chỉ có tên). Tên phải không rỗng, tối đa 256 ký tự; mô tả tối đa 4096 ký tự và không chứa NUL. Không đổi ID, parent hoặc mã thư mục khi sửa tên.
- GUI 14 inch: giữ QSS HMI cũ, hai hàng nút gọn trong dock; hộp thoại có bố cục co giãn. Không buộc sidebar/card cố định vượt viewport.
- Tạo/sửa/đóng được thực thi bằng `ProjectWriteController`/`QThread`; chỉ DTO và tín hiệu được chuyển về GUI thread. Sau khi worker hoàn thành, Explorer tải lại SQLite và cố gắng chọn đúng đối tượng qua ID bất biến.
- Mở ứng dụng **không import MetadataStore hoặc tạo SQLite**; backend chỉ được import trong worker theo thao tác chủ động.

## Backend và an toàn dữ liệu

1. Lệnh metadata dùng `ProjectWorkspaceService` 07.3, không gọi trực tiếp SQLAlchemy hay `sqlite3` từ QWidget.
2. Chỉ cho phép ghi nếu người dùng đã mở một SQLite schema v2; kho v1 vẫn xem được nhưng nút chỉnh sửa bị vô hiệu. Không auto-migrate v1->v2.
3. GĐ0 `MetadataStore.update_scan_session(session_id,label)` được thêm chỉ để sửa nhãn; transaction tạo audit `session.updated`, **không** sửa `session_id`, parent, state hoặc RAW.
4. `ProjectWorkspaceService.update_session(specimen_id,session_id,label=...)` kiểm tra sở hữu parent qua cây SQLite và từ chối khác Specimen.
5. Tạo Project/Specimen/Session dùng flow 07.3: tạo metadata trước, cấp mã theo 07.2 sau; nếu cấp mã thất bại **metadata có thể đã commit**. UI báo ID và yêu cầu dùng công cụ 07.2 để cấp lại, tuyệt đối không kích hoạt tạo trùng. Cần migration/repair nâng cao ở 07.7.
6. Một lần chỉ có một thao tác đọc/ghi kho ở GUI. Nút mở/tải lại/tạo/sửa bị vô hiệu khi đang ghi; đóng ứng dụng đợi `QThread` kết thúc mà không terminate/kill. Người dùng vẫn nên tránh sửa cùng kho từ ứng dụng khác trong khi làm việc; 07.5 chưa triển khai locking liên tiến trình hoặc compare-and-swap optimistic concurrency.
7. Tất cả test chạy với SQLite trong `tmp_path`; không đụng `scantopath-data` thật. Không tạo RAW, không đọc SDK, không làm phép đo, không tạo ProcessingRun giả, không đổi QSS toàn cục.

## Test

- `tests/test_gd1_07_5_forms_contracts.py`: validation, command bất biến, session rename với khóa/cha giữ nguyên, audit, v1 read-only, tạo–sửa–đóng–mở lại v2.
- `tests/test_gd1_07_5_qt.py`: offscreen GUI, khả năng thao tác theo loại entity, đối thoại nhập liệu, tạo/sửa/đóng thực qua QThread, tự reload và restore lựa chọn, chống ghi trùng, đóng an toàn.
- `verify.ps1`: kiểm tra PySide6, chạy hai nhóm 07.5, toàn bộ regression Python, `ctest 2/2`, native self-test. `git diff --check`. Hai symlink test có thể skip vì Windows privilege, nhưng các bài Qt phải chạy.
- Phải kiểm tra UI thật trên màn 14 inch: **Mở kho…**, **Tải lại**, **＋ Thêm…**, **Sửa…**, **Đóng phiên**; khi thu hẹp panel không mất nút hoặc cắt nội dung; thực thi dựa trên **database tạm/bản sao có schema v2**, không dùng kho dữ liệu sản xuất trước khi đủ backup và chủ động chọn sửa.

## Chưa thuộc 07.5

- Xóa dự án/vật mẫu/phiên hoặc chuyển parent, sửa Capture, tạo ProcessingRun bằng thuật toán (07.6).
- Migrate/di chuyển RAW cũ (07.7), tự migrate database hoặc batch cấp mã.
- Giải quyết đồng thời ghi bằng hai ứng dụng ngoài một phiên UI; khóa/migration và failure recovery nâng cao cần đánh giá sau.
- VTK Viewer/measurement/geometry pipeline (phiên 08+).

**Gate:** 07.5 chỉ được khóa khi `verify.ps1` trên Windows đạt, UI smoke thực tế đạt, Git chỉ thay đúng 11 tệp; không merge main.
