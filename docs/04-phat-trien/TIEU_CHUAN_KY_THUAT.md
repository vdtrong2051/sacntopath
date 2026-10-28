# Tiêu chuẩn kỹ thuật: mã nguồn, hợp đồng và tài liệu

> `owner: ENGINEERING_OWNER` · `as_of_commit: a847faebe54050cd6f8bc42cc882b3927ddabfe2` · `verified_at: 2026-10-28`  
> `scope: Python/Qt/C++/RAW/SQLite, bảo toàn bằng chứng và quy tắc tài liệu v2` · `source-of-truth: source tree; docs/02-kien-truc; DOC02_KHUON_MAU_VA_TIEU_CHI.md` · `evidence_level: SOURCE_REVIEWED / WINDOWS_EXECUTION_NOT_TESTED`

## 1. Mục tiêu và cách áp dụng

Chuẩn kỹ thuật ưu tiên **đúng hợp đồng, truy vết và bảo trì** hơn giảm số file hay sao chép boilerplate. Không tồn tại lint/formatter tự động bắt buộc riêng ở `pyproject.toml` của baseline này; các quy tắc đặt tên/kiểm thử dưới đây là **chuẩn đóng góp của tài liệu**, không tuyên bố CI đang enforce hết. Khi thêm công cụ lint, phải chốt lệnh, phiên bản, cấu hình và test theo mốc riêng; DOC-03C không tự thêm dependency. Không sửa hàng loạt source chỉ vì tài liệu này.

## 2. Ranh giới kiến trúc và dependency

- **Domain/application:** quy tắc nghiệp vụ, DTO, command, đơn vị, validation và trạng thái. Không import `QWidget`, bắt tạo `QApplication`, tự vẽ VTK hay thay thế storage qua SQL trực tiếp từ UI.
- **Presentation (Qt):** chỉ phối hợp interaction, presenter/controller, event loop và trạng thái hiển thị; IO/camera/native nặng không chặn GUI thread. Lifetime widget, cancel và close phải xác định chủ sở hữu.
- **Infrastructure:** SQLite, filesystem, SDK/host IPC và file format adapter. Lỗi ở tầng này chuyển thành trạng thái được application/UI xử lý, không làm rò rỉ đối tượng SDK qua các hợp đồng bất biến.
- **Viewer:** child process VTK cách ly với Qt; frame shared memory phải copy trong thời gian hiệu lực, sau đó ACK; scene revision/frame revision chống kết quả stale. `vtkCellPicker` là phép giao face, không mặc định là vertex CAD.
- **RAW/Storage:** bất biến schema, SHA-256, marker `COMMITTED`, idempotence/reservation; không giả định atomic transaction chung SQLite+filesystem. Dữ liệu cảm biến `measured=True` khác `metric_validated`.

Sơ đồ module và lớp thực tế có tại [Kiến trúc](../02-kien-truc/KIEN_TRUC_HE_THONG.md) và [dữ liệu/hệ tọa độ](../02-kien-truc/DU_LIEU_VA_HE_TOA_DO.md).

## 3. Quy tắc Python/Qt và C++20 khi thay đổi mới

| Chủ đề | Quy tắc góp code | Dấu hiệu cần review |
|---|---|---|
| Định danh | Giữ tên API/file/class đã công bố; code mới dùng tên mô tả hành vi, Python `snake_case`, class `PascalCase`, constant `UPPER_SNAKE_CASE` | Rename phá người gọi mà thiếu migration/test |
| Type & contract | Bổ sung type hints ở ranh giới public và unit/frame/provenance tại DTO | `dict` không schema chứa mm/m/px lẫn nhau |
| Exceptions | Phân loại input invalid, timeout, cancelled, child loss, IO/SQLite fail | `except Exception: pass`, fallback báo PASS |
| Qt lifecycle | Callback/worker không ghi widget đã đóng; dispose và thread affinity rõ ràng | long blocking IO trên GUI thread, signal sau close |
| C++ ABI | C++20, build qua CMake; explicit ownership buffer/DLL, version SDK, Python interpreter khi binding | copy `.pyd` thủ công không xác minh DLL/runtime |
| Filesystem | validate tên/path, không theo symlink không an toàn, checksum trước dùng, không ghi RAW ngoài lệnh | thao tác destructive ở lúc import hoặc test docs |
| Concurrency | timeout/cancel, state transition, revision token và ACK được kiểm thử | retry vô hạn, stale frame vẫn được render |
| Test | thêm test cho nhánh lỗi và tình trạng không có thiết bị | chỉnh test cũ chỉ để PASS hoặc SKIP không có lý do |

**Comment và docstring:** ưu tiên tiếng Việt cho các tiền/hậu điều kiện không hiển nhiên, nguồn số đo, process/thread ownership, lý do chống race/crash. Không dịch định danh public/thuật ngữ SDK làm sai API. Comment cần giải thích *vì sao*, không viết lại từng lệnh. Kiểm tra side effects tại import (đặc biệt camera và SQLite). Không tạo class/file chỉ để vượt một ngưỡng dòng tùy ý.

## 4. Ví dụ lỗi và cách viết hợp đồng

**Anti-pattern (minh họa, không trích source):** `if capture.measured: return {"metric_validated": True}`. Đây là suy diễn sai: sensor có thật không tự cho độ chính xác kích thước. Hợp đồng đúng giữ riêng trạng thái đo (`measured`) và chứng cứ kiểm định (`metric_validated` khi có kiểm chứng độc lập), giữ đơn vị `m/unit`, `mm`, `unknown` trong đúng trường, không đổi ngầm ở UI.

**Anti-pattern Viewer:** giữ một `memoryview` của shared-memory frame rồi gửi `ACK` ngay và còn đọc sau ACK. Chủ host có thể tái sử dụng bộ nhớ, gây ảnh nhấp nháy hoặc stale. Cách đúng theo thiết kế đã có: client xác nhận revision, **copy** RGB sang buffer sở hữu riêng trước khi ACK, drop frame trái scene/frame revision. Khi test, mô phỏng delayed/stale response và host teardown, không chỉ happy path.

**Anti-pattern Storage:** cập nhật SQLite row và bỏ qua `COMMITTED` vì "transaction SQL đã xong". Hai hệ lưu trữ độc lập nên cần marker/hash/check recovery và trạng thái pending; đọc dữ liệu chỉ khi hợp đồng cho phép. Không kiểm thử bằng cơ sở dữ liệu thật hoặc tự chạy migrate.

## 5. Mẫu thay đổi và tiêu chí review

Một PR hoặc patch có hành vi mới cần: (1) mô tả mục tiêu và phạm vi; (2) source path và API thay đổi; (3) bất biến giữ/đổi; (4) test mới hoặc cập nhật với lý do; (5) lệnh kiểm và log/receipt; (6) ảnh hưởng tới docs/ADR; (7) cách rollback; (8) giới hạn chưa kiểm. Đối với thay đổi chỉ docs, bỏ source build nếu không ảnh hưởng nhưng vẫn chạy R7/R8 Full theo yêu cầu mốc. `git diff --check`/`git diff --cached --check` giúp phát hiện whitespace nhưng **không** chứng nhận hành vi.

## 6. Quy tắc tài liệu: một nơi quản lý một thông tin

| Loại thông tin | Chủ sở hữu v2 | Đừng sao chép vào |
|---|---|---|
| Giới thiệu/phạm vi | `docs/01-tong-quan/` | nhiều README trùng nhau |
| Kiến trúc, phụ thuộc và hệ tọa độ | `docs/02-kien-truc/` | nhiều ghi chú rời không có owner |
| Cách module hoạt động & sửa | `docs/03-modules/` | hàng loạt hồ sơ ngắn cần tự ghép |
| Cài đặt/build/Git/code/test | `docs/04-phat-trien/` | ghi chú R7/R8 và `development/` cũ |
| Task, state | `docs/05-quan-ly/` (DOC-04) | roadmap và biên bản nghiệm thu |
| Giai đoạn, acceptance, nguồn lịch sử | `docs/06-giai-doan/`, `07-nghiem-thu/`, `99-lich-su/` (DOC-04/05) | module + README copy bảng PASS |

Mỗi trang chuẩn ghi `owner`, `as_of_commit`, `verified_at`, `scope`, `source-of-truth`, `evidence_level`, **giới hạn đã biết**, link tương đối hợp lệ và loại chứng cứ. Viết chủ yếu tiếng Việt; tên API/class/file giữ chính xác tiếng Anh theo code. Khi code đổi, cập nhật trang owner trong cùng PR; thông tin chưa kiểm ghi `CHƯA XÁC MINH`/`NOT_TESTED`, không lấp bằng phỏng đoán. Template tại [DOC-02](../standardization/DOC02_KHUON_MAU_VA_TIEU_CHI.md).

## 7. Cập nhật nội dung kỹ thuật và kiểm chứng

Khi sửa một module, reviewer tự hỏi: người mới đọc **một trang** đã hiểu mục đích, input/output, flow, lỗi, lifecycle, source/API, test, giới hạn chưa? Nếu không, bổ sung phần giải thích vào trang chuẩn, không bắt người đọc ghép năm tài liệu lịch sử. Tham chiếu hồ sơ R4/R5/ADR để hiểu *tại sao*, không dùng snapshot lịch sử làm lời khẳng định runtime hiện hành. [`DOC02_TRUY_VET_43.csv`](../standardization/DOC02_TRUY_VET_43.csv) là bảng truy vết nội dung/hợp đồng, không phải trạng thái nghiệm thu sống; giữ đúng đường dẫn để gate kiểm.

Nếu nội dung cần thay đổi status, không sửa phần đánh giá lịch sử: DOC-04 cập nhật state ledger, acceptance ghi chứng cứ/kết quả độc lập, archive giữ nguyên. Không ghi kết luận **PASS tổng thể R6** nếu cổng 08.06.6 chưa có bằng chứng thủ công. Ba symlink SKIP được phép ở R8.3 không chứng minh đã chạy được nhánh từ chối symlink trên Windows.

## 8. Kiểm soát trước khi đề xuất commit

Ví dụ chỉ đọc kết quả Git và chạy kiểm tra whitespace, dùng PowerShell tại root repo; không ghi hay sửa dữ liệu:

```powershell
Set-Location -LiteralPath $repo
git status --short
git diff --check
if ($LASTEXITCODE -ne 0) { throw 'WORKTREE_DIFF_CHECK_FAILED' }
git diff --cached --check
if ($LASTEXITCODE -ne 0) { throw 'STAGED_DIFF_CHECK_FAILED' }
```

Kiểm tra trên chưa thay thế `scripts/verify.ps1 -Profile Full`: tài liệu có thể hợp lệ mà hệ thống test vẫn sai, và một regression tự động PASS không đồng nghĩa nghiệm thu HMI.

## 9. Quản lý phiên bản, review và giới hạn

- **Trace:** trang kỹ thuật mang source commit và ngày kiểm; test gate tài liệu phải kiểm file/link/API thực; không biến digest Git thành số đo khoa học.
- **ADR:** bất biến theo ngày ký; nếu thay quyết định, tạo ADR mới và cập nhật chỉ mục áp dụng (DOC-04), không overwrite bản gốc.
- **History/incident:** giữ các lần FAIL, waiver và operator report cùng receipt; không thay lịch sử để khớp quyết định mới.
- **Review:** lint Markdown/link là điều kiện cần; operator review tính dễ hiểu là điều kiện độc lập. Không điền reviewer giả, không báo `MANUAL_PASS` chỉ vì script chạy 0.
- **Giới hạn:** tài liệu không enforce tự động mọi quy tắc naming/lint; các màn hình HMI/hardware/native fault vẫn `NOT_TESTED` nếu không có receipt operator. DOC-05 mới di chuyển alias/redirect và sửa gate phụ thuộc đường dẫn.
## 10. Quy tắc ghi nhật ký và đính chính (DOC-04)

Quy tắc này kế thừa [hồ sơ ghi nhật ký R7](TIEU_CHUAN_KY_THUAT.md); không sửa hồ sơ gốc. Mỗi mốc ghi `ID`, `as_of_commit`, ngày/môi trường, nguồn, kết quả **đúng loại phép thử**, giới hạn và bước tiếp theo. Phân loại bằng chứng: `XAC_MINH_GIT` chỉ chứng minh commit/file; `NGUOI_VAN_HANH_BAO_CAO` là log operator, không mặc nhiên remote-verified; `CHUA_KIEM_THU` khác `FAIL`; `MIEN_CO_DIEU_KIEN` cần người duyệt và residual risk, không phải `PASS`.

Với incident, ghi nguyên triệu chứng, attempt FAIL, giả thuyết/`root_cause` đã xác nhận hay chưa, fix, regression, residual risk và owner; các lỗi R6 PowerShell `$args`/exit code thuộc **harness**, không phải crash app. Không ghép phiên chưa thử vào danh sách incident đã xảy ra. Nếu một snapshot cũ ghi R8 `NOT_STARTED` mà source Git đã có R8.5, ghi **ĐÍNH CHÍNH** ở hồ sơ mới cùng thời điểm/nguồn; **không hồi tố sửa** nhật ký/ADR/waiver cũ.

Nguồn sống của task là [Task Register](../05-quan-ly/TASK_REGISTER.md), của trạng thái là [State Ledger](../05-quan-ly/TRANG_THAI_DU_AN.md), của receipt là [Evidence Index](../07-nghiem-thu/EVIDENCE_INDEX.md). Chỉ được chuyển task sang `DONE` sau gate và người duyệt; không sao chép bảng kết quả vào mọi module. Trong DOC-04, `R6_OVERALL_PENDING` và `GD1_OVERALL_PENDING` vẫn giữ cho tới khi 08.06.6 có quyết định độc lập.
