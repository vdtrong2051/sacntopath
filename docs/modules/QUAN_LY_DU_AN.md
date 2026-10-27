# Mô-đun quản lý dự án và dữ liệu nguồn

## Chức năng đã có

Project → Specimen → ScanSession → Capture và ProcessingRun, được lưu như metadata với quan hệ khóa ngoại trong SQLite. Các thành phần Project Workspace có Explorer, biểu mẫu, lịch sử trạng thái và bảng Thuộc tính. Sổ lưu trữ có đường dẫn đánh số và cơ chế chỉ đọc/ghi tường minh theo hợp đồng phiên hiện hành.

**Nguồn sự thật:** Metadata ở SQLite; RAW là các tệp riêng với manifest SHA-256. Một file PLY/OBJ ngoài chưa phải Capture và không tự đăng ký vào Project khi mở Viewer.

## Bất biến

1. Thao tác tạo/sửa phải qua command/service; việc mở chương trình không tự tạo hoặc migrate kho.
2. `ProcessingRun` ghi trạng thái `pending → running → succeeded|failed`, không chứng minh thuật toán đã chạy nếu chỉ nhập dữ liệu thủ công.
3. Đọc RAW có kiểm tra tính toàn vẹn khi được yêu cầu; thao tác tra cứu không tự đổi byte gốc.
4. Giao diện không truy cập trực tiếp SQLAlchemy hoặc lưu trữ vật lý trong Qt event handlers.

## Source và kiểm tra

- Presentation: `src/scantopath/modules/project_workspace/presentation/`.
- Metadata: `src/scantopath/metadata/`.
- Storage: `src/scantopath/storage/`.
- Kiểm thử: `tests/test_gd1_r3_1_recent_store.py`, `tests/test_gd1_r3_3_contextual_inspector.py`, `tests/test_raw_storage.py` và các test GĐ0/07.

Xem thêm [RAW](LUU_TRU_RAW.md) · [Kiến trúc](../architecture/TONG_QUAN_KIEN_TRUC.md) · [ADR-002](../decisions/ADR_002_NUMBERED_STORAGE_LAYOUT.md).
