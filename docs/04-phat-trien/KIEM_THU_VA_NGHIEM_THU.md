# Kiểm thử, hồi quy và bằng chứng nghiệm thu ScanToPath

> `owner: ENGINEERING_OWNER` · `as_of_commit: a847faebe54050cd6f8bc42cc882b3927ddabfe2` · `verified_at: 2026-10-28`  
> `scope: pytest/Qt/CTest và R7/R8 unified runner; phân tầng cổng manual` · `source-of-truth: scripts/verify.ps1; scripts/r8_4_verify.py; scripts/check_qt_acceptance_xml.py; tests/` · `evidence_level: SOURCE_REVIEWED / WINDOWS_REGRESSION_NOT_TESTED`

## 1. Ba tầng kết quả bắt buộc phân biệt

**Hành vi có source (`IMPLEMENTED`)** chỉ nói có code. **Kiểm thử tự động (`PASS`/`FAIL`/`SKIP`)** chỉ nói gate tương ứng đã chạy ở môi trường có log. **Nghiệm thu thực tế (`MANUAL_PASS`, `NOT_TESTED`, `WAIVED_WITH_APPROVAL`)** dành cho DPI, GUI thật, GPU/present, native khi bận, thiết bị hoặc phép đo; không suy ra từ các tầng trước. GĐ1 còn cổng HMI 08.06.6; không nâng thành PASS từ kết quả pytest hay một commit tài liệu.

| Mức | Cổng sử dụng | Chứng minh được | Không chứng minh |
|---|---|---|---|
| Targeted | `python -m pytest ...test_file.py` | Hợp đồng cụ thể trên fixture | Toàn bộ ứng dụng hoặc HMI thật |
| Quick | `scripts/verify.ps1 -Profile Quick` | R7/R8 static + architecture/quality + tập pytest giới hạn | Full suite và CTest |
| Full | `scripts/verify.ps1 -Profile Full` | Static + toàn pytest + JUnit policy + CTest Release hai test | DPI, camera/GPU thật, native close khi busy |
| Acceptance | `scripts/verify.ps1 -Profile Acceptance` | Same automated gate as Full, tùy chọn native probe/benchmark | `overall=PASS` khi manual chưa có; runner ghi `PENDING_MANUAL` |

## 2. Chạy runner hợp nhất trên Windows

Trong PowerShell tại repo, có `.venv` đúng Python 3.12; `Full` cần `ctest` và thư mục build `build-orbbec` đã cấu hình/build hai smoke test. `EvidenceDir` **phải ở ngoài repository**. Lệnh dưới không tự mở camera (không bật các switch probe/benchmark) nhưng **tạo log/JSON/JUnit** trong `_setup`:

```powershell
$repo = 'E:\1_BigProject\scantopath\scantopath-software'
$evidence = 'E:\1_BigProject\scantopath\_setup\ScanToPath_DOC03C_Development_Handbook\evidence'
Set-Location -LiteralPath $repo
powershell -NoProfile -ExecutionPolicy Bypass -File .\scripts\verify.ps1 `
  -ProjectRoot $repo -EvidenceDir $evidence -Profile Quick
if ($LASTEXITCODE -ne 0) { throw 'QUICK_FAILED' }
powershell -NoProfile -ExecutionPolicy Bypass -File .\scripts\verify.ps1 `
  -ProjectRoot $repo -EvidenceDir $evidence -Profile Full
if ($LASTEXITCODE -ne 0) { throw 'FULL_FAILED' }
```

Kết quả kỳ vọng khi **thực tế PASS**: runner in `R8.4 RESULT | profile=... | automated=PASS`; `Full` có JUnit `pytest_full.xml`, `CTEST_RELEASE`, và JSON `SUMMARY.json` ghi các step. Nếu PowerShell có unhandled error, `$LASTEXITCODE` phải khác 0; nếu profile không chạy tới cuối hoặc log thiếu, không ghi PASS. Runner tạo subdir dạng `R84_<timestamp>_<pid>`. **Không hardcode số lượng test PASS trong trang hiện hành** vì số test tăng khi thêm test DOC-03A/B/C; đọc JUnit của lần chạy cụ thể.

`Acceptance` tự động dùng Full + manual gate placeholders; mặc định **không tự chạy native**. Chỉ khi được giao phép thử thiết bị/HMI riêng mới bật `-RunNativeProbe` hoặc `-RunBenchmark`, và khi đó phải bảo đảm Qt desktop thật, dụng cụ/thiết bị đã chuẩn bị, quyền operator, thiết bị/GPU không bị tiến trình khác chiếm. Ví dụ chạy automated acceptance (không tùy chọn):

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File .\scripts\verify.ps1 `
  -ProjectRoot $repo -EvidenceDir $evidence -Profile Acceptance
if ($LASTEXITCODE -ne 0) { throw 'ACCEPTANCE_AUTOMATED_FAILED' }
# Thành công của lệnh này vẫn có overall=PENDING_MANUAL.
```

## 3. Runner thật làm những gì và thứ tự gate

Đọc trực tiếp `scripts/r8_4_verify.py::make_plan`, `_step_command`, `run`, không thay danh sách bằng suy diễn. Các bước chung: `R7_DOCS`, `R8_1_INVENTORY`, `R8_2_STRUCTURE`, `R8_3_CONTRACTS`, `R8_5_AUDIT`, `ARCHITECTURE`, `QUALITY`. Quick nối `PYTEST_QUICK`; Full/Acceptance nối `PYTEST_FULL`, `JUNIT_POLICY`, `CTEST_RELEASE`. Native probe `NATIVE_R53_PROBE` và benchmark `R44_AB_BENCHMARK` là opt-in **chỉ** thuộc Acceptance. Trong step tự động, runner đặt `QT_QPA_PLATFORM=offscreen`; các probe native opt-in phải chạy với display thật.

`R8_5_AUDIT` kiểm danh sách file baseline và ứng viên AST duplicate; đây **là audit, không tự xóa test/script**. `R7_DOCS` vẫn cần alias `docs/INDEX.md`, `docs/architecture/CURRENT_GD1_ARCHITECTURE.md`, `docs/modules/VIEWER3D.md`, v.v. DOC-03C **không dời hoặc xóa alias**; DOC-05 mới điều chỉnh có kiểm soát. Chỉ số test/SKIP phải từ receipt thật, không lấy báo cáo R6 lịch sử để ghi thành kết quả chạy hôm nay.

## 4. Quy tắc JUnit và CTest FAIL-closed

`PYTEST_FULL` lưu JUnit ngoài repo. `JUNIT_POLICY` gọi `scripts/check_qt_acceptance_xml.py` để kiểm trạng thái Qt và chính sách SKIP R8.3: chỉ **ba test symlink Windows theo đúng test ID** được SKIP khi lý do phù hợp; SKIP ngoài danh sách, Qt SKIP hoặc test fail là FAIL. Các ca symlink chưa chạy do quyền Windows vẫn là **chưa chứng minh behavior symlink thực**; không gọi là PASS. `r8_4_verify.py::junit_summary` đếm testcase, failed, skipped và `PYTEST_FULL` yêu cầu đủ baseline tối thiểu (mốc source có điều kiện `cases >= 663`). Con số tối thiểu là ngưỡng code, không là dự báo kết quả của DOC-03C.

`CTEST_RELEASE` gọi chính xác `ctest --test-dir <repo>/build-orbbec -C Release --output-on-failure`; parser yêu cầu một dòng summary `100% tests passed ... out of ...` và ít nhất **2 test**. Nếu `No tests were found`, lỗi DLL, executable không build, hoặc chỉ có một test thì fail. Không sửa test đếm `total` hoặc dỡ CTest khỏi Full để "xanh". Xem [cài đặt/build](CAI_DAT_VA_CHAY.md) để tạo build C++ riêng; build `build-doc03c-core` kiểm smoke nhưng không thay `build-orbbec` trong Full runner.

## 5. Lựa chọn test khi sửa module

| Vùng sửa | Unit/contract đầu tiên | Integration/UI/native tiếp theo |
|---|---|---|
| Acquisition / RAW | `tests/contracts/camera/`, `tests/unit/raw/` | `tests/integration/storage/`, CTest RGB-D contract |
| Project + SQLite | `tests/unit/project/`, `tests/contracts/kien_truc/` | `tests/integration/project/`, `tests/ui/project/` |
| Desktop Shell/Task | `tests/unit/task/`, `tests/contracts/shell/` | `tests/ui/shell/`, `tests/ui/task/` |
| PLY/OBJ, Viewer, pick | `tests/contracts/renderer/`, `tests/integration/viewer/` | `tests/ui/viewer/`, `tests/native/viewer/`, `tests/native/renderer/` |
| Docs/R7/R8 | `tests/contracts/tai_lieu/`, `tests/contracts/quality/` | `scripts/verify.ps1 -Profile Full` |
| Performance R4 | `tests/performance/renderer/` | Benchmark opt-in trên Windows; không đánh đồng workload với FPS màn hình |

Với DOC-03C, thêm `scripts/check_doc03c_content.py` và `tests/contracts/tai_lieu/test_doc03c_content.py` để kiểm text/links/provenance/mapping. `scripts/verify.ps1 -Profile Full` vẫn là regression chung; **không thêm DOC-03C checker trực tiếp vào runner R8.4** vì đó là thay đổi runtime/gate và nằm ngoài scope. Pack `verify.ps1` gọi checker trước rồi mới gọi runner có sẵn. Sau khi commit, test DOC-03C vẫn thuộc full pytest.

## 6. Ví dụ chạy targeted và thu evidence an toàn

```powershell
Set-Location -LiteralPath $repo
$py = Join-Path $repo '.venv\Scripts\python.exe'
$env:QT_QPA_PLATFORM = 'offscreen'
try {
  & $py -X utf8 -m pytest -q -rs tests/contracts/tai_lieu/test_doc03c_content.py
  if ($LASTEXITCODE -ne 0) { throw 'DOC03C_TARGETED_FAILED' }
} finally { Remove-Item Env:QT_QPA_PLATFORM -ErrorAction SilentlyContinue }
```

Cổng docs tĩnh đọc file local và ghi JSON chỉ ra ngoài root. Không gọi CLI acquisition `--once`, không tạo `metadata.sqlite3`, không copy RAW. Trên Linux container chỉ có thể kiểm cú pháp/nội dung và chạy unit docs giả lập; **không** kết luận `Full` Windows/CTest/HMI PASS.

## 7. Kiểm HMI/native thực và hồ sơ còn mở

Sau `Full`, người vận hành có thể cần nghiệm thu một ma trận riêng: DPI 100/125/150; mở/đóng lại Viewer với real display; ứng dụng đóng khi C++ child đang bận; fault isolation; GPU/VRAM thực; input-to-physical-present latency. Ghi từng ca `PASS`, `FAIL`, `NOT_TESTED`, hoặc `WAIVED_WITH_APPROVAL` đúng quyền và receipt. `pytest` offscreen, native fixture hay benchmark "completed workload" không đo physical-present FPS. Tham chiếu [R6 operator status](../acceptance/GD1_R6_ACCEPTANCE_STATUS.md), hồ sơ [08.06.4](../archive/GD1/08/08_06_4_WINDOWS_HMI_ACCEPTANCE.md), [08.06.5](../archive/GD1/08/08_06_5_DEFECT_DISPOSITION_AND_HMI_WAIVER.md). Không viết đè kết quả đã có; DOC-04 sẽ xây chỉ mục nghiệm thu v2.

## 8. Khi FAIL: triage theo cổng, không sửa bài kiểm thử để PASS

1. Mở `SUMMARY.json`: tìm `errors`, bước `status=FAIL`, `exit_code`, file `.log` đúng step. `R8.4` dừng tại gate đầu thất bại nên các gate sau là **chưa chạy**, không phải PASS.
2. Nếu `R7_DOCS` fail: kiểm link/alias/AST; đối chiếu bản DOC-02 và không đổi đường dẫn cũ trước DOC-05.
3. Nếu `R8_5_AUDIT` fail: xem số file, source coupling/duplicate candidates, không xóa hoặc rename test tự phát.
4. Nếu `PYTEST_FULL` hoặc `JUNIT_POLICY` fail: xác định test ID, exception và lý do SKIP thực; test mới bị lỗi phải sửa trong scope hoặc rollback pack.
5. Nếu `CTEST_RELEASE` fail: xác minh build dir, generator/Release, DLL path và log; không giảm số expected tests.
6. Nếu HMI manual fail dù Full PASS: mở incident có ảnh/video/log và người xác nhận; không sửa hồ sơ cũ thành PASS.

## 9. Điều kiện nghiệm thu DOC-03C và giới hạn

**Kỹ thuật:** bốn trang canonical tồn tại, `DOC02_BAN_DO_65.csv` truy vết đủ các mục DOC-03C, mọi link nguồn/test tồn tại, docs portal trỏ đúng trang, gói backup/rollback bảo vệ hash; targeted DOC-03C gate và Full đạt trên Windows. **Khả năng sử dụng:** developer mới đọc được từ setup→build→debug→test→Git, hiểu khi nào lệnh ghi dữ liệu/camera, đọc được nơi sửa Viewer/RAW và giới hạn kết luận. Phần operator phải được kiểm thực, không thể tự chấm từ số tiêu đề. 

**Tình trạng tại lúc biên soạn:** SOURCE_REVIEWED / `WINDOWS_REGRESSION_NOT_TESTED`, HMI & hardware `NOT_TESTED` trong mốc DOC-03C. Các receipt cũ là lịch sử; khi operator chạy trên Windows, lấy kết quả và thời gian đúng từ thư mục evidence mới.
