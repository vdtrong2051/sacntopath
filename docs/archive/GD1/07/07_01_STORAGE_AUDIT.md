# GĐ1 / 07.1 — Rà soát lưu trữ GĐ0 và điểm nghẽn triển khai Project Workspace

**Trạng thái:** Audit hoàn tất trên source nhánh `feat/gd1-desktop-ui`, commit `e1a63374380f7816ff5dcff741fa6a7dd985b0b0` (19/10/2026). Đây là **bước tài liệu**: chưa đổi định dạng dữ liệu, SQLite schema, UI hay RAW. Thiết kế mục tiêu đọc tại [07_01_STORAGE_LAYOUT_V2_CONTRACT.md](07_01_STORAGE_LAYOUT_V2_CONTRACT.md) và [ADR-002](../../../decisions/ADR_002_NUMBERED_STORAGE_LAYOUT.md).

## 1. Ranh giới GĐ1

- **06 đã nghiệm thu theo xác nhận operator**: MainWindow / 4 workspace tiếng Việt / docks / task worker / HMI QSS. Không sửa lại ở 07.1.
- **07 (đang triển khai)**: Project Workspace đọc/ghi metadata thật từ SQLite; quản lý Project, Specimen, ScanSession, Capture, ProcessingRun và audit. Tổ chức lại tên thư mục để dễ tìm là yêu cầu bổ sung.
- **08 (chưa triển khai)**: VTK 3D viewer đọc PLY; không liên quan migration RAW ở 07.1.
- GĐ0 là nguồn sự thật cho RAW/metadata hiện hành. Không được gắn `measured` thành `validated`, tạo world pose hoặc RGB–D alignment tự động.

## 2. Audit thực tế theo mã nguồn

| Hạng mục | Đã có / API | Ràng buộc và tác động |
|---|---|---|
| `storage/session_store.py` | `SessionStore(root)`, `commit`, `commit_raw`, `list_committed`, `read`, `read_raw`, `read_capture` | Tự tạo thư mục root; RAW v1/v2 nằm trong `sessions/<session_id>/captures/<capture_id>`. Không hiểu cây dự án đánh số. |
| RAW v2 write | Tạo sibling `.partial`, ghi `color.mjpg`, `depth.y16`, `metadata.json`, `manifest.json`, `COMMITTED`, rename cùng filesystem | Capture chưa được đăng ký SQLite ngay; phải bảo toàn byte gốc và khả năng phục hồi capture orphan. |
| RAW v2 reader | `read_raw` bắt buộc đường dẫn tương đối **đúng 4 thành phần**, `sessions/{id}/captures/{id}`; kiểm tra tên thư mục `capture_id` trùng metadata và manifest | **Không thể** đổi thư mục thành `C0001` chỉ bằng rename/copy rồi gọi reader cũ. |
| RAW v1 reader | `read(path)` kiểm tra `COMMITTED`, cấu trúc NPY; `read_capture()` phân nhánh v1/v2 từ metadata | Phải duy trì khả năng đọc v1 synthetic; không ép nội suy color/depth v2. |
| `metadata/store.py` | `MetadataStore(root)`: `create_project`, `update_project`, `list_projects`, `get_project`, `create_specimen`, `update_specimen`, `create_scan_session`, `close_scan_session`, `get_project_tree`, `register_capture`, `get_capture`, `create/start/finish_processing_run`, `get_processing_run`, `list_events`, `record_event` | Đã hỗ trợ cây quan hệ thật nhưng chưa có mã hiển thị thứ tự, resolver, storage-layout version hoặc path-migration API. |
| SQLite | `<root>/metadata.sqlite3`, `PRAGMA user_version=1`, FK bật, schema guard | `create_all` không migrate v1 lên schema mới. Thêm bảng/constraint phải có migration tường minh và backup. |
| Capture registry | `register_capture(path)` chỉ chấp nhận `sessions/.../captures/...` đúng 4 thành phần; xác thực RAW rồi lưu `captures.relative_path` | Nếu di chuyển RAW bằng File Explorer, relative_path lỗi, `get_capture(..., verify_raw=True)` không còn làm việc. |
| ID | ID ASCII hợp lệ, khóa chính bất biến; Capture v2 ID thường là UUID hex | Tên folder thân thiện **không thay thế** primary key/RAW metadata ID. |
| ProcessingRun | `processing_runs`, `processing_run_inputs`, `output_files` kiểu JSON; liên kết input capture theo ID | `output_files` là tên tham chiếu, **không chứng nhận artifact đã tồn tại**. Không chuyển lịch sử xử lý thành kết quả thực. |
| CLI acquisition | `capture_once` gọi `SessionStore.commit_raw` và `read_raw` bằng đường dẫn cũ | Nếu muốn ghi trực tiếp v2 phải thiết kế giao kèo với luồng capture này, không phá CLI GĐ0. |
| CLI metadata | Tham số `--root`, tạo/lấy cây qua SQLite; không có export index/migration | Phiên 07 chỉ thêm application adapter sau khi chốt hợp đồng dữ liệu. |
| UI 06 | Docks/explorer/inspector đã tồn tại, chưa tự đọc SQLite khi mở app | UI 07 gọi application service qua DTO; không đưa SQLAlchemy vào QWidget. |

**Dữ liệu hiện hành (filesystem):**

```text
scantopath-data/
  metadata.sqlite3
  sessions/<session_id>/captures/<capture_id>/
    color.mjpg
    depth.y16
    metadata.json
    manifest.json
    COMMITTED
```

Dữ liệu v1 dùng `depth.npy`, `rgb.npy`, `metadata.json`, `COMMITTED`. Tệp `manifest.json` và SHA-256 là hợp đồng của RAW **v2**, không mặc định áp dụng cho v1.

## 3. Điểm nghẽn thiết kế và rủi ro

| Mã | Mức | Vấn đề | Yêu cầu giải quyết |
|---|---|---|---|
| ST-01 | BLOCKER | `read_raw` so khớp basename folder với ID RAW | Resolver mới phải xác minh bằng ID bất biến từ metadata/manifest + registry; đường dẫn cũ giữ nguyên reader GĐ0. |
| ST-02 | BLOCKER | `register_capture` hard-code legacy path và ghi relative_path | Viết luồng đăng ký layout v2 có xác thực parent chain và root; không sửa SQLite relative_path bằng tay. |
| ST-03 | BLOCKER | DB schema v1 không có mã `P/S/T/C/R`, counter hay layout version | Migration schema có backup/rollback, ràng buộc unique `(parent_id, ordinal)`, cấp số nguyên tử. |
| ST-04 | HIGH | RAW commit + SQLite là hai giao dịch khác nhau | Quy trình reconcile: pending/orphan; tuyệt đối không xóa RAW khi đăng ký lỗi. |
| ST-05 | HIGH | Tên thư mục dài, slug có dấu và case Windows | Mã đánh số ASCII, slug ngắn **bất biến**, chặn traversal/symlink/reparse và path too long. |
| ST-06 | HIGH | Chuyển thư mục cũ làm hỏng link capture | 07.7 migration tùy chọn, backup, dry-run, kiểm tra checksum, recovery/rollback. |
| ST-07 | MEDIUM | Không có `list_specimens` public; chỉ có `get_project_tree` | Phiên 07.3 dùng query service; không yêu cầu QWidget biết ORM. |
| ST-08 | MEDIUM | `output_files` không được kiểm chứng trên đĩa | Chỉ hiển thị trạng thái tham chiếu, không báo artifact `validated` khi chưa kiểm chứng. |
| ST-09 | MEDIUM | Tên dự án đổi nhưng tên thư mục chứa slug | Không tự rename thư mục khi đổi title; UI luôn ưu tiên nhãn từ SQLite. |
| ST-10 | MEDIUM | Export index CSV là dữ liệu phụ | CSV được xây từ DB, ghi atomic; tránh công thức CSV injection, không dùng làm khóa chính. |

## 4. Những điều **không** làm ở 07.1

- Không tạo thư mục `01_PROJECTS/` bên trong dữ liệu thật, không sửa `metadata.sqlite3`, `SessionStore`, `MetadataStore`, pyproject, ứng dụng hoặc test.
- Không rename/move/duplicate RAW hiện có, không sửa `capture_id`, `session_id`, `manifest.json`, `metadata.json`, `COMMITTED` hoặc checksum.
- Không coi folder code như ID quốc gia hoặc thay toàn bộ UUID: mã hiển thị phải có bảng ánh xạ và được cấp độc lập.
- Không tự triển khai migration 07.7 trước khi có giao thức v2 reader/writer/validator và kiểm thử 07.2.

## 5. Phân công việc tiếp theo theo cổng nghiệm thu

| Bước | Deliverable | Gate tối thiểu |
|---|---|---|
| **07.1** | Audit này + Storage Layout v2 Contract + ADR-002 | Rà soát code và kiểm thử hồi quy không đổi; tài liệu không chứa lệnh đụng RAW. |
| **07.2** | Registry cấp mã `P/S/T/C/R`, path resolver đọc legacy/v2, schema migration chủ động, test | Không trùng mã khi cấp đồng thời; giữ GĐ0 reader và checksum; reject traversal, giả tên, thiếu link. |
| **07.3** | Application Project Services/DTO thực nối SQLite | Reopen persistent, CRUD/query/error; không gọi SQLAlchemy từ QWidget. |
| **07.4** | Project Explorer dữ liệu thật + navigation | Cây đúng parent, empty/loading/error/selected, không tạo record giả. |
| **07.5** | Forms/Inspector và validation | Tạo/sửa Project, Specimen, Session dùng API thật, không làm hỏng key bất biến. |
| **07.6** | Capture, Run, Audit timeline + verify | Phân biệt RAW registered/present/verified/corrupt; `ProcessingRun` chỉ metadata. |
| **07.7** | Dry-run/migration **tùy chọn** legacy→v2 + rollback | Byte+checksum giữ nguyên; SQLite link đúng; kiểm tra recovery sau restart. |
| **07.8** | Tích hợp/Windows acceptance + native regression | UI 14-inch, SQLite reopen, RAW v1/v2, CTest 2/2, native self-test. |

## 6. Nguồn source đã đối chiếu

- `src/scantopath/storage/session_store.py` (`commit_raw`, `read_raw`, `read_capture`).
- `src/scantopath/metadata/store.py` (`MetadataStore.__init__`, `register_capture`, `get_capture`, `get_project_tree`, ProcessingRun).
- `src/scantopath/domain/raw_rgbd.py` (`RawRgbdCaptureMetadataV2`: ID, riêng lưới màu/sâu, pose unknown).
- `src/scantopath/acquisition/capture_once.py`, `src/scantopath/metadata/cli.py`.
- `docs/PRE_03_RAW_STORAGE.md`, `docs/PRE_05_GD0_METADATA_PERSISTENCE.md`, `docs/ROADMAP.md`, `docs/gd1/06_6_INTEGRATED_ACCEPTANCE.md`.

**Nghiệm thu 07.1:** tài liệu thiết kế có thể được khóa khi operator chạy kiểm thử và commit; chưa thể tuyên bố layout v2 đã vận hành.
