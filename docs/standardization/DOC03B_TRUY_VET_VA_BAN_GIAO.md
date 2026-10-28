# DOC-03B — Biên bản biên soạn và truy vết 5 module kỹ thuật

> **Mốc đối chiếu source:** `feat/gd1-desktop-ui@0557c0d4fed9a3df3b180fc9872c6d3293b5f0d5` (DOC-03A đã commit). **Ngày:** 2026-10-28. **Phạm vi:** tài liệu kỹ thuật; không sửa phần mềm, dữ liệu RAW/SQLite, test cũ hoặc hồ sơ lịch sử. **Trạng thái nghiệm thu:** IMPLEMENTED / WINDOWS FULL REGRESSION PENDING.

## 1. Sản phẩm và thứ tự đọc

Bắt đầu bằng [cổng tài liệu](../README.md), sau đó chọn một trong năm bộ mô tả trực tiếp đầy đủ 13 mục:

| Module | Nguồn R7 nội dung được kế thừa | Nguồn code đối chiếu | Điều kiện cần phân biệt |
|---|---|---|---|
| [Thu nhận RGB-D](../03-modules/RGBD_ACQUISITION.md) | `docs/modules/THU_NHAN_RGBD.md`, PRE-02 RAW contract | `acquisition/`, `domain/raw_rgbd.py`, `cpp/acquisition` | RAW MJPEG/Y16 độc lập, SDK opt-in, `measured` ≠ metric |
| [RAW Storage](../03-modules/RAW_STORAGE.md) | `LUU_TRU_RAW.md`, PRE-02/03, 07.01 Storage v2 | `storage/session_store.py`, `numbered.py`, `legacy_migration.py` | marker/checksum, SQLite reservation, crash recovery |
| [Project Workspace](../03-modules/PROJECT_WORKSPACE.md) | `QUAN_LY_DU_AN.md`, 07.11–07.12, ADR-002 | `modules/project_workspace/`, `metadata/` | UI chọn kho không tự tạo DB; CLI `MetadataStore` có khả năng tạo DB |
| [Desktop UI](../03-modules/DESKTOP_UI.md) | `GIAO_DIEN_DESKTOP.md`, các thử R1–R3.5 | `ui/shell/`, `ui/components/`, `application/contracts` | Qt GUI thread, lifecycle, offscreen ≠ HMI thật |
| [Viewer 3D](../03-modules/VIEWER_3D.md) | `KIEM_TRA_3D.md`, R4.3–R5.3 | `modules/viewer3d/`, `viewer_bootstrap.py` | scene/frame revision, SHA, copy→ACK, pick point/face |

**Bản cũ vẫn tồn tại** trong `docs/modules/` và archive. DOC-05 mới xử lý chuyển hướng/đường dẫn tương thích sau khi các bộ kiểm thử cập nhật đúng. DOC-03B không đổi bản gốc ADR/biên bản HMI hay nội dung các kết quả FAIL/SKIP lịch sử.

## 2. Đối chiếu từng nguồn kỹ thuật quan trọng

| Hợp đồng | Trang mới | Source xác minh | Mốc lịch sử (không là nguồn hiện trạng) |
|---|---|---|---|
| RawRgbdCaptureMetadataV2 / MJPEG Y16 / m-unit, mm | RGB-D, RAW | `domain/raw_rgbd.py`, `acquisition/raw_rgbd.py` | PRE-02/PRE-04 |
| SDK native lazy load và `capture_one_raw()` | RGB-D | `acquisition/native.py`, `orbbec_adapter.py` | PRE-06 |
| `commit_raw` / `read_raw`, manifest/COMMITTED | RAW | `storage/session_store.py` | PRE-03 |
| Numbered P/S/T/C/R + SQLite v1/v2 / migration | RAW, Project | `storage/numbered.py`, `numbered_schema.py`, `legacy_migration.py` | 07.01, ADR-002 |
| Project tree + commands/queries/inspections | Project | `project_workspace/application/` và `metadata/store.py` | GĐ1 07 |
| Qt shell và controller ownership | Desktop | `ui/main.py`, `ui/shell/main_window.py` | GĐ1 06–R3 |
| Viewer isolated host/IPC, RGB ACK | Viewer, Desktop | `resident_poc/{async_session,client,host,protocol}.py` | R4.3/R4.5 |
| SceneSource/Descriptor/SelectionRef và source SHA | Viewer | `viewer3d/application/scene_contracts.py` | R5.1 |
| Qt live/fallback, point/face inspector | Viewer | `live_controller.py`, `interactive_controller.py` | R5.2/R5.3 |
| Three Windows symlink SKIPs, HMI pending | toàn bộ module phù hợp | R8.3 skip policy, R8.4 runner | R6 history; chưa có physical PASS mới |

## 3. Giới hạn các kết luận

- Bộ module mô tả **source hiện hành đã kiểm**, không phải bản báo cáo thử camera/GPU mới. Các số liệu GĐ0/GĐ1 chỉ được nhắc là hồ sơ lịch sử theo operator; không phát sinh evidence mới.
- Không nâng cấp `R6_OVERALL_PENDING`, không đánh dấu HMI 08.06.6 PASS. `scripts/verify.ps1 -Profile Full` là cổng tự động; Acceptance phải có bằng chứng vật lý riêng.
- Cấu hình cơ khí/camera ngoài `RawRgbdCaptureMetadataV2` cần quyết định dự án hiện hành theo hardware baseline riêng. Việc nguồn PRE-02 ghi camera pose unknown không định nghĩa tư thế máy quét tương lai.
- Ví dụ làm việc với data root chỉ dùng **kho thử đã kiểm tra**; đặc biệt CLI `MetadataStore` có thể khởi tạo SQLite trên root trống; không chạy trên RAW thật như cách thử tài liệu.
- Không hứa dữ liệu nguồn file PLY/OBJ có chuẩn mét; Viewer giữ `units=unknown` và `coordinate_frame=unknown`.

## 4. Cổng bàn giao

`python -X utf8 scripts/check_doc03b_content.py --project-root <repo> --out-dir <evidence-outside-repo>` kiểm toàn bộ 5 module, đường dẫn Markdown, danh sách source/test, 13 mục, DOC-02 mapping. Sau đó chạy pytest tập trung `tests/contracts/tai_lieu/test_doc03b_content.py` và `scripts/verify.ps1 -Profile Full` trên Windows. Cổng nội dung không chứng nhận độ dễ hiểu tuyệt đối; operator cần đọc mẫu một luồng tốt/lỗi ở từng module trước khi duyệt.

**Không thực hiện trong DOC-03B:** sửa `docs/modules/*` R7, xóa alias, đổi `src/`, `cpp/`, `pyproject.toml`, dọn R4/R5 archives, chỉnh docs/acceptance hoặc cập nhật Task Register của DOC-04.
