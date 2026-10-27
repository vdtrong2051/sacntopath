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
