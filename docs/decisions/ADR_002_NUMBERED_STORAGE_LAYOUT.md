# ADR-002 — Mã thư mục đánh số cho ScanToPath Data Store

- **Ngày:** 2026-10-19.
- **Trạng thái:** Accepted as **target design**, implementation pending 07.2/07.7.
- **Phạm vi:** GĐ1 / phiên 07; giữ nguyên PRE-02/03 RAW v1/v2; không ghi đè/rename dữ liệu tồn tại.
- **Liên kết:** [Audit 07.1](../gd1/07_PROJECT_WORKSPACE/07_01_STORAGE_AUDIT.md), [Layout contract](../gd1/07_PROJECT_WORKSPACE/07_01_STORAGE_LAYOUT_V2_CONTRACT.md), [UI-first ADR-001](ADR_001_UI_FIRST.md).

## Bối cảnh

GĐ0 dùng `sessions/<session_id>/captures/<capture_id>`, tối ưu ID bất biến và truy vết dữ liệu nhưng khó tìm bằng File Explorer. Người dùng yêu cầu phân cấp theo Project, Specimen, Session, Capture, ProcessingRun với mã dễ đọc `P0001/S0001/T0001/C0001/R0001`. `SessionStore.read_raw` và `MetadataStore.register_capture` hiện ràng buộc layout v1; đổi tên thủ công sẽ phá reader, quan hệ DB và khả năng xác minh dữ liệu.

## Quyết định

1. Mã `P/S/T/C/R` là **alias công khai có scope**, không thay immutable IDs trong SQLite hoặc RAW metadata. Các code cấp con được hiểu dưới đường dẫn đầy đủ parent.
2. Tổ chức dữ liệu **mới khi code đã hỗ trợ** dưới `01_PROJECTS/P0001_[slug]/01_SPECIMENS/S0001_[slug]/01_SESSIONS/T0001/01_CAPTURES/C0001`; `02_PROCESSING/R0001` đặt bên Session. Giữ nguyên `sessions/` cho dữ liệu legacy; migration chỉ opt-in 07.7.
3. SQLite là nguồn sự thật về ID, code, parent và `relative_path`, không dùng CSV hoặc tên folder để phục hồi quan hệ theo suy đoán.
4. Slug ASCII ngắn được khóa tại lúc tạo, không đồng bộ rename theo tên dự án. Giao diện lấy tên tiếng Việt từ SQLite; hỗ trợ thư mục chỉ có code nếu không có slug an toàn.
5. Layout v1 và v2 phải được phân luồng rõ ràng ở resolver/reader; xác minh hash+metadata+manifest và `COMMITTED` giữ nguyên, reader v2 không giả định `folder_name == capture_id`.
6. Schema version của SQLite, RAW capture schema và storage layout version được lưu/truyền riêng; migration có kiểm thử và backup, không ngầm `create_all` hoặc update đường dẫn bằng tay.
7. Project UI chỉ tải DB khi người dùng chủ động mở root; không tự tạo database hay mở camera khi mở desktop app.

## Phương án không chọn

- **Đổi trực tiếp UUID/ID thành C0001:** phá idempotence, RAW metadata, manifest và khóa ngoại/lineage.
- **Chỉ rename folder legacy:** các reader hiện tại từ chối và SQLite giữ path cũ.
- **Chỉ dùng `catalog.csv`:** có nguy cơ bất nhất, không có FK/transaction.
- **Đưa UUID vào tên folder luôn:** vẫn khó duyệt và không giải quyết nhu cầu File Explorer.

## Hệ quả, tradeoff và gate

- Cần DB migration và Path Resolver rõ trách nhiệm; số mã thêm chi phí metadata/backup, nhưng UI/File Explorer dễ duyệt.
- Cần chống cấp trùng khi ghi đồng thời và kiểm tra chống symlink/junction/traversal/corrupt RAW.
- Tách triển khai nhỏ: 07.2 (code mapping/resolver), 07.3–07.6 (UI/services), 07.7 (optional migration), 07.8 (acceptance).
- Quyết định này **không** tạo ra dữ liệu v2 thực ở 07.1 và **không** chứng nhận trạng thái migration hoặc tính nguyên tử giữa filesystem/SQLite.
