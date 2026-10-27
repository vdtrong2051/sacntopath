# GĐ1 — 06.2: DTO, Application Services và Navigation ViewModel

**Source baseline:** `feat/gd1-desktop-ui`, commit `299819209d96c6b732bf62485e2e20e408b1f442` (đã có 06.1).
**Phạm vi:** xây dựng mã Python thuần + kiểm thử, **không thay đổi giao diện Qt đang chạy**.
**Trạng thái:** bản vá 06.2; kiểm thử Windows, commit/push được xác nhận sau khi operator thực hiện.

## Các tệp mới

```text
src/scantopath/application/__init__.py
src/scantopath/application/contracts/__init__.py
src/scantopath/application/contracts/models.py
src/scantopath/application/services.py
src/scantopath/ui/viewmodels/__init__.py
src/scantopath/ui/viewmodels/navigation.py
tests/test_gd1_06_2_contracts.py
docs/gd1/06_2_APPLICATION_CONTRACTS.md
```

## Hợp đồng đã thực thi

| Loại | Định nghĩa | Ý nghĩa |
|---|---|---|
| `WorkspaceId` | projects, capture, inspect3d, processing | Chính xác 4 workspace theo 06.1 |
| `UiDataState` | not_implemented, fixture, measured, estimated, validated, insufficient_evidence | Không đánh đồng đo với kiểm chứng |
| `SourceContext` | data_state, source_ids, frame_id?, units? | Không tự sinh tọa độ, tư thế camera, đơn vị |
| `CommandRequest` | request_id, command, parameters, source_context | Snapshot JSON bất biến ở mức cấu trúc |
| `CommandOutcome` | request_id, status, value?, error_code?, message? | Succeeded/failed/cancelled/not_implemented, không trả kết quả giả |
| `SelectionRef` | entity_type, entity_id, source_id? | Chỉ là tham chiếu ID, không load SQLite |
| `TaskSnapshot` | task_id, title, state, progress?, can_cancel, error? | Hợp đồng cho worker 06.5; chưa có task execution |
| `NavigationService` | current(), select() | Service đồng bộ thuần Python, revision idempotent |
| `CommandService` | execute() | Whitelist `workspace.current/select` và trả NOT_IMPLEMENTED cho tính năng chưa có |
| `NavigationViewModel` | select_workspace(), select_entity(), state | UI 06.3 dùng trực tiếp, không Qt dependency |

**Quan trọng:** `TaskSnapshot` là trạng thái tác vụ UI tương lai, **không** phải `ProcessingRun` SQLite GĐ0. Task executor + cancel thật thuộc 06.5; Project services gọi `MetadataStore` thật thuộc 07. Chưa tạo class mô phỏng truy xuất project, camera hoặc point cloud.

## Kiểm chứng

- Test thuần Python: import ngoài GUI, 4 workspace, revision, invalid command, NOT_IMPLEMENTED, JSON DTO immutability, outcome serialize, trạng thái cancel/failed, selection và ViewModel.
- `CommandService` chỉ nhận đúng command và parameters; không gán thành công cho command khác.
- Phải chạy toàn bộ pytest từ GĐ0 và native CTest, self-test trên Windows; 06.2 không phụ thuộc GUI, camera hoặc SQLite để unit-test mới.
- `python -m scantopath.ui.main` vẫn mở shell cũ; main.py không sửa tại 06.2.
- Không tạo nhánh con, không sửa C++, RAW, metadata, `pyproject.toml`, Qt shell.

### Tiêu chí chặn chuyển bước 06.3

1. New tests passed; full regression không failure (ngoại lệ Windows symlink skip có ghi nhận).
2. CTest 2/2 và native self-test exit 0.
3. `git diff --check` không lỗi; chỉ 8 tệp mới ở trên.
4. Commit và push trên nhánh hiện hữu `feat/gd1-desktop-ui`, **không merge main**.

**Bước tiếp theo (06.3):** dùng `NavigationViewModel` để dựng một `QMainWindow` + `QStackedWidget` 4 workspace, không copy logic điều hướng/validation vào QWidget.
