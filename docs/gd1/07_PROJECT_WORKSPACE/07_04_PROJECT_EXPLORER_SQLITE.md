# GĐ1 — 07.4: Project Explorer kết nối SQLite thật

**Baseline:** nhánh `feat/gd1-desktop-ui`, commit `1c492a7635f86a94d0dd6dd0d7fb2f433ded6c38` (07.3 đã nghiệm thu Windows). 07.4 chỉ mở kho theo hành động người dùng và **chỉ đọc metadata**. Không triển khai biểu mẫu CRUD (07.5), timeline ProcessingRun (07.6), migration RAW (07.7) hoặc VTK (08).

## 1. Các thay đổi

- `ui/projects/presentation.py`: `ProjectLoadBundle`, `ProjectRow`, `project_rows` là lớp chuyển **DTO của application 07.3** sang bản ghi hiển thị không phụ thuộc Qt. Không giả dữ liệu 3D/pose/accuracy, không cấp mã. Với mã chưa có, dùng `Chưa cấp mã` thay vì hiển thị UUID như một mã công khai.
- `ui/projects/controller.py`: `ProjectLoadController` chạy công việc đọc SQLite bằng QThread riêng. Mỗi lần tải khởi tạo `ProjectWorkspaceService` bên trong worker, lấy `list_projects()` rồi `get_project_tree(...)` cho từng dự án, chuyển `ProjectLoadBundle` qua signal. GUI và QTreeWidget **chỉ cập nhật trong GUI thread**. Không chạy `assign_all`, `migrate_database`, `get_capture(... verify_raw=True)` hoặc `SessionStore.commit_raw`.
- `ui/components/project_explorer.py`: nút **Mở kho…** mở hộp thoại chọn thư mục, **Tải lại** có hiệu lực sau khi kho mở thành công; nhãn tên kho/schema v1 hoặc v2, thông báo đang tải/rỗng/lỗi, cây đối tượng theo số cấp đã có.
- `ui/components/property_inspector.py`: giữ API `set_selection` và hành vi fixture 06.4; khi chọn đối tượng được tải thật, nối thêm trường mã, tên, trạng thái / địa chỉ lưu trữ **từ DTO**. Ghi chú cảnh báo tính toàn vẹn RAW khác với xác nhận đo lường 3D.
- `ui/shell/main_window.py`: điều phối chọn kho, làm mới, đồng bộ lựa chọn và trạng thái; khi đổi kho sẽ xóa dữ liệu cũ ngay để tránh chọn nhầm đối tượng từ kho trước; bảo đảm worker đọc SQLite đã kết thúc trước khi thực sự đóng cửa sổ. Vẫn tương thích `QtTaskController` 06.5. Giữ nguyên QSS HMI 06.5A.

## 2. Trình tự vận hành

1. Khởi động `python -m scantopath.ui.main`: **chưa kết nối kho**, không tạo `metadata.sqlite3` hoặc mở Gemini 2.
2. Trong dock **Cây dự án**, chọn **Mở kho…** rồi chọn thư mục *cha* chứa `metadata.sqlite3` (ví dụ `scantopath-data`, không chọn trực tiếp tệp `.sqlite3`).
3. `ProjectWorkspaceService(root)` từ 07.3 chỉ chấp nhận database đã có ở `PRAGMA user_version=1` hoặc `2`. Nếu thư mục không đúng: thông báo tiếng Việt; không tạo kho hay nâng schema.
4. Dữ liệu được lấy bằng worker và chuyển qua QObject signal; các thao tác nút tải bị vô hiệu trong lúc truy vấn. Nếu kho rỗng: hiển thị thông báo, không tạo fixture.
5. Khi có dữ liệu, Project → Specimen → ScanSession → Capture trong cây, có `P/S/T/C` nếu đã cấp mã theo 07.2. Khi chưa cấp, hiện **Chưa cấp mã**. Tên hiển thị lấy từ SQLite, không lấy từ tên thư mục. `SelectionRef` luôn mang ID nội bộ bất biến.
6. Chọn mục sẽ cập nhật `NavigationViewModel`/Inspector, không tự gọi RAW verification hay thực hiện lệnh lưu. **Tải lại** mới truy vấn các thay đổi từ chương trình khác, không polling filesystem liên tục.
7. Thao tác đóng cửa sổ khi còn truy vấn: `closeEvent` từ chối đóng cho đến khi QThread thực sự hoàn thành rồi thử đóng lại. Không gọi `terminate()`/`wait()` khiến đóng băng GUI; khi quá trình đọc SQLite dài, người dùng đợi completion.

## 3. Giới hạn rõ ràng

- **Không tự cấp số trên kho v2 đã có dữ liệu cũ:** gọi `assign_all` thủ công bằng công cụ 07.2 nếu muốn nhìn thấy `P0001...`; nhấn **Mở kho…** chỉ đọc.
- **RAW integrity:** số `C0001` không có nghĩa SHA-256 đã được kiểm tra; khi chưa verify, trạng thái hiện `Chưa kiểm tra RAW`. RAW và manifest không bị mở khi dựng cây.
- **ProcessingRun:** API 07.3 vẫn có record nhưng 07.4 chỉ trình bày cây Project/Specimen/Session/Capture; timeline/lần xử lý thuộc 07.6.
- **Không chụp camera, không tạo ảnh mẫu, không đọc VTK, không đổi database schema, không dịch chuyển data.**
- **Không thực hiện kiểm thử màn hình vật lý trong môi trường Python không có PySide6:** bài Qt 07.4 phải đạt trên Windows. Với hàng nghìn record, 07.4 tải tất cả theo lát cắt nhỏ; đánh giá phân trang/cached tree sẽ dành cho tối ưu sau nghiệm thu dữ liệu thực.

## 4. Test và nghiệm thu Windows

- Headless 07.4: SQLite v1 đọc mà không cấp mã, SQLite v2 đã/ chưa cấp mã, dữ liệu Capture legacy không đổi bytes, empty/error, validator đầu vào.
- Qt 07.4: khởi động trống, hộp thoại chọn kho/cancel, v1/v2, chọn Explorer→Inspector, kho rỗng, lỗi schema, không tạo DB khi folder sai, reload, đổi kho, signal main thread, đóng cửa sổ trong khi worker còn chạy.
- Hồi quy GĐ0–07.3, CTest 2/2, native self-test `hardware_access=false`. Chỉ commit khi toàn bộ test có thể chạy ở Windows đạt; ngoại lệ skip quyền symlink phải ghi lý do. Kiểm tra bằng GUI thật trên laptop 14 inch: nút Mở kho/Tải lại luôn nhìn thấy, tree cuộn được, nhãn/Inspector không đè layout, đóng khi đang tải không crash.
- Patch 07.4 chỉ có **3 tệp sửa + 6 tệp mới**, không thay đổi `MetadataStore`, `SessionStore`, `NumberedStorageRegistry`, RAW, QSS, pyproject hoặc camera.

**Tiếp theo 07.5:** biểu mẫu thêm/sửa Project/Specimen/Session qua Application Services 07.3, chỉ cho phép ghi khi schema v2, có validation và trạng thái lỗi/race rõ ràng.
