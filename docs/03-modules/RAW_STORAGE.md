# RAW Storage — Ghi, đọc và bảo toàn dữ liệu gốc

> **owner:** `storage` / `metadata` boundary · **as_of_commit:** `0557c0d4fed9a3df3b180fc9872c6d3293b5f0d5` · **verified_at:** 2026-10-28  
> **scope:** RAW legacy v1, RAW RGB-D v2, numbered layout + migration tường minh · **implementation:** IMPLEMENTED (các API đã có), HMI/độ bền mất điện chưa chứng nhận · **source-of-truth:** `src/scantopath/storage/`, `src/scantopath/metadata/`, test tương ứng.  
> **evidence:** static source + GĐ0/GĐ1 tests; **manual/physical verification:** NOT_TESTED trong DOC-03B.

## 1. Mục đích và tình huống sử dụng

RAW Storage lưu ảnh màu và độ sâu **đúng byte nhận được**, cung cấp bằng chứng truy vết mà phép xử lý 3D sau này có thể đọc lại. Một ví dụ: sau một shot Gemini 2, dữ liệu gốc phải giữ nguyên cả khi người dùng mở Viewer, lọc point cloud hoặc chạy lại thuật toán với tham số khác. Vì thế mọi file dẫn xuất phải được quản lý riêng, không cập nhật RAW tại chỗ.

Lưu ý **hai hệ thống song song**: tệp chứa byte RAW ở filesystem và metadata/quan hệ Project ở SQLite. SQLite không phải kho chứa pixel; việc commit RAW **không** đồng nghĩa giao dịch SQLite tương ứng đã hoàn tất.

## 2. Phạm vi chạy được và chưa có

| Năng lực | Hiện trạng | Giới hạn |
|---|---|---|
| `SessionStore.commit()` / `.read()` legacy | Có cho `FrameBundle` v1, dữ liệu NumPy đã registered | Không dùng để ghi RAW v2 MJPEG/Y16 độc lập |
| `commit_raw()` / `read_raw()` v2 | Có, kiểm checksum và hình dạng thư mục | Không chứng nhận chịu mất điện tuyệt đối |
| `commit_raw_numbered()` | Có khi caller sở hữu reservation SQLite | Không tự cấp mã hoặc đăng ký metadata |
| `NumberedStorageRegistry` | Mã P/S/T/C/R + resolver + catalog; schema v2 | Cần kho SQLite đã tồn tại và di trú tường minh |
| `LegacyRawMigrator` | Copy-first, preflight, apply/rollback có kiểm soát | Không tự chạy lúc mở desktop; đòi app/writer đóng |
| Đồng bộ transaction giữa SQL và filesystem | **Không có ACID xuyên hai kho** | Cần phát hiện/khôi phục trạng thái nửa chừng |

## 3. Sơ đồ kiến trúc và source

```text
[RawRgbdCapture: metadata + owned bytes]
      │
      ├─ SessionStore.commit_raw() ───────────────────────────────┐
      │               legacy sessions/<id>/captures/<id>/         │
      └─ NumberedStorageRegistry.reserve_capture()               │
              → SessionStore.commit_raw_numbered()               │
              → NumberedStorageRegistry.register_reserved_capture()
                                                              ↓
                 filesystem: partial → manifest + COMMITTED → rename
                          ↕ verify hash / content / path safety
                 SQLite metadata: Project/Specimen/Session/Capture
```

| Source | Trách nhiệm |
|---|---|
| `src/scantopath/storage/session_store.py` | API ghi/đọc v1/v2, kiểm byte, marker/manifest |
| `src/scantopath/storage/numbered.py` | façade `NumberedStorageRegistry`, cấp mã và điều phối |
| `src/scantopath/storage/numbered_contracts.py` | `StorageLocation`, `CaptureReservation`, ràng buộc đường dẫn |
| `src/scantopath/storage/numbered_ops/capture.py` | reservation → write → register, recovery trạng thái chờ |
| `src/scantopath/storage/numbered_ops/migration.py` | nâng SQLite v1→v2 có backup |
| `src/scantopath/storage/legacy_migration.py` | di dời bản sao RAW legacy opt-in với rollback |
| `src/scantopath/storage/numbered_schema.py` | bảng phụ, khóa ngoại, trigger bất biến |
| `src/scantopath/metadata/store.py`, `metadata/schema.py` | nguồn sự thật entity IDs/relations và ProcessingRun |

## 4. Đầu vào, đầu ra và hợp đồng dữ liệu

**Định dạng Capture RAW v2** khi commit đầy đủ:

```text
sessions/<session_id>/captures/<capture_id>/
├── color.mjpg       # MJPEG gốc; không decoded/re-encoded
├── depth.y16        # uint16 little-endian; chưa align
├── metadata.json    # RawRgbdCaptureMetadataV2
├── manifest.json    # size_bytes + SHA-256 từng payload
└── COMMITTED        # marker chỉ xuất hiện ở bản ghi công bố
```

Với numbered layout, thư mục Capture nằm dưới `01_PROJECTS/P0001/.../01_SPECIMENS/S0001/.../01_SESSIONS/T0001/01_CAPTURES/C0001` (code dưới namespace parent), **không** thay immutable `capture_id`/`session_id` trong metadata. `capture_schema_version`, SQLite `PRAGMA user_version`, `layout_version` là **ba version khác nhau**; `v2` của cái này không suy ra `v2` của cái kia.

| Trường | Kiểu/đơn vị | Quy tắc |
|---|---|---|
| `color.mjpg` / `depth.y16` | `bytes`, raw | SHA-256 của byte, Y16 bytes = 2×W×H |
| `manifest.json` | JSON: tên file → size/hash | từ chối thiếu/thừa file/hỏng hash |
| `COMMITTED` | marker file | cần cho reader, nhưng **không** là bằng chứng chống mất điện tuyệt đối |
| `metadata.json` | Pydantic schema v2 | thông tin calibration gốc, sensor source, frame IDs |
| `relative_path` ở SQLite | path tương đối | không đồng nhất tên thư mục với UUID, chống traversal/symlink |
| `capture_id` và mã `C...` | immutable ID / public alias | map trong SQLite; không tự đổi identity |

**Không nhầm với legacy v1:** `depth.npy`, `rgb.npy`, `metadata.json` + `COMMITTED` dùng API `commit()/read()`; `rgb.npy` đã registered vào cùng lưới depth theo hợp đồng v1. RAW v2 giữ MJPEG và Y16 riêng, không có auto-align.

## 5. Luồng hoạt động bình thường

**A. One-shot legacy-layout RAW v2:** `RawRgbdCapture` được kiểm bằng domain contract → `commit_raw()` kiểm ID và đích → ghi vào thư mục `.partial` kề bên → `fsync` từng file → tạo manifest và marker → đổi tên sang thư mục cuối trên cùng filesystem → `read_raw()` duyệt file/hash và tái tạo capture. Nếu dữ liệu sau đọc không giống packet đầu vào, caller báo lỗi, không tuyên bố roundtrip PASS.

**B. Numbered layout:** Operator chọn kho SQLite hiện có → migrate schema v1→v2 *tường minh* với backup khi có nhu cầu → tạo entity và mã P/S/T... → `reserve_capture(capture_id, session_id, specimen_id)` cấp C-code bền vững → `write_reserved_capture(capture)` ghi RAW gốc → `register_reserved_capture(capture_id)` xác minh và cập nhật SQLite. Nếu dừng giữa write/register, dùng `pending_reservations()` để chẩn đoán; không tự xóa dữ liệu chưa đăng ký.

**C. Đọc lại/kiểm toàn vẹn:** caller lấy path từ SQLite, resolver chặn thư mục vượt root và liên kết không hợp lệ → `read_raw()` xác nhận `COMMITTED`, manifest, byte hash và metadata → trả cấu trúc bất biến. Viewer mở PLY/OBJ ngoài **không** kích hoạt luồng này.

## 6. Bất biến an toàn

- Không sửa RAW đã công bố, không thay bytes khi kiểm tra hoặc đọc.
- Không coi rename thư mục là giao dịch ACID xuyên filesystem+SQLite; không cam kết durability mất điện tuyệt đối.
- Không tự dùng `create_all`/migrate schema khi chỉ đọc Project; `MetadataStore` có bước tạo DB mới nếu người dùng **khởi tạo tường minh** qua API, khác `probe_existing()` chỉ kiểm kho có sẵn.
- Không ghi các trường `measured` từ fixture như phép đo thật. Không tự align RGB và depth.
- Không xóa capture legacy khi migrate; `LegacyRawMigrator` dùng copy-first và backup.
- Symlink/reparse point/junction: code kiểm đường dẫn trong các đường đi được bảo vệ; test SKIP trên Windows không chứng nhận mọi nhánh đã chạy.

## 7. Vòng đời, trạng thái và phục hồi

```text
UNRESERVED → RESERVED → RAW_WRITTEN → REGISTERED
                │             │
                └─ error      └─ SQLite registration error → pending reservation

RAW write: .partial → manifest/COMMITTED → rename → final
```

Ứng dụng phải xử lý rollback/resume một cách tường minh, không đoán rằng có `.partial` nghĩa là có một Capture hợp lệ. `LegacyRawMigrator.plan()` chỉ mô tả chuyển đổi; `apply()` có thể ghi bản sao và backup; `rollback(migration_id)` phải được chỉ định đúng mã. Các lệnh này **không** thuộc quy trình kiểm thử docs hay quickstart.

## 8. Tình huống lỗi và cách xử lý

| Hiện tượng | Điểm kiểm tra | Xử lý | Test/giới hạn |
|---|---|---|---|
| thiếu/thừa file, sai hash | `SessionStore.read_raw()` | từ chối; không sửa file tự động | `tests/unit/raw/test_raw_storage.py` |
| thiếu `COMMITTED` | reader | từ chối capture chưa hoàn tất | raw storage tests |
| path traversal/junction | numbered safe path | từ chối truy cập | `tests/integration/storage/test_gd1_07_2_numbered_storage.py`; Windows symlink có SKIP |
| không có `metadata.sqlite3` | `NumberedStorageRegistry` / `probe_existing` | yêu cầu chọn kho có sẵn; không tạo giả | project integration tests |
| schema v1 khi cần numbered | migrate explicitly | backup, kiểm integrity, chỉ thao tác trên bản sao test | migration tests |
| lỗi trong đăng ký SQLite sau ghi RAW | reservation tồn tại | audit `pending_reservations()`, sửa có kiểm soát | `tests/integration/storage/test_gd1_07_8_integrated.py` |
| đích numbered đã có | check trước ghi | không overwrite | storage tests |
| mất điện đang ghi | trạng thái filesystem không được bảo đảm | kiểm thủ công/bản sao và phục hồi; không gọi tự động PASS | NOT_TESTED physical durability |

## 9. Ví dụ an toàn

Chạy tại gốc repository Windows; chỉ dùng thư mục `tmp_path` của pytest, **không** chạy migration với dữ liệu thật:

```powershell
& .\.venv\Scripts\python.exe -X utf8 -m pytest -q `
  tests/unit/raw/test_raw_storage.py `
  tests/integration/storage/test_gd1_07_2_numbered_storage.py `
  tests/integration/storage/test_gd1_07_7_legacy_migration.py
```

Kiểm một Capture v2 đã lưu có chủ ý:

```powershell
& .\.venv\Scripts\python.exe -X utf8 -m scantopath.acquisition.capture_once `
  --verify '<CAPTURE_DIR_V2>' --output '<DATA_ROOT>'
```

`--verify` không mở camera, nhưng có thể phát sinh lỗi khi file hỏng; **không** dùng lệnh này như một công cụ sửa chữa. Không thực thi `LegacyRawMigrator.apply()` trong phần này vì cần bước preflight, backup và đóng mọi writer.

## 10. Hiệu năng và độ tin cậy

Chi phí chính là ghi/đọc dữ liệu nén MJPEG và Y16 kèm SHA-256; số đo thông lượng/IOPS dưới điều kiện ổ đĩa/NTFS chưa có ở mốc DOC-03B. Bản ghi R6/C++ không chứng minh chịu ngắt nguồn hoặc thời gian khôi phục khi fail. Bất biến bảo toàn byte là bằng chứng **hợp đồng**, không phải chứng thư an toàn lưu trữ tuyệt đối.

## 11. Hướng dẫn mở rộng module

Thêm một dạng RAW phải sửa **metadata schema + payload validator + writer/reader + test invalid/roundtrip**, không chỉ thêm phần mở rộng file. Thay numbered layout phải kiểm `storage/numbered_schema.py` (FK, immutable trigger), resolver và toàn bộ migration rollback, tránh rename folder trực tiếp. Khi thay transaction SQLite, kiểm nguồn sự thật `MetadataStore` và trạng thái pending reservation; không sửa UI để thao tác thẳng SQL.

## 12. Kiểm thử, bằng chứng và SKIP

| Bộ | Đường dẫn hiện hành | Phạm vi |
|---|---|---|
| RAW v2 | `tests/unit/raw/test_raw_rgbd_contract.py`, `tests/unit/raw/test_raw_storage.py` | validation, checksum/manifest |
| Numbered | `tests/integration/storage/test_gd1_07_2_numbered_storage.py` | cấp mã/đường dẫn/FK |
| History/migration | `tests/integration/storage/test_gd1_07_6_history.py`, `test_gd1_07_7_legacy_migration.py` | lịch sử, copy-first/rollback |
| Integrated | `tests/integration/storage/test_gd1_07_8_integrated.py` | project + capture + metadata |
| GĐ0 | `tests/integration/metadata/test_pre06_gd0_acceptance.py` | nhiều contract nối nhau |

`Full`/`Acceptance` dùng `scripts/verify.ps1`; SKIP quyền symlink do Windows được ghi đúng test ID theo R8.3 nhưng chưa chứng minh nhánh symlink được kiểm thử. Kết quả R8 tự động không biến durability/metric thành PASS.

## 13. Quyết định và giới hạn còn mở

ADR-002 là quyết định thiết kế **theo thời điểm ban hành**; mã numbered đã có qua các phiên 07.2–07.8, nhưng không sửa hồi tố bản ADR để gọi trạng thái ban đầu là DONE. Các nghiệp vụ sâu trong legacy migration có hợp đồng tại `docs/archive/GD1/07/07_01_STORAGE_LAYOUT_V2_CONTRACT.md`; phần cốt lõi cần để hiểu/duy trì đã được tóm và giải thích ở đây. **Chưa có** bằng chứng đo lỗi mất điện thực địa hoặc giao dịch nguyên tử file+DB.
