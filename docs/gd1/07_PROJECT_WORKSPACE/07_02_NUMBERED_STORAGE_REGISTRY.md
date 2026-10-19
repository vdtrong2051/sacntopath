# GĐ1 / 07.2 — Numbered Storage Registry và Path Resolver

**Mốc source:** `feat/gd1-desktop-ui`, commit `417558619128cfcfc267640cda8d9b13f2aaee99` (07.1 đã push). **Mục tiêu:** triển khai hợp đồng ở [07.1](07_01_STORAGE_LAYOUT_V2_CONTRACT.md) và [ADR-002](../../decisions/ADR_002_NUMBERED_STORAGE_LAYOUT.md), không sửa dữ liệu RAW legacy trong lần áp dụng patch.

## 1. Kết quả triển khai, ranh giới

| Thành phần | Đã triển khai | Không hàm ý |
|---|---|---|
| `storage/numbered_schema.py` | Schema SQLite v2 gồm 5 bảng mapping có FK đến Project/Specimen/Session/Capture/ProcessingRun, bảng counter theo scope, capture reservation; triggers chống reparent / sửa mapping | Không tự migrate DB đang dùng |
| `NumberedStorageRegistry.migrate_database(root)` | Migration **tường minh** v1→v2, SQLite backup API nhất quán với WAL, kiểm tra integrity/FK, kiểm tra schema/version, kiểm tra dung lượng, backup riêng và DDL trong transaction | Không dịch chuyển RAW; không tự restore nếu người dùng tiếp tục dùng DB khác sau migration |
| `assign()` / `assign_all()` | Cấp `P0001/S0001/T0001/C0001/R0001` bền vững, counter trong `BEGIN IMMEDIATE`; legacy Capture chỉ được cấp **alias**, physical path vẫn cũ | `assign_all()` không tạo cây thư mục hàng loạt; không chép RAW |
| `resolve_id()` / `resolve_public_path()` | Ánh xạ theo ID hoặc mã **đầy đủ phân cấp**, trả `StorageLocation`; có tùy chọn `verify=True` | Không dùng glob; không coi mã `C0001` đơn lẻ là duy nhất |
| `reserve_capture()` | Đặt chỗ mã Capture trong SQLite; phục hồi bằng `pending_reservations()` | Không phải Capture đã committed hay ProcessingRun |
| `write_reserved_capture()` + `register_reserved_capture()` | Ghi RAW v2 mới vào `01_PROJECTS/.../C0001`, xác minh manifest/byte/SHA-256 rồi đăng ký SQLite + audit atomically trong cùng một transaction DB | Hai transaction FILESYSTEM + SQLite vẫn **không đồng bộ tuyệt đối**; giữ orphan nếu đăng ký thất bại |
| `SessionStore.read_raw_numbered()` | Reader **riêng** cho đường numbered RAW v2, kiểm tra checksum và ID bất biến từ DB/manifest/metadata | Không nới lỏng `read_raw()` legacy; không đặt `capture_id='C0001'` |
| `export_catalog()` | CSV xuất on demand từ SQLite, ghi file tạm và rename, BOM UTF-8 cho Excel, chặn công thức CSV | CSV không authoritative, không phải bidirectional sync |
| `numbered_cli.py` | Lệnh kiểm tra/migrate (có `--confirm`), cấp alias legacy, tra mã, xuất catalog, liệt kê pending | Không tự khởi động camera, SQLite khi mở PySide6 |

**Ba loại version phải tách:** RAW metadata schema (v1/v2), SQLite (`PRAGMA user_version`: 1→2), filesystem layout (legacy=1, numbered=2). Nâng SQLite v2 **không** đồng nghĩa đổi RAW schema. Một kho chứa Capture legacy và numbered đồng thời.

## 2. Thư mục sau khi có Capture mới

```text
scantopath-data/
  metadata.sqlite3
  00_INDEX/
    backups/metadata-before-v2-<UTC>.sqlite3
    catalog.csv                     # tùy chọn, sinh thủ công
  01_PROJECTS/
    P0001/
      01_SPECIMENS/
        S0001/
          01_SESSIONS/
            T0001/
              01_CAPTURES/
                C0001/
                  color.mjpg
                  depth.y16
                  metadata.json      # capture_id vẫn là ID nội bộ
                  manifest.json      # SHA-256; capture_id vẫn là ID nội bộ
                  COMMITTED
  sessions/<session_id>/captures/<capture_id>/  # legacy giữ nguyên
```

`02_PROCESSING/R0001` được **reserve ở dạng metadata** (ProcessingRun hiện chỉ lưu lịch sử), chưa tạo file/kết quả 3D. `02_EXPORTS` / `03_REPORTS` chỉ tạo ở những phiên thật sự dùng. Số có ít nhất 4 chữ số, >9999 tự dài hơn; Project code toàn kho, các code con tăng theo parent. Tên Project/Specimen tiếng Việt hiển thị từ SQLite; tên folder **chỉ là code ASCII bất biến**, không phụ thuộc tên người dùng.

## 3. API lưu Capture mới (khi nghiệp vụ thực được nối ở 07.3+/09)

```python
# Workflow có chủ đích, ví dụ; packet là RawRgbdCapture V2 **đã có**.
from scantopath.storage.numbered import NumberedStorageRegistry

registry = NumberedStorageRegistry(root)  # root đã explicit migrate schema v2
slot = registry.reserve_capture(packet.metadata.capture_id,
                                packet.metadata.session_id,
                                packet.metadata.specimen_id)
path = registry.write_reserved_capture(packet)             # RAW commit; chưa DB register
record = registry.register_reserved_capture(slot.capture_id)  # check hashes + DB register
assert record.public_path == slot.public_path
assert record.integrity_state == "verified"
```

Trường hợp rơi giữa ghi RAW và đăng ký: `pending_reservations()` ghi lại slot bền vững. **Không xóa tự động** RAW orphan hoặc reuse code. Dữ liệu RAW trên đĩa bất biến; `register_reserved_capture()` có thể gọi lại sau khi khắc phục lỗi (nếu Capture còn hợp lệ, session còn `open`), không cần ghi RAW lần nữa. Không nhận RAW v1 trên đường writer numbered; RAW v1 chỉ được đọc legacy như trước.

**Hạn chế có chủ đích:** SDK one-shot hiện gọi `SessionStore.commit_raw()` legacy, **không** tự chuyển sang numbered. Phiên 07.3+/09 phải chủ động dùng workflow v2. Dữ liệu GĐ0 cũ chỉ được đưa vào bảng alias; việc di chuyển có kiểm chứng và rollback thuộc **07.7**. Sau mapping legacy, trong `resolve_id(capture)` có `public_path` mới nhưng `relative_path` cũ và `layout_version=1`; không nói với người dùng rằng thư mục `C0001` đã có trên đĩa.

## 4. Lệnh CLI — trên **bản sao kho thử**, không chạy thẳng production

```powershell
cd E:\1_BigProject\scantopath\scantopath-software
$py = (Resolve-Path .\.venv\Scripts\python.exe).Path
$root = 'E:\ScanToPath-TestData-COPY'  # phải là BẢN SAO và có metadata.sqlite3 v1

& $py -m scantopath.storage.numbered_cli --root $root status
# ĐÓNG app / CLI truy cập cùng SQLite, bảo đảm đã backup kho gốc trước.
& $py -m scantopath.storage.numbered_cli --root $root migrate --confirm
& $py -m scantopath.storage.numbered_cli --root $root assign-all
& $py -m scantopath.storage.numbered_cli --root $root resolve --public-path P0001
& $py -m scantopath.storage.numbered_cli --root $root catalog
& $py -m scantopath.storage.numbered_cli --root $root pending
```

**Không áp dụng riêng `migrate --confirm` trên `scantopath-data` thật khi chưa quyết định chuyển schema.** `apply.ps1` và `verify.ps1` của patch này **không nâng schema database**. Test dùng `tmp_path`, dữ liệu RAW synthetic riêng, không yêu cầu Gemini 2.

Sau migrate, `MetadataStore` chấp nhận cả v1/v2. SQLite v2 chứa các bảng riêng, không sửa bảng GĐ0 hay primary key của Capture. File backup tồn tại độc lập dưới `00_INDEX/backups` và không bị patch xóa. Việc restore cần dừng ứng dụng, dùng backup nhất quán, xem lại dữ liệu mới được tạo sau backup; **không tự replace** DB khi còn ứng dụng đang mở.

## 5. Hợp đồng an toàn và điều kiện nghiệm thu

- Không tự mở `metadata.sqlite3` khi mở app; CLI `status` là chế độ đọc, với kho chưa tồn tại không tự tạo database.
- Counter/reservation là SQLite transaction; mã đã được phát hành/đặt chỗ không tự dùng lại, thứ tự độc nhất theo parent. FK + triggers chặn mapping sai parent; mapping bất biến qua UPDATE thông thường. Di chuyển legacy 07.7 cần kế hoạch migration riêng.
- Path lookup chỉ dựa trên registry, không scan filesystem. Chặn traversal, absolute path, symlink/junction/reparse point (trong phạm vi API `pathlib` Python 3.12), checksum mismatch, không tạo kết quả giả.
- RAW v2 ghi với cùng bytes `color.mjpg`/`depth.y16` và manifest gốc theo PRE-03. Manifest checksum là phát hiện hỏng dữ liệu, **không** phải chữ ký chống giả mạo. Không suy ra pose/độ chính xác/alignment RGB-D.
- `StorageLocation.exists=False` hay `integrity_state=not_checked` **không phải** đã verify; `verify=True` mới kiểm RAW. `ProcessingRun.output_files` chỉ là tham chiếu, không coi là artifact tồn tại.
- Schema migration cần close các client khác; backup API bảo đảm ảnh chụp nhất quán trong SQLite, nhưng vẫn có cửa sổ thời gian giữa backup và khóa DDL. Không tự tuyên bố nhất quán nếu có writer bên ngoài bất chấp quy trình operator.

**Gate Windows:** `tests/test_gd1_07_2_numbered_storage.py` (17 test), full pytest/Qt (symlink Windows có thể skip vì đặc quyền, phải ghi rõ), CTest 2/2, native self-test exit 0; xác nhận Git chỉ đúng bảy file của 07.2. Một bài fixture không thay thế benchmark camera thật. Kiểm thử chỉ trên temp root; application UI, C++ và SDK GĐ0 không thay đổi.

## 6. Bước tiếp theo

**07.3**: Project Application Services/DTO thực, kết nối `MetadataStore` + `NumberedStorageRegistry` trong luồng người dùng chủ động mở kho, hiển thị mã `P/S/T/C/R` và trạng thái legacy/numbered; không gọi ORM hay thao tác filesystem trực tiếp trong QWidget. **07.7**: migration RAW legacy→numbered, dry-run, checksum, rollback và recovery.
