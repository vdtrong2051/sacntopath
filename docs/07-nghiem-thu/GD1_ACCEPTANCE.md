# GĐ1 — Nghiệm thu Desktop/Viewer, ranh giới automated và HMI 08.06.6

> `owner: ACCEPTANCE_OWNER` · `as_of_commit: 81da5d2050324b1dc4a65ffbca9a38ed1ebba10a` · `verified_at: 2026-10-28`  
> `scope: gate cuối GĐ1 và điều kiện pending` · `source-of-truth: cổng nghiệm thu GĐ1; trạng thái tổng thể chỉ ở 05-quan-ly` · `evidence_level: R6_OPERATOR_REPORTED + R8_CODE_GIT_VERIFIED; FINAL_MANUAL_NOT_TESTED`

## 1. Căn cứ và điều kiện chốt

GĐ1 có code Qt/Project/Viewer PLY/OBJ R5.3. Hồ sơ R6 ngày 27/10/2026 báo **14/14 automated PASS**, pytest **618 passed / 3 skipped** (privilege symlink), CTest **2/2**, native transport/geometry/benchmark. Đây là **OPERATOR_REPORTED**, không phải lần kiểm tra remote DOC-04 mới. R8.5 code/script đã commit; kết quả `Full` trên máy operator sau DOC-04 **chưa có receipt trong nguồn đối chiếu**.

Quyết định final yêu cầu cả (1) Full gate tự động của baseline đang xét và (2) các gate HMI/native thực địa có PASS hoặc waiver **đúng scope, có người duyệt**, tất cả có timestamp/receipt. Cho đến lúc đó: **`GD1_OVERALL_PENDING`**, task `GD1-08-06-6` BLOCKED.

## 2. Automated gate và cách đọc

| gate_id | expected / command | evidence hiện có | quyết định DOC-04 |
|---|---|---|---|
| `ARCHITECTURE_0711` | 0 import/dependency violations | R6 operator báo PASS | `HISTORICAL_OPERATOR_REPORTED_PASS` |
| `QUALITY_0712` | source quality rules PASS | R6 operator báo PASS | `HISTORICAL_OPERATOR_REPORTED_PASS` |
| `PYTEST_R6` | R6 full Python/Qt | 618 PASS, 3 SKIP theo R6 | `HISTORICAL_OPERATOR_REPORTED_PASS_WITH_3_SKIP` |
| `JUNIT_R6` | 621 cases, 0 fail, đúng skip policy | R6 operator báo PASS | `HISTORICAL_OPERATOR_REPORTED_PASS` |
| `CTEST_R6` | core + RGB-D contract | 2/2 PASS theo R6 | `HISTORICAL_OPERATOR_REPORTED_PASS` |
| `RENDER_R53` | geometry, transport, native probe và benchmark | R6 14/14 tổng, 1K/100K/1M completed-workload | `HISTORICAL_OPERATOR_REPORTED_PASS`, không suy physical FPS |
| `R8_FULL_CURRENT` | `scripts/verify.ps1 -Profile Full` + `SUMMARY.json` JUnit/CTest, R8.5 audit | `scripts/verify.ps1`, R8.4 runner và R8.5 audit **đã có source**; receipt chưa đối chiếu | `NOT_TESTED_AT_DOC04`; Windows operator phải chạy |
| `DOC04_CONTENT` | check DOC04 + targeted pytest + reviewer | Chỉ có trong pack DOC04; chưa áp | `NOT_TESTED_AT_DOC04`; không tự PASS |

`R8_FULL_CURRENT` chỉ được nâng khi receipt thực có `automated=PASS`, `overall=PASS` của **Full** cho đúng commit/working tree, và JUnit/CTest hợp lệ. `Acceptance` tự động có thể `automated=PASS`, `overall=PENDING_MANUAL`; không điền `MANUAL_PASS` thay runner.

## 3. Sáu manual/physical gates của 08.06.6

| gate_id | expected / phương pháp | result tại DOC-04 | evidence và điều kiện PASS/waiver |
|---|---|---|---|
| `HMI_DPI_100_125_150` | Mở Qt thật ở 100/125/150%, kiểm focus/clipping/tooltip, screenshot/checklist từng DPI | `NOT_TESTED` cho bộ R6 final | Ảnh, cấu hình monitor/OS, người duyệt và case-by-case result |
| `HMI_REOPEN_CLOSE_REAL` | Reopen/close nhiều lần và kiểm PID/host/SQLite owner | `PARTIAL_EVIDENCE` — 08.06.4 session A normal close | Các lần khởi động/đóng thực với thời điểm/process list; session A không đủ tự chứng minh mọi cycle |
| `CPP_NATIVE_BUSY_CLOSE` | Chứng minh C++ worker **đang bận** rồi close, bounded cleanup | `NOT_TESTED` trong R6 final | Native trace before/after, busy proof, timeout và PID; TC11 waiver cũ chỉ phạm vi 08.06.5 |
| `CPP_NATIVE_FAULT_ISOLATION` | Inject lỗi native C++ có kiểm soát trong child; Qt parent còn sống | `NOT_TESTED` | Fault receipt/exit code/core & recovery evidence; kill process không tương đương C++ native fault |
| `GPU_VRAM_MEASURED` | Đo GPU/VRAM với method/driver/renderer workload, Qt+host | `PARTIAL_EVIDENCE` — RSS CPU là dữ liệu khác | VRAM/driver tool + peak, không thay bằng RAM ~MiB của process con |
| `INPUT_TO_PHYSICAL_PRESENT_LATENCY` | Từ user input đến khung hình hiện vật lý, có thiết bị/cách đo | `NOT_TESTED` | Measurement method, sampling, units, thresholds; benchmark completed-render ≠ physical-present |

Ngoài bảng, việc đánh giá `NOT_RUN_WAIVED_BY_OPERATOR` cho TC11/TC12 của [08.06.5](../99-lich-su/ARCHIVE/GD1/08/08_06_5_DEFECT_DISPOSITION_AND_HMI_WAIVER.md) chỉ chứng minh **quyết định operator ở phiên cũ**. Không tự thừa nhận có waiver `08.06.6`; để waive gate mới phải mở quyết định độc lập, mô tả phạm vi, rủi ro còn lại, người phê duyệt, ngày và receipt.

## 4. Quy trình ký 08.06.6

1. Khóa SHA/version source và người vận hành; giữ bộ `SUMMARY.json`, JUnit XML, CTest Release và kết quả R8.5 audit **ngoài Git** trong `_setup/.../evidence`.
2. Đối chiếu bảng từng gate với `expected`, `method`, `environment`, `result`, `evidence`, `executed_at`, `reviewer`, `limitation` và `next_action`; `NOT_TESTED` vẫn là NOT_TESTED nếu chưa có phép thử tương ứng.
3. Nếu một gate không thử được, lập waiver cụ thể trước khi sign-off; không chỉnh test/threshold chỉ để PASS. Ghi rủi ro residual, phương án thử lại và thẩm quyền.
4. Kết luận `PASS/FAIL/PENDING/ACCEPTED_WITH_EXPLICIT_WAIVER` dựa trên **quyết định 08.06.6 thực**, cập nhật [Evidence Index](EVIDENCE_INDEX.md), [State Ledger](../05-quan-ly/TRANG_THAI_DU_AN.md) và task `GD1-08-06-6`. Không ghi trạng thái PASS ở tất cả tài liệu cũ.

## 5. Dùng sổ tay và kiểm thử tại máy Windows

Ở gốc repo, tách biến môi trường offscreen của pytest khỏi HMI thật. Lệnh chuẩn đã xác minh với source `scripts/verify.ps1`:

```powershell
$repo = 'E:\1_BigProject\scantopath\scantopath-software'
Set-Location -LiteralPath $repo
powershell -NoProfile -ExecutionPolicy Bypass -File .\scripts\verify.ps1 -ProjectRoot $repo -Profile Full
if ($LASTEXITCODE -ne 0) { throw 'R8_FULL_FAILED' }
```

Lưu ý: PowerShell script dùng `throw` khi lỗi, vì vậy nếu gọi từ automation riêng phải kiểm tra **cả exit code và receipt**, không chỉ đọc chữ PASS trong stdout. Khi cần manual thật, bỏ `QT_QPA_PLATFORM=offscreen` và chạy trên máy Windows có desktop/driver. Xem [sổ tay test](../04-phat-trien/KIEM_THU_VA_NGHIEM_THU.md).

## 6. Giới hạn đã biết

DOC-04 không đo DPI/native fault/GPU/physical-present, không xác minh độc lập evidence ngoài Git, và không tự tạo waiver mới. Source có `R8.5` nghĩa có **công cụ kiểm chứng** chứ không đồng nghĩa mọi gate đã chạy ở HEAD hiện tại. Mọi claim final PASS cần sign-off ở 08.06.6.
