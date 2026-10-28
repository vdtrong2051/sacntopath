# DOC-02 — Bộ mẫu viết tài liệu và tiêu chí nghiệm thu nội dung

> **Tài liệu vận hành cho DOC-03/DOC-04.** Không phải nguồn mô tả hiện trạng ScanToPath; các đoạn `[CẦN BỔ SUNG]` là placeholder chỉ dành cho **bản nháp template**, tuyệt đối không chuyển nguyên chúng vào tài liệu chuẩn được nghiệm thu.

## 1. Quy tắc dùng mẫu

- Mỗi trang chuẩn có: `owner`, `as_of_commit`, `verified_at`, `scope`, `source-of-truth`, `evidence_level` và mục **Giới hạn đã biết**. Nếu không chứng minh được, ghi `CHƯA XÁC MINH`, không tự đưa ra kết luận.
- Viết tiếng Việt rõ ràng; tên module, API, class, tham số và error code giữ nguyên như code thực. Giải thích thuật ngữ tại lần xuất hiện đầu. Sơ đồ có mũi tên hướng dữ liệu đúng, phân biệt Qt process và native child process.
- Mỗi ví dụ lệnh có working directory, môi trường, yêu cầu đầu vào, tác dụng phụ và kết quả mong đợi; **không** đưa lệnh camera thật/migrate SQLite vào “Quick start” mà thiếu cảnh báo.
- Đừng cắt/dán terminal log, báo cáo kết quả benchmark hoặc task list vào mọi module. Khi cần giải thích chọn giải pháp, đưa bối cảnh và hệ quả vào trang chính, link ADR để xem chứng cứ.
- Khi có số đo/số kiểm thử: ghi năm/ngày, commit, OS, thiết bị, điều kiện, loại bằng chứng; không ghi ngắn gọn “đã kiểm thử thành công” nếu thiếu phạm vi.

## 2. Mẫu README gốc — 8 phần bắt buộc

```markdown
# ScanToPath — [mô tả chính xác bài toán, không thổi phồng tính năng]
> Baseline source: <sha> | Last verified: <YYYY-MM-DD> | Project scope: <phạm vi>

## 1. ScanToPath làm gì và không làm gì?
[3–5 đoạn: vấn đề, đối tượng, đầu ra, giới hạn. Không đồng nhất Viewer với scan-to-path pipeline.]
## 2. Tình trạng năng lực hiện hành
[Bảng: capability | implementation | automated evidence | physical/manual evidence | limitation.]
## 3. Kiến trúc ở mức người mới
[Sơ đồ 1 khối: Qt / Python / native C++ / SQLite+RAW / isolated VTK host.]
## 4. Yêu cầu môi trường
[Windows, Python, CMake, SDK khi nào bắt buộc và khi nào không.]
## 5. Bắt đầu nhanh
[Lệnh chuẩn và output kỳ vọng; không dùng đường dẫn SDK cố định của một máy.]
## 6. Cấu trúc repository
[Bản đồ package cấp 1; trỏ rõ điểm vào code hiện tại.]
## 7. Chạy kiểm thử và phân biệt nghiệm thu
[Quick/Full/Acceptance, khi nào HMI còn NOT_TESTED.]
## 8. Cổng tài liệu
[Link trực tiếp docs/README; 3 tuyến: hiểu, phát triển, nghiệm thu.]
```

**Tự kiểm tra:** từ README người mới phải biết chạy ứng dụng, chưa có pipeline nào và không bị dẫn vào trang redirect trước nội dung cần đọc. Nếu status bảng không khớp `TRANG_THAI_DU_AN.md`, không nghiệm thu.

## 3. Mẫu MODULE — 13 mục, không bỏ vì “xem tài liệu khác”

```markdown
# <Tên module> — Hướng dẫn kỹ thuật hiện hành
> Owner: <module> | as_of_commit: <sha> | verified_at: <ngày>
> Status: IMPLEMENTED/PARTIAL/PLANNED | Evidence: <test/receipt link>

## 1. Mục đích và tình huống sử dụng
[Giải thích ngôn ngữ tự nhiên, ví dụ cụ thể, ai gọi.]
## 2. Phạm vi chạy được và chưa có
[Bảng capability và limitation; tránh nhầm R&D planned với implementation.]
## 3. Sơ đồ lớp và source thực tế
[Package/file/module, class, owner, quan hệ; không bịa API.]
## 4. Đầu vào/đầu ra và hợp đồng dữ liệu
[Bảng field | type | unit | frame | source | validation | ownership; ví dụ hợp lệ/lỗi.]
## 5. Luồng thực thi bình thường từ đầu tới cuối
[Thứ tự sự kiện, process/thread, nơi tạo object, nơi copy dữ liệu, nơi persist.]
## 6. Bất biến và các ranh giới không được vượt
[Điều kiện trước/sau, hash, revision, no implicit conversion; vì sao.]
## 7. Vòng đời, trạng thái và hủy tác vụ
[INIT/READY/BUSY/FAILED/CLOSING; race condition, timeout, retry, dispose.]
## 8. Lỗi, phục hồi và biểu hiện người dùng thấy
[Bảng trigger | error code | effect | recovery | test ID.]
## 9. Ví dụ an toàn có thể chạy lại
[Code/lệnh fixture, đầu ra dự kiến, cảnh báo IO/camera/migration.]
## 10. Hiệu năng, giới hạn phép đo
[Máy, số liệu có nguồn, chỉ số chưa đo, không suy diễn FPS/metric accuracy.]
## 11. Sửa ở đâu khi mở rộng module?
[Task → file/class → hợp đồng cần cập nhật → regression liên quan.]
## 12. Kiểm thử tự động và thủ công
[Đường dẫn tests R8.2+, runner, điều kiện PASS/SKIP/NOT_TESTED.]
## 13. Quyết định quan trọng và giới hạn còn mở
[Giải thích lựa chọn ngay trong file, nguồn ADR/incident, blocker theo ID.]
```

**Ví dụ mức sâu bắt buộc đối với VIEWER_3D:** nêu rõ luồng `PLY/OBJ → SceneDescriptor/source_sha → Qt controller → IPC → VTK Render Host → RGB shared memory → Qt copy → ACK` và luồng `click → scene_revision/frame_revision → point/cell picker → Inspector`. Giải thích vì sao không cho frame stale, vì sao cell intersection không là vertex CAD. Đây là ví dụ **hợp đồng cần giải thích**, không là tuyên bố kiểm thử HMI thật.

**Ví dụ mức sâu bắt buộc đối với RAW_STORAGE:** trình bày `color.mjpg`, `depth.y16`, `metadata.json`, `manifest.json`, `COMMITTED`, version độc lập, crash recovery, sai checksum, symlink, quan hệ SQLite và lý do không có atomic transaction xuyên filesystem/SQLite. Không thực thi thao tác trên RAW người dùng khi chỉ kiểm thử tài liệu.

**Điểm cho đạt:** tổng 13 mục đủ *nội dung thực*, không chấp nhận 13 tiêu đề trống; có ít nhất một luồng tốt, một luồng lỗi và một ví dụ an toàn, mọi file/code path đã đối chiếu tại `as_of_commit`.

## 4. Mẫu ARCHITECTURE — cấu trúc kỹ thuật chung

1. Bối cảnh bài toán và yêu cầu non-functional (UI responsive, RAW immutable, isolation).
2. Ranh giới: domain/application/infrastructure/presentation, sở hữu dependency.
3. Context diagram: camera, host Qt, metadata DB, files, render child process.
4. Package/component diagram và source map có đường dẫn thật.
5. Ba luồng hoạt động **đã có**: thu nhận RAW, quản lý Project, mở PLY/OBJ.
6. Contracts: units/frame/provenance, SHA-256, timeout, cancellation, IPC/shared memory.
7. Concurrency: Qt event-loop, Python worker, native process, async command ACK.
8. Lỗi/mất tiến trình: cleanup, stale frame, partial write, retry và degrade.
9. Kiến trúc chưa triển khai: đưa vào roadmap với nhãn `PLANNED`, không chen vào sơ đồ hiện trạng.
10. Quyết định A/B, sự đánh đổi và test/receipt tương ứng.

## 5. Mẫu hồ sơ GIAI ĐOẠN — không copy task

```text
Mã giai đoạn; mục tiêu đo được; phạm vi (IN/OUT); input từ giai đoạn trước;
Deliverables đã có; phụ thuộc quan trọng; quyết định chủ chốt; các task ID liên quan;
Tình trạng triển khai có nguồn; acceptance summary; exceptions/waivers có duyệt;
Bài học/bàn giao; điều kiện mở giai đoạn kế tiếp.
```

Mốc R7/R8 là tiến trình chuẩn hóa kiểm thử/tài liệu, không đồng nghĩa Feature stage. Chỉ có thể ghi DONE cho một giai đoạn khi gate của giai đoạn đó có bằng chứng, không dùng `git commit` làm bằng chứng duy nhất.

## 6. Mẫu TASK REGISTER — dữ liệu sống, một hàng một việc

| Field | Yêu cầu |
|---|---|
| `task_id` | Duy nhất, bất biến (ví dụ `DOC-03B-VIEWER`, `GD1-08-06-6`) |
| `parent_stage` / `workstream` | Giai đoạn/nhóm công việc; không đổi chỉ vì chuyển thư mục |
| `title` / `outcome` | Mô tả có thể nghiệm thu, không phải nhật ký terminal |
| `owner` | Người/phân hệ chịu trách nhiệm; không tự gán cá nhân |
| `priority` | P0/P1/P2 và lý do |
| `status` | `BACKLOG`, `READY`, `IN_PROGRESS`, `BLOCKED`, `IN_REVIEW`, `DONE`, `DEFERRED`, `CANCELLED` |
| `depends_on` | ID khác; không phải tên tài liệu tự do |
| `acceptance_criteria` | Điều kiện đo được, mức test cần chạy |
| `commit_or_pr` | SHA/PR chính xác; rỗng nếu chưa có |
| `evidence_uri` | Biên bản/evidence ngoài repo, không suy đoán path |
| `updated_at` / `updated_by` | Thời điểm, người thực hiện; phân biệt agent đề xuất và operator duyệt |
| `blocker` / `notes` | Phạm vi rủi ro, bước gỡ chặn |

**Chuyển trạng thái:** `DONE` yêu cầu gate thích hợp và người duyệt; `BLOCKED` yêu cầu blocker cụ thể; `DEFERRED/CANCELLED` yêu cầu lý do. Không đặt `PASS` cho task (PASS dành cho gate).

## 7. Mẫu STATE LEDGER — trạng thái hiện hành duy nhất

| Field | Yêu cầu |
|---|---|
| `capability_id` | Ví dụ `ACQ_GEMINI2`, `RAW_V2`, `PROJECT`, `VIEWER_R53`, `SCAN_PIPELINE`, `HMI_GD1` |
| `implementation` | `NOT_STARTED`, `PARTIAL`, `IMPLEMENTED`, `DEPRECATED` |
| `automated_verification` | `NOT_TESTED`, `PASS`, `FAIL`, `SKIP_WITH_REASON` + receipt |
| `physical_manual_verification` | `NOT_TESTED`, `PARTIAL_EVIDENCE`, `PASS`, `FAIL`, `WAIVED_WITH_APPROVAL` |
| `as_of_commit` / `verified_at` | Xác nhận code/date; không tự suy luận tính mới từ tên nhánh |
| `scope` / `limitation` | Cụ thể phần nào có hoặc chưa chứng minh |
| `source` | Git, log operator, image, run report, physical test |

**Không hợp lệ:** `VIEWER_IMPLEMENTED` dẫn tới tự động `HMI_MANUAL_PASS`; `measured` tự trở thành `metric_validated`; `bench_completed` tự thành FPS màn hình. Dữ liệu bảng chỉ là snapshot được đối chiếu tại ngày ghi.

## 8. Mẫu ADR và quyết định hiện hành

- ADR gốc chứa: ID, ngày, phạm vi, vấn đề, phương án, quyết định, trade-off, trạng thái tại ngày ký, ảnh hưởng, cách rollback.
- ADR hiện hành dùng index tách: `adr_id`, `original_path/sha`, `current_applicability` (`ACTIVE`, `PARTIALLY_APPLIED`, `SUPERSEDED`, `PENDING_VERIFICATION`), `evidence`, `superseding_adr`, `reviewed_at`.
- Nếu ADR-002 ghi “implementation pending” tại ngày soạn, không sửa hồi tố thành “done”. Cập nhật chỉ mục áp dụng, giải thích phần storage thực tế ở module hiện hành.

## 9. Mẫu ACCEPTANCE — không dùng câu “đã test” chung chung

| Field | Mô tả |
|---|---|
| `gate_id` | Tên cổng kiểm thử; `HMI_DPI_125`, `CPP_NATIVE_BUSY_CLOSE` ... |
| `expected` | Điều kiện đạt và phép đo được định nghĩa trước |
| `method` | CLI, JUnit, CTest, camera thật, manual DPI, fault injection ... |
| `environment` | Windows version, Qt/Python/MSVC, GPU, SDK, DPI nếu liên quan |
| `result` | PASS/FAIL/SKIP/NOT_TESTED/WAIVED; không gộp manual+auto |
| `evidence` | SHA/receipt/output gốc có thể mở lại, không bịa link |
| `executed_at` / `reviewer` | Ngày/giờ và người thực hiện/duyệt |
| `limitation` | Vì sao benchmark không chứng minh FPS hoặc metric accuracy |
| `next_action` | Cần thử thêm hoặc quyết định ngoại lệ |

Ba SKIP symlink trên Windows hợp lệ theo whitelist R8.3 nhưng **không** chứng minh đã chạy code từ chối symlink. `Acceptance` R8.4 tự động PASS vẫn có thể `overall=PENDING_MANUAL`.

## 10. Rubric nghiệm thu từng tài liệu

| Tiêu chí | Cách kiểm | Cổng |
|---|---|---|
| Tính xác thực | Source/API/test path hiện hành, claim có commit/receipt | HARD |
| Tự giải thích | Người mới hiểu flow chính, ví dụ, trường hợp lỗi, giới hạn | HARD |
| Đủ bất biến | Không mất CT-01..CT-16 liên quan | HARD |
| Đúng trạng thái | Implementation ≠ automated ≠ manual; có `verified_at` | HARD |
| Dễ thao tác | Lệnh thật với prerequisites, side effect, output | HARD |
| Giữ nguồn lịch sử | ADR/waiver/FAIL nguyên gốc; có trace | HARD |
| Markdown/link/encoding | UTF-8, link đúng, không có redirect vòng | AUTOMATED |
| Điều hướng | 2 click từ docs/README đến trang module chuẩn | REVIEW |
| Cập nhật | Owner và tác động thay đổi được ghi trong PR | REVIEW |

**Kết luận nghiệm thu:** một tài liệu không đạt nếu bất kỳ HARD gate nào FAIL. Điểm mỹ thuật hoặc số trang không bù được sai hợp đồng/nguồn. Trước khi đánh dấu DONE ở Task Register phải có `reviewer_or_operator` và đối chiếu test/evidence tương ứng.
