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

## 7. Quyết định đóng GĐ1 ngày 28/10/2026

**Marker:** `GD1_08_06_6_FINAL_CLOSURE_20261028`.
**Quyết định cuối cùng:** `CLOSED_ACCEPTED_WITH_EXPLICIT_OPERATOR_WAIVERS`. Chủ dự án yêu cầu dừng kiểm thử GĐ1, đóng mốc phát triển và merge `feat/gd1-desktop-ui` vào `main` trong hội thoại ngày 28/10/2026. Đây là quyết định **chấp nhận phạm vi phát triển có giới hạn**, không phải kết quả `PHYSICAL_ALL_PASS`; không có chữ ký kiểm toán độc lập.

| Gate | Trạng thái khi đóng | Căn cứ và rủi ro còn lại |
|---|---|---|
| R8.4 Full regression | `OPERATOR_REPORTED_PASS` | Operator báo Full 10/10 sau sửa Zoom; evidence tại `E:\1_BigProject\scantopath\_setup\GD1_08_06_6\zoom_fix_full_v3\` trên Windows, chưa được GitHub connector đọc độc lập. |
| `HMI_DPI_100_125_150` | `OPERATOR_ACCEPTED_PASS` | Đã thao tác Qt thật và chụp hình 3 mức DPI theo operator. |
| `HMI_REOPEN_CLOSE_REAL` | `OPERATOR_ACCEPTED_PASS` | Operator xác nhận 5 vòng đóng/mở, UI không treo; chưa đối chiếu độc lập trace PID mỗi vòng. |
| `CPP_NATIVE_BUSY_CLOSE` / NT-01 | **`WAIVED_BY_OPERATOR`** | File 1,4 triệu điểm tải quá nhanh, chưa chứng minh native BUSY tại thời điểm đóng; chấp nhận rủi ro cleanup race chưa thử. Không ghi PASS. |
| `CPP_NATIVE_FAULT_ISOLATION` / NT-02 | `PASS_CONTROLLED_FAIL_FAST` | C++ fail-fast test-only trong Render Host; Windows Application Error Event ID 1000 (28/10/2026 23:36:21), PID `0x8958`/35160, exception `0xC0000602`; Qt vẫn hoạt động, UI báo lỗi, operator mở lại PLY được. Không chứng minh mọi lỗi VTK hay tự phát hiện lúc idle. |
| `GPU_VRAM_MEASURED` / NT-03 | **`WAIVED_BY_OPERATOR`** | PLY 1.400.000 điểm và tương tác hoạt động; CPU tối đa 2,8% theo operator. Task Manager nhóm Python RAM ~73,0 → 299,6 → 264,7 MB; **không đo GPU utilization, dedicated/shared VRAM hay VRAM peak**. Không cam kết VRAM. |
| `INPUT_TO_PHYSICAL_PRESENT_LATENCY` / NT-04 | **`WAIVED_BY_OPERATOR`** | Không có phép đo input-to-photon, P95/P99 hoặc cam kết FPS vật lý. |
| Zoom toolbar | `OPERATOR_ACCEPTED_PASS` | Đã sửa và kiểm thử trên UI Windows; regression test PASS, commit `92a7e7a`. |

**Dữ liệu và môi trường:** Qt/PySide6 và VTK trên Windows, PLY tổng hợp 1,4 triệu điểm; Windows Event Log và ảnh trong hội thoại; evidence gốc ngoài Git ở `E:\1_BigProject\scantopath\_setup\GD1_08_06_6\`. Không đưa fault-injection DLL, dữ liệu RAW, SQLite, PLY cá nhân hoặc secrets vào Git.

**Giới hạn:** Không coi Viewer GĐ1 là hệ thống realtime 60 FPS, không chứng nhận GPU budget/VRAM peak, không suy ra metric calibration, fusion, RAW→mesh/path, robot trajectory hay điều khiển cơ cấu. Các nhận định `NOT_MEASURED` vẫn giữ nguyên. Các mục 1–6 phía trên là snapshot trước ngày chốt; mục 7 là quyết định mới nhất. Bắt đầu GĐ2 bằng baseline/phạm vi riêng, không mở lại R7/R8 để tiếp tục dọn nợ GĐ1.
