# DOC-05 — Biên bản di chuyển lịch sử và bàn giao Documentation Baseline v2

> `owner: DOCUMENTATION_OWNER` · `as_of_commit: 8bf5e1e1603a0acf735ffc55f0b3d11ef9d96286` · `verified_at: 2026-10-28`  
> `scope: DOC-05 documentation-only migration` · `source-of-truth: DOC02_BAN_DO_65.csv, DOC05_MIGRATION_PLAN.json, source Git` · `evidence_level: SOURCE_REVIEWED / WINDOWS_VERIFY_PENDING`

## 1. Kết quả cấu trúc và chính sách không phá tương thích

28 tệp lịch sử được lập kế hoạch sao chép sang `docs/99-lich-su/` theo bản đồ DOC-02: 12 hồ sơ `ARCHIVE`, 2 ADR, 3 nhật ký và 1 hồ sơ nguồn cũ, cùng 10 tệp R7/R8 gồm CSV. Mỗi hàng có Git blob nguồn; bản sao Markdown chỉ chuẩn hóa **đường dẫn liên kết tương đối** (đích vẫn là tệp mà liên kết cũ trỏ tới) để có thể đọc tại vị trí mới. File nguồn không sửa. Hai nguồn `docs/archive/README.md`, `docs/history/README.md` có chung đích `99-lich-su/README.md` nên được tổng hợp thành một chỉ mục mới thay vì đè lên nhau. `DOC-053` là alias của `DOC-026` cho cùng roadmap lịch sử.

Giữ 7 alias của DOC-02: `docs/INDEX.md`, `docs/architecture/CURRENT_GD1_ARCHITECTURE.md`, `docs/development/ENGINEERING_STANDARDS.md`, `docs/development/R7_DOCUMENTATION_POLICY.md`, `docs/modules/PROJECT_WORKSPACE.md`, `docs/modules/VIEWER3D.md`, `docs/roadmap/ROADMAP_V1_ARCHIVED.md`. Chúng vẫn được R7, DOC-03B/C, DOC-04 và đường dẫn permalink dùng; **0 xóa tự động**. Các file `docs/acceptance/`, `docs/development/`, `docs/standardization/` và `docs/history/` cũ không bị xóa bởi gói này.

## 2. Kiểm tra an toàn và tính đầy đủ

- HEAD đầu vào chính xác `8bf5e1e1603a0acf735ffc55f0b3d11ef9d96286`, nhánh `feat/gd1-desktop-ui` và worktree sạch; nguồn Git blob phải đúng 28/28.
- Chương trình chỉ đọc nguồn, không mở camera/SQLite/RAW, không sửa source ứng dụng hoặc test nghiệp vụ.
- R7 Docs Gate được mở rộng bằng các mục v2, nhưng **giữ nguyên đường dẫn v1** vì `README.md`/test cũ vẫn tham chiếu; test R7/R8 phải chạy thật, không đổi ngưỡng hay SKIP.
- `check_doc05_migration.py` đối chiếu 28 source/destination, 7 alias, link trong các chỉ mục, trạng thái pending, dấu vết nội dung và schema kế hoạch.
- Full Windows `scripts/verify.ps1 -Profile Full`: 10 gate R7/R8 + pytest, JUnit policy và CTest Release; cần receipt `SUMMARY.json` xuất **ngoài repo**.
- Review operator: mở tài liệu 99, đi tới ADR-002, nhật ký FAIL R6, R8.5, nghiệm thu GĐ1, quay về nguồn gốc. Nếu link nguồn lịch sử đã hỏng từ trước thì ghi tồn đọng, không báo giả đã sửa.

## 3. Di chuyển chưa đồng nghĩa nghiệm thu GĐ1

`DOC05_PACK_PREPARED` khi tạo gói: không phải `WINDOWS_FULL_PASS`. HMI DPI 100/125/150, native busy close, real fault injection, GPU/VRAM và input-to-physical-present vẫn cần quyết định tại `08.06.6`. Waiver 08.06.5 không tự áp lên các phép thử mới. `R6_OVERALL_PENDING` và `GD1_OVERALL_PENDING` được giữ trong status/acceptance.

## 4. Rollback và bàn giao

`apply.ps1` sao lưu mọi file hiện có mà nó sửa, ghi trạng thái và hash vào `_setup` bên ngoài Git. `verify.ps1` yêu cầu nội dung không bị chỉnh tay, kiểm source và chạy Full. `rollback.ps1` chỉ hoàn nguyên khi HEAD chưa commit, không có stage ngoài scope và mọi file còn đúng hash áp dụng; tránh `git reset --hard` và không xóa lịch sử gốc. Sau khi verify PASS, reviewer duyệt, commit/push phạm vi DOC-05; bản sao history được coi là **canonical view có provenance**, còn nguồn gốc vẫn là bản lưu tương thích.

**Giới hạn:** Không truy cập evidence gốc Windows hoặc khảo sát liên kết bên ngoài repository từ môi trường biên soạn; không tự chứng nhận hoàn tất việc loại bỏ alias/duplicate nếu chưa chứng minh được an toàn. Với chính sách này, DOC-05 khóa cách đọc v2 và provenance trước; việc xóa các alias sử dụng bởi gate cần thay đổi độc lập và nghiệm thu lại.
