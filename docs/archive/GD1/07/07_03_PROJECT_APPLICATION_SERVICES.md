# GĐ1 / 07.3 — Project Application Services & DTO (thực thi)

**Nhánh chuẩn:** `feat/gd1-desktop-ui`; **commit nền:** `3a0558463244572ea4686c501039dd5d05adf302` (07.2 đã push).

**Phạm vi:** kết nối Application Service với `MetadataStore` và `NumberedStorageRegistry` đã triển khai. Không sửa `MetadataStore`, `SessionStore`, UI, RAW, SQLite schema hay QSS. Toàn bộ phương thức dưới đây là Python thuần, không import Qt/SDK. Mọi kết quả trả về là DTO bất biến; không trả SQLAlchemy Session.

## 1. Quy tắc mở kho và schema

`ProjectWorkspaceService(root)` chỉ được tạo khi người dùng **chủ động chọn một thư mục kho đã có**. Yêu cầu có `metadata.sqlite3`; nếu thiếu thì trả `StoreNotOpenError`, **không tạo database mới**. Đối với SQLite v1: đọc cây dữ liệu và RAW legacy, không tự migration, không tạo mới bằng service 07.3. Đối với SQLite v2: đọc/ghi metadata và cấp mã qua registry 07.2.

Bộ service chỉ kiểm tra cấu trúc, không tự cấp mã khi query. Dòng legacy hoặc chưa được cấp mã hiển thị `storage.public_code=None` + `state=unmapped/legacy_unmapped`. Khi cần đánh số các bản ghi đã tồn tại phải chủ động gọi `assign_existing_codes()`. Việc này chỉ ghi bảng mã, **không di chuyển RAW**. Không chạy `migrate --confirm` trên dữ liệu thật khi chưa duyệt backup và kiểm thử trên bản sao.

## 2. API và kết quả

| API | Hành động | Ghi vào DB? |
|---|---|---|
| `info` | Đọc `StoreInfo` gồm root/schema và chế độ có mã | Không |
| `list_projects()` | Danh sách `ProjectSummary` | Không |
| `get_project_tree(id)` | `ProjectTree` → `SpecimenNode` → `SessionSummary` → Capture / Run | Không |
| `get_capture(id, verify_raw=False)` | `CaptureSummary`, kiểm tra RAW nếu `True` | Không |
| `get_processing_run(id)` | Run metadata; đường dẫn output chỉ là tham chiếu | Không |
| `list_events(limit=100)` | Audit log bền vững có `details_json` | Không |
| `assign_code(kind,id)` | Cấp lại mã cho bản ghi đã tồn tại | Có, v2 |
| `assign_existing_codes()` | Ánh xạ các bản ghi cũ theo quy tắc 07.2 | Có, v2 |
| `create_project(name,description,project_id=...)` | Ghi Project qua GĐ0, cấp mã P | Có, v2 |
| `update_project(id,...)` | Sửa tên/mô tả, không đổi mã P | Có, v2 |
| `create_specimen(project_id,label,...,specimen_id=...)` | Ghi Specimen, cấp mã S | Có, v2 |
| `update_specimen(project_id,specimen_id,...)` | Kiểm tra thuộc project trước khi sửa | Có, v2 |
| `create_session(specimen_id,label,...,session_id=...)` | Tạo ScanSession, cấp mã T | Có, v2 |
| `close_session(specimen_id,session_id)` | Kiểm tra quan hệ cha, chuyển closed | Có, v2 |

`CaptureSummary.schema_version` là **định dạng RAW**. `StorageRef.layout_version` là **bố cục thư mục**. `StoreInfo.schema_version` là **phiên bản SQLite**; không được trộn ba loại này. `CaptureSummary.data_state` dùng `MEASURED` cho sensor và `FIXTURE` cho dữ liệu synthetic. Nó không bao giờ tự đánh dấu metric `VALIDATED`. `storage.state=verified` chỉ cho biết kiểm tra file/manifest đã đạt, **không chứng nhận kích thước vật lý**.

**Lỗi tạo 2 bước:** GĐ0 `create_*` và 07.2 `assign` không phải một SQLite transaction xuyên qua hai API. Nếu metadata đã commit nhưng cấp code lỗi, `NumberingPendingError(entity_type,internal_id)` giữ lại ID; không gọi `create_*` lần nữa. Khôi phục bằng `assign_code(entity_type,internal_id)`. Không xóa metadata đã commit, không giả vờ rollback và không ngầm tạo mã ở bước đọc.

## 3. Cách gọi từ tầng ứng dụng (không phải code QWidget)

```python
from scantopath.application.projects import ProjectWorkspaceService

# Chỉ thực hiện khi người dùng chọn kho hợp lệ:
service = ProjectWorkspaceService(r"E:\Data\ScanToPath")
projects = service.list_projects()
if projects:
    tree = service.get_project_tree(projects[0].project_id)

# Tạo mới đòi hỏi SQLite schema v2 đã migrate chủ động:
if service.info.writable_with_codes:
    project = service.create_project("Mẫu thử kỹ thuật")
    print(project.storage.public_path)  # P0001, P0002, ...
```

Ở **07.4**, ProjectExplorer sẽ gọi các API này qua Presenter/Worker, không import SQLAlchemy, và cần các trạng thái đang tải/rỗng/lỗi. Ở **07.5**, forms sẽ gọi create/update. Ở **07.6**, lịch sử Capture/Run/Audit sẽ hiển thị chi tiết. Ở **07.7** mới xử lý di chuyển legacy RAW theo dry-run, backup và rollback.

## 4. Nghiệm thu và giới hạn

- `tests/test_gd1_07_3_project_services.py`: 22 tests, không cần PySide6, camera hay GPU; chạy với `tmp_path`, không truy cập `scantopath-data/` thật.
- Hồi quy PRE-02/03/05 và 07.2 trong môi trường độc lập: 122 passed gồm 21 bài 07.3 trước khi bổ sung bài numbered RAW v2; sau bổ sung phải chạy lại trên Windows.
- 07.3 **không** thêm UI widget, không sửa C++ hoặc camera; Qt integration, HMI và native tests vẫn bắt buộc trên Windows qua script verify.
- Nếu chưa migrate schema v2, UI có thể đọc dữ liệu legacy nhưng không được cho người dùng tưởng đã tạo thành công thư mục có mã; service sẽ từ chối ghi.
- **Không tự động migration**: `apply.ps1`, `verify.ps1`, `publish.ps1` chỉ sửa source/repo, không chạm dữ liệu RAW/SQLite thật.
