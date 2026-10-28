# Sổ tay phát triển, debug và quy trình Git/patch

> `owner: ENGINEERING_OWNER` · `as_of_commit: a847faebe54050cd6f8bc42cc882b3927ddabfe2` · `verified_at: 2026-10-28`  
> `scope: thay đổi có kiểm soát trong GĐ1 và chuyển sang GĐ2` · `source-of-truth: source tree; docs/02-kien-truc; docs/03-modules; scripts/verify.ps1` · `evidence_level: SOURCE_REVIEWED / WINDOWS_EXECUTION_NOT_TESTED`

## 1. Một yêu cầu code đi qua những cổng nào?

Trình tự vận hành: **xác định hợp đồng → tìm module owner → lập thay đổi nhỏ → thực thi trong nhánh → test phạm vi → Full regression → review bằng chứng → operator commit/push**. Một commit Git chỉ chứng minh đã lưu mã; nó không tự chứng minh kiểm thử HMI, GPU hay hardware. Nếu thay đổi hành vi làm sai test cũ, xác định hợp đồng nào thay đổi và lý do trước; **không sửa test chỉ để xanh**.

```text
Yêu cầu/bug + kết quả mong đợi
  → git HEAD, trạng thái repo, nhánh
  → source/API/test thực tế và bất biến
  → tác động Qt / Python / native / storage / SQLite
  → code + test + tài liệu chuẩn có cùng scope
  → Quick hoặc targeted gate (phản hồi nhanh)
  → Full + JUnit/CTest (cổng tự động)
  → HMI/native physical nếu cần (cổng độc lập)
  → kiểm phạm vi Git → commit/push do operator thực hiện
```

Với nhiệm vụ **chỉ viết docs**, không thay đổi `src/`, `cpp/`, source của các gate R7/R8, dữ liệu RAW/SQLite hoặc trạng thái nghiệm thu; script/test mới chỉ được thêm để kiểm tra chính các tài liệu mới. Di chuyển alias và archive dành cho DOC-05.

## 2. Định vị đúng source và trách nhiệm

| Sửa gì? | Điểm bắt đầu có thật tại baseline | Bất biến chính | Test khởi đầu |
|---|---|---|---|
| Layout/đóng cửa sổ, điều hướng workspace | `src/scantopath/ui/main.py`, `ui/shell/main_window.py`, `ui/workspaces/pages.py` | Qt event loop và lifecycle; offscreen ≠ HMI | `tests/ui/shell/`, `tests/contracts/shell/` |
| Project create/select/inspect | `src/scantopath/modules/project_workspace/{application,presentation,infrastructure}/` | UI không tự tạo/migrate SQLite ở root người dùng | `tests/integration/project/`, `tests/ui/project/` |
| RAW v2 save/read, commit, checksum | `src/scantopath/storage/session_store.py`, `src/scantopath/domain/raw_rgbd.py` | checksum, marker `COMMITTED`, provenance, idempotence | `tests/unit/raw/`, `tests/integration/storage/` |
| Thu nhận Gemini 2 | `src/scantopath/acquisition/`, `cpp/src/acquisition/`, `cpp/python/orbbec_bindings.cpp` | lazy load SDK, frame ownership, m/unit ≠ mm, không tự mở camera | `tests/contracts/camera/`, `cpp/tests/rgbd_packet_contract.cpp` |
| Mở PLY/OBJ, navigation, pick | `src/scantopath/modules/viewer3d/`, `ui/shell/viewer_bootstrap.py` | render host cách ly, scene/frame revision, shared memory copy rồi ACK | `tests/integration/viewer/`, `tests/ui/viewer/`, `tests/native/viewer/` |
| Task runner và cổng kiểm thử | `scripts/verify.ps1`, `scripts/r8_4_verify.py`, `scripts/r8_5_audit.py` | receipt/JUnit/CTest ngoài repo, SKIP policy không bị nới | `tests/contracts/quality/`, `tests/contracts/nghiem_thu/` |

Khi mở rộng chức năng, đọc trang module tương ứng trước rồi lần theo API thật; không tạo layer mới chỉ vì đường dẫn dài hoặc số dòng lớn. [Kiến trúc](../02-kien-truc/KIEN_TRUC_HE_THONG.md) ghi ranh giới, [từng module](../03-modules/VIEWER_3D.md) giải thích flow chi tiết. Nếu import giữa layer làm Qt/VTK vào domain, review kiến trúc trước khi code.

## 3. Walkthrough: sửa lỗi mở PLY trong Viewer

Tình huống giả định: mở tệp PLY ngoài bị lỗi hoặc ảnh preview cũ xuất hiện sau khi chuyển nguồn. Đây **là quy trình điều tra**, không khẳng định lỗi tồn tại ở HEAD này.

1. Tạo fixture PLY/OBJ tổng hợp trong thư mục tạm; ghi SHA-256, đặc tính header, số điểm/face, kích thước, đơn vị/hệ tọa độ `unknown`. Không sửa tệp gốc của người dùng.
2. Theo đường `ui/shell/viewer_bootstrap.py` → `modules/viewer3d/presentation/controller.py`/`live_controller.py` → `infrastructure/scene_reader.py`/`render_ply.py` → `infrastructure/resident_poc/{async_session,client,host,protocol}.py`.
3. Kiểm tại hợp đồng `application/scene_contracts.py` (`SceneSource`, `SceneDescriptor`, `SceneSelectionRef`): nguồn có SHA, lifecycle và revision tương ứng. Frame trở về Qt phải được **copy** khỏi shared memory trước khi gửi `ACK`; không chấp nhận frame `scene_revision` cũ khi thay source.
4. Phân loại lỗi trước khi sửa: file/format invalid, nguồn bị đổi sau hashing, IPC timeout/host chết, stale frame, Qt view đóng, selection invalid. Lỗi IPC/host không được che bằng giả lập frame PASS.
5. Cập nhật test đúng tầng: `tests/integration/viewer/test_gd1_08_03_ply.py`, `tests/ui/viewer/test_gd1_08_03_qt.py`, `tests/native/viewer/test_gd1_r5_1_scene_geometry.py`, và nếu sửa picking thì `tests/ui/viewer/test_gd1_r5_3_qt.py`. Không mở thiết bị/GPU thật trong test unit thuần.
6. Chạy targeted pytest, kiểm log, chạy Full. Nếu thay đổi HMI native/present, nghiệm thu thủ công DPI/GPU và thu receipt theo [kiểm thử](KIEM_THU_VA_NGHIEM_THU.md); không tự tuyên bố manual PASS.

Ví dụ targeted không ghi dữ liệu người dùng, chạy tại root bằng PowerShell đã có `$py`:

```powershell
Set-Location -LiteralPath $repo
$env:QT_QPA_PLATFORM = 'offscreen'
try {
  & $py -X utf8 -m pytest -q -rs `
    tests/integration/viewer/test_gd1_08_03_ply.py `
    tests/ui/viewer/test_gd1_08_03_qt.py
  if ($LASTEXITCODE -ne 0) { throw 'VIEWER_TARGETED_FAILED' }
} finally { Remove-Item Env:QT_QPA_PLATFORM -ErrorAction SilentlyContinue }
```

## 4. Walkthrough: thay đổi RAW hoặc Project

RAW không chỉ là ảnh: source hợp đồng `RawRgbdCaptureMetadataV2` mang kích thước, encoding MJPEG/Y16, timestamp chẩn đoán và provenance. `commit_raw`/`read_raw` đi qua manifest, checksum và `COMMITTED`; SQLite metadata và filesystem **không có một giao dịch atomic chung**. Khi sửa: kiểm crash/partial write, marker, symlink, replay và audit; xem [RAW Storage](../03-modules/RAW_STORAGE.md). Không thực hiện migration `numbered_cli migrate --confirm`, `legacy_migration_cli apply --confirm`, `metadata.cli` trên dữ liệu thật như một bài unit test.

Project đi qua `modules/project_workspace/application/commands.py`, `queries.py`, `service.py` rồi `infrastructure/sqlite_backend.py`/`metadata/`. Kiểm business rule ở application trước; UI chỉ gọi presenter/controller. Sự khác biệt quan trọng: thao tác UI **chọn root** không được mặc định tạo database; `MetadataStore` trên root trống **có thể khởi tạo SQLite**. Dùng `tmp_path`/fixture hỗ trợ trong `tests/support` thay root thật. Xem [Project Workspace](../03-modules/PROJECT_WORKSPACE.md).

## 5. Debug theo tầng thay vì sửa bừa

| Dấu hiệu | Điều tra | Không làm |
|---|---|---|
| Pytest đỏ | test ID, stacktrace, temporary dir, contract nguyên gốc; chạy lại test đơn lẻ | nới assertion, xóa test, đổi SKIP whitelist |
| Qt test PASS nhưng người dùng không thấy frame | Phân biệt `offscreen` với present thật; DPI, compositor, log Render Host | ghi HMI PASS chỉ từ pytest |
| Render Host đóng chậm/chết | timeout, cancellation, child process, copy→ACK, shared memory release | chạy VTK nặng trong GUI thread hoặc retry vô hạn |
| RAW/SQLite lệch | kiểm `COMMITTED`, checksum, schema version, receipt/backup trước khi sửa | sửa trực tiếp DB/RAW thật để tái hiện |
| CTest fail | cấu hình generator/Release, `ctest --output-on-failure`, exe thực tế | sửa `CTestTestfile.cmake` hoặc bỏ CTest khỏi Full |
| Crash native chỉ trên Windows | ghi MSVC, SDK, DLL path, parent/child exit code, debugger dump có kiểm soát | tự bật camera, ngầm nâng SDK/firmware |

Trình tự chứng cứ: thu log gốc → tái hiện bằng fixture → xác nhận phạm vi ảnh hưởng → fix có test → Quick → Full → manual khi cần → review. Không cam kết sửa lỗi mà chưa xác định root cause; chưa kiểm chứng ghi `NOT_TESTED`.

## 6. Git workflow, đặt tên commit và phạm vi stage

Dự án đang làm việc trên nhánh `feat/gd1-desktop-ui` theo baseline bàn giao; không suy ra nhánh `main` hoặc PR flow bắt buộc cho mọi contributor. Với patch DOC-03C, **operator** là người commit/push; các bước này không nằm trong `apply.ps1`:

```powershell
Set-Location -LiteralPath $repo
git branch --show-current
git log -1 --oneline
git status --short
# Sau apply+verify PASS, chỉ stage các file đã cho phép:
git add -A -- docs/04-phat-trien docs/README.md `
  docs/standardization/DOC03C_TRUY_VET_VA_BAN_GIAO.md `
  scripts/check_doc03c_content.py tests/contracts/tai_lieu/test_doc03c_content.py
git diff --cached --check
if ($LASTEXITCODE -ne 0) { throw 'GIT_STAGED_DIFF_INVALID' }
git diff --cached --stat
# Chỉ người vận hành tự quyết định commit sau khi đã xem diff và log Windows.
```

Commit gợi ý: `docs(doc03c): complete Windows development and verification handbook`. Sau commit mới `git push origin feat/gd1-desktop-ui` khi branch và policy cho phép. Không stage `_setup/`, `.venv/`, build binaries, JUnit hay dữ liệu người dùng; evidence phải ở `_setup` **ngoài** repo. `git diff --check`/`--cached --check` phát hiện whitespace; kiểm tra Git sạch trước áp patch, không dùng `git reset --hard` khi lỗi.

## 7. Quy trình ZIP có backup, verify, rollback

Gói từ ChatGPT tải về `E:\1_BigProject\scantopath\_setup\ScanToPath_DOC03C_Development_Handbook.zip`, giải nén ngoài workspace, chạy `apply.ps1 -ProjectRoot $repo`, rồi `verify.ps1 -ProjectRoot $repo -FullRegression`. `apply.ps1` chỉ ghi manifest file đã định danh, backup file hiện tại, kiểm SHA baseline; phải từ chối dirty worktree, nhánh/HEAD không khớp hoặc file bị thay đổi. `rollback.ps1` chỉ khôi phục file từ backup **nếu** hash working file vẫn là bản patch và HEAD chưa thay đổi; nếu đã commit hoặc chỉnh tay thì dừng, không ghi đè công sức mới. Backup không thay việc commit có review.

**Lưu ý:** các lệnh trong sổ tay là ví dụ; dùng `README_APPLY.md` và các script **bên trong đúng pack** để lấy tham số thực, không giả định mọi pack có giao diện tham số giống nhau. `verify.ps1` của repo là runner R8.4, khác `verify.ps1` của pack.

## 8. Thay đổi hợp đồng và tài liệu

Khi sửa API/contract, cập nhật source + test + trang chính cùng thay đổi. Nếu quyết định kiến trúc mới, có ADR với ngày, căn cứ, trade-off và ảnh hưởng; **không sửa hồi tố ADR đã chốt**. Task state và biên bản nghiệm thu do DOC-04/07 quản lý tập trung; trang module chỉ giải thích năng lực và link evidence. Mẫu tài liệu, quy định owner/provenance ở [tiêu chuẩn kỹ thuật](TIEU_CHUAN_KY_THUAT.md), đặc tả [DOC-02](../standardization/DOC02_KHUON_MAU_VA_TIEU_CHI.md).

## 9. Checklist reviewer và giới hạn

Reviewer cần trả lời được: thay đổi đúng owner chưa; có sửa dữ liệu RAW/SQLite hay camera không; source/tests paths có thật không; lỗi/cancel/timeout có xử lý; thay đổi có phục hồi được không; gate Quick/Full và manual ở trạng thái nào; có đổi bất biến R7/R8 không; evidence nằm ngoài Git không; tài liệu cập nhật đúng chủ? Nếu chưa có log operator, kết luận chỉ là **SOURCE_REVIEWED**, không phải Windows PASS. Sổ tay này không ấn định một chuẩn branch/protection ngoài những gì repo và operator đã xác nhận.
