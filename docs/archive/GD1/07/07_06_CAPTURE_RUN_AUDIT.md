# GĐ1 — 07.6: Capture / ProcessingRun / Audit Timeline (read-only)

**Baseline:** `feat/gd1-desktop-ui`, commit `f7cddc6802eb5b156d9d0715bd43d2ff94cbc32f` (07.5). Không thay SQLite schema, không migration 07.7, không ghi RAW, không tạo thuật toán 3D hoặc dữ liệu đo giả.

## Đã bổ sung

1. `project_rows`: hiển thị `ProcessingRun` đã có trong SQLite dưới `ScanSession`, sau các Capture. Có mã `R0001` nếu đã được gán, nếu chưa có hiển thị **Chưa cấp mã**. Inspector hiển thị `stage`, thuật toán, version, trạng thái, input_capture_ids, `output_files`, thông số và lỗi **lấy từ metadata thật**. `output_files` là **tham chiếu**, không phải file đã được xác minh.
2. `ProjectLoadController`: ngoài cây, tải **100 sự kiện gần nhất** qua `ProjectWorkspaceService.list_events()` trong QThread. Truy vấn SQLite chỉ khi người dùng mở kho/tải lại; không polling và không ghi audit giả.
3. `TaskAndEventPanel`: tab **Nhật ký SQLite** riêng biệt với **Thông báo UI** và **Tác vụ KIỂM THỬ**. Mỗi hàng: timestamp UTC, level, action, entity type/ID; details JSON ở tooltip (giới hạn). Thay kho sẽ xóa nhật ký cũ, không trộn nhiều kho.
4. `ProjectWorkspaceService.inspect_capture(capture_id)`: chỉ gọi khi người dùng nhấn **Kiểm tra RAW** cho Capture đã đăng ký. Trả immutable `CaptureInspection` với `verified | missing | corrupt | inaccessible`. V1 là kiểm tra cấu trúc, NPY, COMMITTED **không có SHA-256**. V2 kiểm tra metadata, manifest, SHA-256, identity và COMMITTED theo reader GĐ0/07.2. Không tự sửa metadata/path, không lưu trạng thái `verified` vào SQLite, không coi checksum là đánh giá độ chính xác hình học.
5. `CaptureInspectionController`: QThread chạy kiểm tra I/O/RAW ngoài GUI; chặn đổi kho/tải lại/ghi metadata trong khi kiểm tra; đóng cửa sổ chờ worker kết thúc qua signal, không `terminate`, không chặn event loop.
6. Inspector: chỉ bật nút **Kiểm tra RAW** cho Capture; trạng thái xác minh chỉ hiển thị tạm trong session UI. Khi chọn đối tượng khác và chọn lại, dùng trạng thái DTO `Chưa kiểm tra RAW` cho đến khi người dùng xác minh lại. Không tự cập nhật SQLite.

## Trạng thái, ý nghĩa và giới hạn

| Khái niệm | Ý nghĩa thực |
|---|---|
| Đã đăng ký | Bản ghi `captures` thực sự tồn tại trong SQLite, chưa kết luận dữ liệu trên đĩa. |
| RAW chưa kiểm tra | Capture tồn tại trong SQLite; chưa có kết quả kiểm tra byte mới trong phiên UI. |
| Verified v1 | Có cấu trúc RAW v1 hợp lệ; **không có SHA-256**. |
| Verified v2 | Có metadata/manifest/ID đúng và các checksum SHA-256 đúng. |
| Missing | Thư mục hoặc file RAW thiếu, bản ghi SQLite giữ nguyên. |
| Corrupt | RAW không đạt điều kiện cấu trúc/metadata/hash/path. Không tự phục hồi. |
| Inaccessible | Lỗi quyền hoặc I/O; không kết luận RAW còn nguyên hay đã hỏng. |
| ProcessingRun `succeeded` | **Trạng thái metadata do backend lưu**, không đồng nghĩa thuật toán đã đạt chất lượng hình học. |
| `output_files` | Danh sách tham chiếu, không tự mở, không suy diễn artifact tồn tại. |
| SQLite audit | Sự kiện do metadata backend thực sự ghi, **khác log UI**. |

Để kiểm thử 07.6 trên Windows mà **không ảnh hưởng kho 07.5**, chạy fixture builder `scripts/create_demo_store.py` từ gói vá (chỉ tạo thư mục mới, từ chối nếu đã tồn tại). Nó tạo RAW synthetic v1/v2, không gọi camera. ProcessingRun metadata ở trạng thái `pending`, không tạo output thuật toán. Sau đó mở kho này từ UI: cây Project → Specimen → Session → Capture C0001/C0002 → R0001; chọn Capture và nhấn **Kiểm tra RAW**; tab **Nhật ký SQLite** có các event đã lưu. Có thể thử lỗi bằng cách tạo bản sao của toàn bộ thư mục fixture và cố ý thay file trong **bản sao thử nghiệm**, không sửa RAW thực.

## Cổng nghiệm thu

- 07.6 tests: headless + Qt offscreen; mỗi ca dùng temp root, không mở Gemini 2.
- Full pytest trên Windows phải đạt; symlink skip vì thiếu quyền cần ghi rõ. PySide6 **không được skip**.
- CTest 2/2 và `native --self-test` (`hardware_access=false`).
- GUI trên laptop: hiển thị Capture/Run và Audit SQLite, lựa chọn/Inspector đồng bộ, nút verify không bị che, đang kiểm tra không làm đơ GUI; đóng cửa sổ khi worker chạy không crash.
- Không thay GĐ0 Storage, registry 07.2, QSS, schema, C++, SDK. Không merge `main` trước 07.8.

**Tiếp theo 07.7:** migration legacy RAW → numbered layout là một công việc **tùy chọn, riêng biệt**, có dry-run, sao lưu và rollback.
