# Project Workspace — dữ liệu và quyền sở hữu

**Mốc kiểm kê:** `ff45ccf`. Đây là module Project + SQLite/RAW metadata thật, **không** phải pipeline xử lý point cloud.

- `modules/project_workspace/presentation/controller.py` điều phối use-case theo feature. Shell tạo controller nhưng không gọi trực tiếp SQL/IO ở Qt main thread.
- Các application services dùng metadata, Registry và RAW storage hiện hành. Data Store v2 có mã phân cấp Project (P), Specimen (S), Session (T), Capture (C), ProcessingRun (R); **SQLite là nguồn sự thật**, đường dẫn có thể chưa materialized.
- Bảng Thuộc tính chung nhận dữ liệu Project khi chọn node metadata, nhận DTO hình học khi mở Viewer. File PLY nhập ngoài **không tự trở thành Capture hay Project**.
- Đọc kho gần đây ≠ tự mở/khởi tạo kho; mọi thao tác create/edit/close/verify có chủ sở hữu command rõ ràng.
- `ProcessingRun` là **bản ghi trạng thái**, không đồng nghĩa thuật toán xử lý đã chạy nếu không có bằng chứng thực thi.
- GĐ0 RAW màu MJPEG và depth Y16 độc lập, SHA-256/manifest bất biến, không tự align hai lưới, không suy diễn world pose.

## Kiểm thử và ranh giới cần giữ

`tests/test_gd1_r3_1_recent_store.py`, `tests/test_gd1_r3_3_contextual_inspector.py`, `tests/test_gd1_r3_4_processing_workspace.py`, `tests/test_gd1_07_12_architecture.py`, `tests/test_raw_storage.py` cùng bộ RAW/metadata GĐ0.

**Cấm trong công việc chỉ về tài liệu R7:** tự migrate SQLite, ghi RAW, đổi schema, xóa compatibility facade khi chưa kiểm caller, tự mở Gemini 2.

**Nguồn:** [ADR-002](../decisions/ADR_002_NUMBERED_STORAGE_LAYOUT.md) · [07.11](../architecture/07_11_ARCHITECTURE_HARDENING.md) · [GĐ0 acceptance](../PRE_06_GD0_ACCEPTANCE.md).
