# GĐ1 / 07.1 — Hợp đồng mục tiêu Storage Layout v2 (thiết kế, chưa triển khai)

**Quyết định thiết kế cho 07.2+**. Cần phân biệt ba version: **RAW Capture schema v1/v2** (định dạng packet), **SQLite schema** (`PRAGMA user_version=1` hiện tại; schema nâng cấp là chuyện riêng) và **Storage Layout v1/v2** (cách tổ chức filesystem). Không lấy số `v2` ở một loại để suy ra loại khác.

## 1. Cây dữ liệu hướng người dùng

```text
scantopath-data/
├── metadata.sqlite3                   # nguồn sự thật, quan hệ / ID / ánh xạ
├── 00_INDEX/                          # chỉ export tra cứu, không authoritative
│   └── catalog.csv                    # tùy chọn ở 07.2+, sinh từ SQLite
├── 01_PROJECTS/
│   └── P0001_HopGiamToc/              # project code toàn kho + slug bất biến
│       └── 01_SPECIMENS/
│           └── S0001_TrucVit/         # specimen code trong project
│               └── 01_SESSIONS/
│                   └── T0001/         # session code trong specimen
│                       ├── 01_CAPTURES/
│                       │   ├── C0001/ # capture code trong session
│                       │   │   ├── color.mjpg
│                       │   │   ├── depth.y16
│                       │   │   ├── metadata.json
│                       │   │   ├── manifest.json
│                       │   │   └── COMMITTED
│                       │   └── C0002/
│                       └── 02_PROCESSING/
│                           └── R0001/ # run code trong session
│                               └── 01_OUTPUTS/
├── 02_EXPORTS/                         # xuất bản sao cho người dùng; có link nguồn
├── 03_REPORTS/                         # báo cáo, không chứa RAW nguồn
└── sessions/                            # LEGACY v1 layout GĐ0 (giữ nguyên)
    └── <session_id>/captures/<capture_id>/...
```

Đây là **sơ đồ mục tiêu**, không phải lời khẳng định các folder/processings/results đã có hoặc đã được kiểm chứng. Processing outputs chỉ được tạo khi thuật toán thật chạy ở những phiên tương ứng. Không sinh thư mục rỗng giả lập khi 07.1.

## 2. Hợp đồng danh tính và đánh số

| Loại | Mã hiển thị / directory | Phạm vi ordinal | ID nội bộ không đổi |
|---|---|---|---|
| Project | `P0001` hoặc `P0001_HopGiamToc` | toàn bộ root | `projects.project_id` |
| Specimen | `S0001` hoặc `S0001_TrucVit` | mỗi Project | `specimens.specimen_id` |
| ScanSession | `T0001` | mỗi Specimen | `scan_sessions.session_id` |
| Capture | `C0001` | mỗi ScanSession | `captures.capture_id`, RAW metadata ID |
| ProcessingRun | `R0001` | mỗi ScanSession | `processing_runs.run_id` |

- Code dạng `[PSTCR][0-9]{4,}`; bắt đầu ở 0001, **tối thiểu bốn chữ số**, tự tăng bề rộng khi >9999 (không cắt số). Không tái sử dụng ordinal của record đã tạo dù record/archive bị ẩn.
- Mọi ID nội bộ theo GĐ0 vẫn **unique toàn kho**. Code của entity cấp con chỉ unique trong **parent**: `P0001/S0001/T0001/C0001` được hiểu đầy đủ, không truy bằng `C0001` đơn lẻ.
- Mỗi entity chỉ có **một mã hiển thị ổn định và một parent chain**; `public_code`, `ordinal`, `parent_id`, `relative_path`, `layout_version` là metadata riêng. `UNIQUE(parent, ordinal)` và FK khóa chain. `parent_id` của Project là root (scope singleton). ID nội bộ không đổi khi folder được gán mã.
- Cấp số trong giao dịch SQLite có kiểm soát ghi đồng thời: không dùng `SELECT MAX()+1` ngoài transaction; cơ chế counter + `BEGIN IMMEDIATE` hoặc ràng buộc unique + retry có kiểm thử race. Không cấp lại số khi transaction thất bại một cách không có chính sách.
- Code/slug là ASCII; tên dự án tiếng Việt giữ trong SQLite/UI. Slug không bắt buộc và chỉ lấy mẫu khi tạo (vd. `HopGiamToc`), độ dài tối đa 24 ký tự `[A-Za-z0-9_]`, không trailing dot/space hoặc Windows reserved name, không tự rename sau `update_project`/`update_specimen`. Có thể chọn chỉ `P0001` / `S0001` nếu transliteration không rõ; code vẫn duy nhất trong cấp cha.
- Trên Windows, preflight path length, `Path.resolve`, từ chối path escaping/reparse point/symlink và traversal; không diễn giải đường dẫn tùy ý do người dùng nhập thành quyền đọc ngoài store root. Không dùng file name làm nguồn xác nhận quyền sở hữu duy nhất.

## 3. Resolver, liên kết và kiểm chứng

**Đầu vào:** `(entity_type, immutable_id)` hoặc `(root, full_hierarchical_public_code)`; **đầu ra:** DTO path metadata đã xác minh `layout_version`, `relative_path`, `entity_ids`, `public_code`, `existence`, `integrity_state` (không trả ORM Session hay native pointer). Tuyệt đối không dùng `glob('**/C0001')` để tìm RAW không qua registry.

**Legacy layout v1:**

```text
sessions/<session_id>/captures/<capture_id>
```

Tiếp tục gọi `SessionStore.read_capture`/`read_raw` GĐ0 nguyên bản. Nếu cùng project có legacy + numbered captures, UI đưa vào **một cây quan hệ theo SQLite**, không ép đổi vị trí file cũ khi mở Project.

**Numbered layout v2:**

```text
01_PROJECTS/P0001_HopGiamToc/01_SPECIMENS/S0001_TrucVit/
01_SESSIONS/T0001/01_CAPTURES/C0001
```

Ở 07.2 phải xây **reader/writer có version routing rõ ràng**: registry resolve `C0001` → immutable capture_id; kiểm tra parent `P/S/T`, đường dẫn thực tế nằm trong root và không là symlink. Trong folder RAW v2, kiểm tra **`metadata.capture_id == manifest.capture_id == captures.capture_id`**, kiểm tra hash/size và `COMMITTED`. **Không** so `metadata.capture_id` với basename `C0001`: đó là giả định của GĐ0 cần được tháo ở *đường đọc v2 mới*, không nới lỏng legacy reader một cách vô điều kiện.

`register_capture` GĐ0 chỉ nhận đường dẫn cũ. Đường ghi/đăng ký v2 phải xác thực hình dạng mới, parent chain, raw identity, đồng thời giữ API legacy ổn định. Nếu phải thêm API thì có tên rõ (`register_numbered_capture` hoặc service adapter) và kèm migration/test; **không sửa SQLite bằng tay**.

`captures.relative_path` được quản lý bởi registry qua giao dịch có audit. Khi dùng layout v2, không yêu cầu RAW metadata ghi đè code hiển thị hay địa chỉ vật lý; provenance nguyên bản giữ nguyên.

**An toàn commit:** ghi vào `.partial` cạnh đích, flush và rename sau marker `COMMITTED`, không ghi vào folder tồn tại. RAW commit và SQLite vẫn là hai giao dịch: nếu đăng ký thất bại giữ dữ liệu RAW orphan cho recovery có kiểm soát, không xóa tự động; cần idempotent reconcile ở 07.7. SHA-256 là phát hiện hư hỏng ngẫu nhiên, không phải bảo đảm chữ ký/chống giả mạo.

## 4. Hợp đồng schema và catalog

- Database **hiện tại** có `PRAGMA user_version=1`, khóa ngoại bật. Không dùng `CREATE TABLE IF NOT EXISTS` để âm thầm sửa DB v1 có dữ liệu.
- 07.2 phải đưa ra migration DB version mới tường minh; backup SQLite nhất quán khi đang mở bằng SQLite backup API hoặc khi DB đã được đóng, không copy bừa file đang có WAL; preflight dung lượng, bản DB lạ, rollback và test version guard.
- Thiết kế ưu tiên bảng `storage_entries(entity_type, immutable_id, parent_type, parent_id, ordinal, public_code, layout_version, relative_path)` + counter theo scope; hoặc các bảng con có FK phù hợp. Phải bảo đảm FK/unique phù hợp với khóa polymorphic (SQLite không tự enforce được FK kiểu `entity_type + immutable_id` vào nhiều bảng). **Đây là hướng thiết kế, chưa duyệt SQL DDL trước 07.2**.
- Ở 07.2 lựa chọn DDL bắt buộc chứng minh referential integrity, tồn tại parent trong bảng thật, transaction cấp số/đường dẫn. Tránh mapping trùng, dangling, path alias hoặc slug collision.
- `00_INDEX/catalog.csv` chỉ xuất **on demand** từ một snapshot SQLite, ghi file tạm rồi rename. Các cột tối thiểu `entity_type,internal_id,public_path,storage_relative_path,layout_version,state`; dữ liệu text escape CSV, vô hiệu formula injection (`=`, `+`, `-`, `@` ở đầu ô). Không có sync hai chiều.

## 5. Các trường hợp lỗi bắt buộc

| Case | Ứng xử yêu cầu |
|---|---|
| Root chưa mở / database không có | UI chỉ báo chưa chọn kho; **không** tự tạo SQLite qua khởi động ứng dụng. |
| Entity ID có nhưng chưa có số folder | Có thể đọc quan hệ legacy qua SQLite; trạng thái `legacy`/`chưa cấp mã`, không báo thiếu RAW khi RAW còn tồn tại. |
| Code `C0001` ở nhiều Session | Yêu cầu đầy đủ parent chain hoặc ID, không lấy bản đầu tiên. |
| Path bị sửa ngoài ứng dụng / symlink / traversal | Trả lỗi integrity/path; không tự chạy tìm hoặc sửa file để khớp. |
| RAW `COMMITTED` thiếu / manifest mismatch / checksum fail | Không được hiển thị `verified`; không sửa RAW tại chỗ. |
| RAW commit thành công, SQLite ghi thất bại | Báo orphan, không xóa; recovery thủ công/được xác nhận. |
| Process crash khi cấp số hay migration | SQLite atomic, không trùng mã và có báo cáo recovery; không assume cả filesystem+DB atomic. |
| Project đổi tên sau khi tạo | Không tự đổi tên folder; GUI hiển thị tên SQLite mới. |
| ProcessingRun có `output_files` nhưng file không tồn tại | Hiển thị tham chiếu, không coi là artifact đã xác minh. |
| Chuyển dữ liệu legacy vào v2 | Chỉ ở 07.7, có dry-run, backup, checksum, idempotency và rollback. |

## 6. Acceptance 07.2 và thứ tự phụ thuộc

1. Hiển thị cây SQLite có số `P/S/T/C/R` **mà không di chuyển RAW legacy**.
2. Cấp số xác định và độc nhất qua reopen/concurrent creates; old project IDs giữ nguyên.
3. Resolver đọc legacy RAW v1/v2 như trước và đọc numbered RAW v2 có cùng dữ liệu/hash; không nới lỏng path verification.
4. Ngăn symbolic link/junction, traversal, alias, duplicate/mismatched parent ID.
5. Test ghi/đăng ký lỗi giữa RAW và DB; không mất file gốc, khả năng recover rõ ràng.
6. DB migration không phá schema v1, có backup thật, test unknown version refusal.
7. `catalog.csv` là phụ trợ, tái tạo được, không được dùng để sửa relationship.
8. Mọi Qt UI ở 07.3+ đi qua application services, không truyền SQLAlchemy object trực tiếp.

**Lưu ý chốt:** `Storage Layout v2` là chuẩn mục tiêu được duyệt ở mức tài liệu 07.1. Chưa có dữ liệu nào được đổi tên, và bộ đọc/ghi GĐ0 hiện không hiểu cấu trúc v2. Không đặt RAW vào cây đánh số thủ công trước khi 07.2 có reader/writer/validator đúng.
