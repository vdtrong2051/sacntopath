# Quy trình kiểm thử và bằng chứng nghiệm thu

## 1. Kiểm thử tự động

```powershell
$py = '.\.venv\Scripts\python.exe'
$env:QT_QPA_PLATFORM = 'offscreen'
& $py -X utf8 -m pytest -q -rs tests
if ($LASTEXITCODE -ne 0) { throw 'Pytest failed' }
ctest --test-dir .\build-orbbec -C Release --output-on-failure
if ($LASTEXITCODE -ne 0) { throw 'CTest failed' }
Remove-Item Env:QT_QPA_PLATFORM -ErrorAction SilentlyContinue
```

Bổ sung Architecture Guard và Quality Gate theo `scripts/check_architecture_boundaries.py`, `scripts/check_07_12_quality.py`; kiểm tra liên kết tài liệu ở R7-B.

## 2. Phần phải kiểm bằng giao diện thật

Qt offscreen không thay thế thao tác chuột, bố cục tại các DPI khác nhau, khả năng đóng khi native thật sự bận hay đo frame xuất hiện trên màn hình. Bảng HMI R6 cần có PASS/FAIL/NOT_TESTED từng ca; phép đo chưa làm phải ghi `NOT_TESTED`.

## 3. Mốc bằng chứng

R6 tự động (operator Windows, 27/10/2026): 14/14 cổng PASS, 618 pytest PASS, ba symlink SKIP do quyền Windows, CTest 2/2. Benchmark 1K/100K/1M là completed renderer workload, **không phải FPS vật lý**.

Chi tiết: [Bảng nghiệm thu](../acceptance/GD1.md).

## R8.2 — Phân nhóm test theo chức năng

Các ca kiểm thử được phân theo nhóm và giữ nguyên tên hàm pytest. Dùng `python -m pytest -q tests` để chạy tất cả. Đường dẫn trước/sau xem [bản đồ R8.2](../standardization/R8_2_BAN_DO_TEST.csv). Fixture RAW và Project dùng chung nằm trong `tests/support/`. Không tự xóa test trong R8.2; R8.3 mới xử lý chất lượng hợp đồng.

## R8.3 — Hợp đồng fixture và SKIP Windows

Fixture RAW/SQLite tổng hợp giữ nguyên thân hàm sau R8.2; kiểm tra tính bất biến ở `tests/contracts/quality/test_gd1_r8_3_contracts.py`. JUnit chỉ chấp nhận ba SKIP do quyền symlink trên Windows theo **đúng test ID**, các SKIP khác là FAIL; Qt bắt buộc không được SKIP. Tài liệu: [R8.3](../standardization/R8_3_HOP_DONG_FIXTURE_VA_SKIP.md). Chạy full pytest với `--junitxml=<evidence>/R83_full.xml` rồi dùng `scripts/check_qt_acceptance_xml.py --junit <evidence>/R83_full.xml` trên Windows. Qt offscreen không thay thế HMI/native trên thiết bị thật.

## R8.4 — Bộ kiểm thử thống nhất

Sử dụng `scripts/verify.ps1 -Profile Quick|Full|Acceptance` để chạy một pipeline duy nhất, ghi JUnit/JSON bên ngoài repository. `Quick` không thay `Full`; `Acceptance` vẫn ghi `PENDING_MANUAL` nếu thiếu xác nhận HMI/native thực tế. Có thể chủ động bật `-RunNativeProbe` và `-RunBenchmark` riêng trong `Acceptance`. Xem [hướng dẫn R8.4](../standardization/R8_4_BO_KIEM_THU_THONG_NHAT.md).
## R8.5 — Kiểm toán và khóa hệ thống kiểm thử

`Quick`, `Full`, `Acceptance` đều chạy thêm `R8_5_AUDIT` qua `scripts/r8_5_audit.py`. Công cụ so sánh 80 file test, 27 script của mốc R8.4 và xuất các ứng viên trùng AST hoặc thiếu tham chiếu tĩnh vào `evidence` ngoài repository. **Không có file lịch sử nào bị tự động xóa**, không chuyển SKIP sang PASS. Báo cáo: [R8.5](../standardization/R8_5_KIEM_KE_VA_NGHIEM_THU.md). `Full` PASS khóa riêng hệ thống regression; nghiệm thu GĐ1 vẫn phải xử lý các cổng HMI/native còn mở tại 08.06.6.
