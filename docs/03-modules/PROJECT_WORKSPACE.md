# Project Workspace — Quản lý dự án, vật mẫu và dữ liệu quét

> **owner:** `modules/project_workspace` · **as_of_commit:** `0557c0d4fed9a3df3b180fc9872c6d3293b5f0d5` · **verified_at:** 2026-10-28  
> **scope:** metadata/SQLite, Project/Specimen/ScanSession/Capture/ProcessingRun, thao tác UI và kiểm RAW · **implementation:** IMPLEMENTED trong GĐ1, HMI cuối PENDING · **source-of-truth:** `src/scantopath/modules/project_workspace/`, `src/scantopath/metadata/`, `src/scantopath/storage/` và các test.  
> **evidence:** đối chiếu Git + hồi quy R8 theo lịch sử; **manual verification:** NOT_TESTED mới trong DOC-03B.

## 1. Mục đích và tình huống sử dụng

Project Workspace trả lời: *vật mẫu này thuộc dự án nào, đã có những phiên thu nhận nào, dữ liệu RAW ở đâu và có thể kiểm chứng lại nguồn gốc không?* Người dùng chọn một kho đã tồn tại, xem cây dữ liệu, thêm/sửa metadata bằng form, đóng phiên quét, kiểm tra Capture và xem lịch sử tác vụ. Đây là quản lý **quan hệ và dấu vết**; việc tạo một `ProcessingRun` không có nghĩa các thuật toán đã tự được chạy.

Ví dụ: sau khi có một Capture thực đã commit, operator có thể mở Project, chọn Capture và yêu cầu kiểm checksum mà không làm biến đổi file gốc. Một file PLY ngoài được Viewer mở **không** trở thành Capture hoặc `ProcessingRun` của Project nếu chưa có quy trình đăng ký được thiết kế riêng.

## 2. Chức năng hiện hành và giới hạn

| Khả năng | Trạng thái/nguồn | Giới hạn |
|---|---|---|
| Project, Specimen, ScanSession, Capture, ProcessingRun | SQLite schema và API có trong `MetadataStore` | dữ liệu pixel không nằm trong SQLite |
| Chọn kho, tải cây, recent store, Inspector | Controller/Qt workflow đã có | không tự mở kho khi khởi động shell |
| Tạo/sửa Project/Specimen/Session, đóng Session | `ProjectWorkspaceService` + command/form | chỉ với kho hợp lệ/schema hỗ trợ |
| Cấp mã P/S/T/C/R | `NumberedStorageRegistry` schema v2 | không tự migrate schema cũ |
| Xác minh Capture RAW | `CaptureInspection` và SessionStore | chỉ xác minh toàn vẹn byte/hợp đồng, không xác minh chất lượng phép đo |
| Xử lý ảnh → point cloud → mesh/Zigzag | **Chưa tích hợp pipeline** | `ProcessingRun` không phải bộ xử lý geometry |

## 3. Thành phần và ranh giới mã nguồn

```text
QMainWindow / ProjectExplorer / Inspector
    ↔ ProjectWorkspaceController (QObject, signals, view lifecycle)
       ├─ _ProjectReadCoordinator → ProjectLoadController
       ├─ _ProjectWriteCoordinator → ProjectWriteController
       └─ _CaptureReviewCoordinator → CaptureInspectionController
                   │
       ProjectWorkspaceService (commands / queries / inspection)
                   │
       sqlite_backend.probe_existing + MetadataStore
       + NumberedStorageRegistry + SessionStore (khi verify RAW)
                   │
           metadata.sqlite3  +  RAW files
```

| Đường dẫn | Trách nhiệm |
|---|---|
| `modules/project_workspace/presentation/controller.py` | lớp điều phối Qt, giữ tương thích call-site cũ |
| `presentation/workflows/{reading,writing,capture}.py` | 3 chuỗi tín hiệu/tác vụ độc lập |
| `presentation/{dashboard,edit_dialog,processing_workspace}.py` | bố cục/biểu mẫu, trạng thái hiển thị |
| `application/service.py` | façade `ProjectWorkspaceService` không phụ thuộc QWidget |
| `application/{commands,queries,inspection,models,errors}.py` | xử lý nghiệp vụ, điều kiện hợp lệ, DTO/lỗi |
| `infrastructure/sqlite_backend.py` | kiểm tra kho đã có, path an toàn, factory adapter |
| `metadata/{store,schema,repos/}.py` | truy vấn và giao dịch entity/audit |
| `storage/numbered.py` | code public P/S/T/C/R và bảo toàn mapping |

Dùng `src/scantopath/` ở trước các đường dẫn `modules/`, `metadata/`, `storage/` trong bảng. Presentation **không** đọc SQLAlchemy trực tiếp trong sự kiện bấm nút.

## 4. Hợp đồng dữ liệu

Quan hệ logical:

```text
Project (project_id)
 └─ Specimen (specimen_id, project_id)
      └─ ScanSession (session_id, specimen_id, state=open|closed)
           ├─ Capture (capture_id, session_id, relative_path, schema_version, measured)
           └─ ProcessingRun (run_id, session_id, stage, algorithm, version, state, inputs)
AuditEvent (action, entity_type, entity_id, details)
```

| Dữ liệu | Kiểu/đơn vị | Quy tắc |
|---|---|---|
| `project_id`, `specimen_id`, ... | ASCII ID, khóa ngoại | immutable internal identity; không thay bằng P0001/S0001 |
| `name`, `label`, `description` | Unicode text | validation tại domain/service; không dùng tên để làm ID filesystem |
| `ScanSession.state` | `open` / `closed` | đóng phiên khác với đóng ứng dụng Qt |
| `Capture.schema_version` | 1 / 2 | phân biệt RAW packet contract; không là SQLite schema |
| `Capture.relative_path` | đường dẫn dưới data root | reader/registry phải kiểm giới hạn root |
| `Capture.measured` | boolean provenance | đo từ sensor ≠ kiểm định metric |
| `ProcessingRun.state` | pending, running, succeeded, failed | phản ánh metadata trạng thái; không tự chứng minh thuật toán chạy |
| public code P/S/T/C/R | alias có scope theo parent | tùy schema v2/numbering đã cấp |
| `AuditEvent.details` | JSON | không được ghi serial/secret/RAW payload không cần thiết |

**SQLite schema v1/v2 là độc lập với RAW schema v1/v2 và numbered layout.** `MetadataStore` có thể tạo DB mới khi khởi tạo trên root trống theo API; **UI workflow chọn kho** dùng `probe_existing` để tránh tạo/migrate khi chỉ mở kiểm tra.

## 5. Luồng thực thi bình thường

1. Desktop khởi động mà chưa mở SQLite. Người dùng chọn **thư mục kho có `metadata.sqlite3`**; `_ProjectReadCoordinator` gọi `ProjectLoadController` để nạp không chặn GUI.
2. `sqlite_backend.probe_existing()` kiểm path, không cho symlink/junction, yêu cầu DB tồn tại và `PRAGMA user_version` được hỗ trợ. `ProjectWorkspaceService` lắp assembler cho metadata/numbered (chỉ với schema v2).
3. Dịch vụ Query đọc danh sách Project/tree, Mapper chuyển thành DTO; UI hiển thị Explorer và bảng Thuộc tính. Chuyển lựa chọn không tự ghi database.
4. Khi người dùng bấm tạo/sửa: `_ProjectWriteCoordinator` mở `ProjectEditDialog`, xác thực `ProjectEditCommand`, gửi sang `ProjectCommands`. Tạo entity/quan hệ trong SQLite theo service; nếu cấp mã không thành công sau commit, báo `NumberingPendingError` để phục hồi tường minh, **không** coi SQL record đã bị mất.
5. Sau thao tác ghi thành công, controller cập nhật/hồi tải cây và trạng thái. Lỗi được đưa về signals/UI; không thao tác cập nhật widget từ worker nền tùy tiện.
6. Khi chọn Capture → Verify, `_CaptureReviewCoordinator` dùng `CaptureInspectionController` đọc/kiểm integrity, rồi mới ghi kết quả vào Inspector; không ghi lại RAW.

## 6. Bất biến và biên kiến trúc

- **User action mới mở kho**: import Python hoặc constructor QMainWindow không tạo Project/SQLite.
- Ghi thông qua service/commands, đọc thông qua queries; không chạy SQL trong QLabel, slot Qt hoặc Viewer.
- Không nâng schema v1 lên v2 khi chỉ mở; migration có bước backup và chấp thuận riêng.
- Internal UUID/ID là nguồn quan hệ; public code đánh số chỉ là alias có scope.
- Không coi `ProcessingRun` là pipeline geometry thật chỉ vì bản ghi `succeeded`.
- SQLite lưu metadata/đường tương đối, RAW giữ tại filesystem; xác minh hash chỉ khi yêu cầu.
- Các exception về numbering/đường dẫn không được che bằng dữ liệu giả để UI có vẻ bình thường.

## 7. Vòng đời, trạng thái và hủy tác vụ

```text
NO_STORE --choose existing root--> LOADING --success--> READY
                                \--error--> ERROR (old invalid view cleared)
READY --write--> BUSY --success--> READY + refresh
             \--failed--> READY + error notice
READY --verify capture--> BUSY --complete/fail--> READY + result
READY --close window--> stop coordinators/workers → Qt close
```

Có ba coordinator độc lập để giảm xung đột read/write/capture inspect. Cờ `_project_closing` và tín hiệu `stopped` giúp không đưa kết quả tới Qt widget đã bị hủy. Các thao tác dài không được thực hiện đồng bộ trong main thread. Việc xóa/thay đổi root giữa hai tác vụ cần tránh trường hợp kết quả cũ được trình như trạng thái kho mới.

## 8. Lỗi và phục hồi

| Tình huống | Cơ chế từ chối | Phản hồi/khôi phục | Nguồn test |
|---|---|---|---|
| Không có thư mục/`metadata.sqlite3` | `StoreNotOpenError` từ `probe_existing` | yêu cầu chọn kho thực, không tự tạo | `tests/integration/project/test_gd1_07_3_project_services.py` |
| SQLite version không hỗ trợ | `RuntimeError`/validation | backup, migration ngoài luồng mở kho | `tests/integration/storage/test_gd1_07_2_numbered_storage.py` |
| session không thuộc specimen | `LookupError` hoặc command validation | giữ nguyên dữ liệu, chỉnh lựa chọn | project services tests |
| code chưa cấp xong sau SQL commit | `NumberingPendingError` | thao tác `assign_code()` có chủ ý, không xóa entity | `tests/integration/storage/test_gd1_07_8_integrated.py` |
| RAW đã được đăng ký nhưng checksum sai | `CaptureIntegrityChecker` fail | thông báo capture hỏng, không sửa bản gốc | project/RAW integration |
| đang ghi mà đóng cửa sổ | shutdown coordinator theo lifecycle | chờ kết thúc/cancel qua flow được định nghĩa; không tắt cưỡng bức DB tùy tiện | tests UI 07.12/R3.5 |
| public path escaped/symlink | resolver từ chối | sửa cấu trúc kho/test bằng bản sao | symlink SKIP trên một số Windows |

## 9. Ví dụ tái lập an toàn

**Tại root repo, `.venv` có pytest.** Chạy trên `tmp_path` của test, không mở kho thực:

```powershell
& .\.venv\Scripts\python.exe -X utf8 -m pytest -q `
  tests/integration/project/test_gd1_07_3_project_services.py `
  tests/ui/project/test_gd1_07_8_qt.py `
  tests/ui/project/test_gd1_r3_2_project_dashboard.py
```

Kiểm danh sách trong **kho đã chuẩn bị**, không tự migrate/ghi nếu chỉ xem:

```powershell
& .\.venv\Scripts\python.exe -X utf8 -m scantopath.metadata.cli `
  --root '<EXISTING_DATA_ROOT>' list-projects
```

**Giới hạn quan trọng:** CLI này gọi `MetadataStore(args.root)` và có thể **tạo SQLite nếu root trống**, vì vậy chỉ được chạy với thư mục đã xác minh có `metadata.sqlite3`, không dùng nó để kiểm tra xem một kho có tồn tại hay không. Có thể xem `python -m scantopath.metadata.cli --help` mà không chạm kho. Không dùng `create_project` trên dữ liệu người dùng để “thử tài liệu”.

## 10. Hiệu năng và mức chứng minh

SQLite và mã Project được hồi quy trên fixture/Windows trong GĐ1; chưa có báo cáo riêng về hàng triệu Capture, contention nhiều writer hoặc benchmark UI khi dùng kho cỡ lớn. `QTimer`/worker giúp tránh block GUI ở các luồng được triển khai, nhưng không thay thế HMI đo thao tác thực trên các DPI và latency. Không gọi một ảnh màn hình dashboard là kiểm định tính toàn vẹn RAW.

## 11. Mở rộng mô-đun

Thêm entity/field: cập nhật schema, models, repos, commands/queries, mapper, form và integration tests. Thay số lượng/cấp mã: update `numbered_schema` và migration; không renumber bằng Explorer. Thêm hành động xử lý Geometry: thiết kế worker và provenance của ProcessingRun trước, không đặt ICP/meshing trong Qt controller. Nếu thay public façade, kiểm các alias tương thích từ 07.11/07.12 và guard R8.

## 12. Test và phép thử thủ công

| Nhóm | Kiểm thử hiện hành |
|---|---|
| SQLite nền | `tests/integration/metadata/test_pre05_metadata_store.py` |
| Project/service | `tests/integration/project/test_gd1_07_3_project_services.py` |
| numbering/migration | `tests/integration/storage/test_gd1_07_2_numbered_storage.py`, `test_gd1_07_7_legacy_migration.py` |
| UI Project | `tests/ui/project/test_gd1_07_4_qt.py`, `test_gd1_07_8_qt.py`, `test_gd1_r3_5_integrated_ux.py` |
| hợp đồng kiến trúc | `tests/contracts/kien_truc/test_gd1_07_11_clean_architecture.py` |

Cổng tổng `scripts/verify.ps1 -Profile Full` bao gồm pytest/JUnit/CTest, còn `Acceptance` **không** tự chứng nhận Project HMI thực, corruption recovery hoặc dữ liệu sensor chính xác. Các giới hạn này phải được ghi ở hồ sơ nghiệm thu.

## 13. Quyết định và tồn đọng

Đường lưu trữ đánh số được quyết định ở ADR-002 và **được hiện thực từng phần theo các phiên 07**, nhưng bản ADR gốc vẫn phản ánh trạng thái tại ngày ký. UI không được tự biến `NOT_IMPLEMENTED` thành fake `succeeded`. Cần thêm nghiệm thu trên dữ liệu/GUI thực, xử lý đóng khi worker bận và kế hoạch GĐ2 cho pipeline dẫn xuất. Trang này giải thích đủ quyền sở hữu và luồng hiện hành; hồ sơ archive chỉ phục vụ truy vết lịch sử.
