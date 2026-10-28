# R8.4 — Bộ kiểm thử thống nhất ScanToPath

**Đầu vào:** nhánh `feat/gd1-desktop-ui` sau R8.3, commit `5068224`. **Phạm vi:** công cụ và tài liệu kiểm thử; không sửa `src/`, C++, RAW hoặc SQLite người dùng. R8.4 không phải nghiệm thu GĐ1 cuối cùng.

## Chạy trên Windows PowerShell

Tại thư mục repository, sau khi kích hoạt `.venv`:

```powershell
.\scripts\verify.ps1 -Profile Quick
.\scripts\verify.ps1 -Profile Full
.\scripts\verify.ps1 -Profile Acceptance
```

Để **chủ động** kiểm tra native trên màn hình thật và benchmark A/B (không bật mặc định), dùng:

```powershell
.\scripts\verify.ps1 -Profile Acceptance -RunNativeProbe -RunBenchmark
```

Không sử dụng `QT_QPA_PLATFORM=offscreen` hoặc `minimal` cho native probe. Các lệnh không tự động khởi động camera RGB-D. Benchmark dùng fixture ảo, có thể sử dụng CPU/GPU và chạy lâu. Có thể chỉ chạy một trong hai công tắc.

`-EvidenceDir` tùy chọn chỉ nhận đường dẫn **ngoài** Git repository. Mặc định: thư mục `../_setup/ScanToPath_R8_Verification/evidence/R84_<timestamp>_<pid>/`. Mỗi lần chạy lưu `SUMMARY.json` và log từng gate, pytest sinh XML, CTest được đối chiếu số ca thực từ output. Không phát sinh receipt PASS nếu không có XML hoặc nếu bất kỳ gate thất bại.

## Profile và điều kiện

| Profile | Nội dung | Quyết định |
|---|---|---|
| `Quick` | R7 docs, kiểm kê R8.1, cấu trúc R8.2, hợp đồng R8.3, Architecture/Quality và pytest tập trung | `PASS` hoặc `FAIL`; **không** thay Full |
| `Full` | Các cổng Quick tĩnh + toàn bộ pytest, JUnit policy theo đúng test ID và CTest Release | `PASS` hoặc `FAIL` |
| `Acceptance` | Full + native R5.3/benchmark **nếu được chọn tường minh**; xuất mọi cổng manual chưa kiểm thử | `automated=PASS` có thể đi cùng `overall=PENDING_MANUAL` |

### Những gì không được suy ra

- Qt offscreen PASS không chứng minh DPI 100/125/150 hoặc thao tác HMI thật.
- R5.3 native probe không chứng minh crash C++ khi đang bận, lỗi native C++ thực hay input-to-display-present latency.
- Benchmark R4.4 chỉ đo render-completed; không phải FPS hiển thị màn hình và không thay đo VRAM.
- Ba SKIP symlink được cho phép đúng test ID bởi R8.3, không trở thành PASS về kiểm soát symlink.
- `Acceptance` luôn ghi `NOT_TESTED` cho 6 cổng hiện chưa có quy trình đo đủ chặt: DPI, reopen/close HMI, close native busy, fault injection native, GPU/VRAM, input-to-present.
- Việc chấp nhận ngoại lệ và khóa cuối GĐ1 thuộc mốc **08.06.6**, không thuộc runner này.

## Chống lỗi hệ thống chạy kiểm thử

- Gọi subprocess bằng mảng đối số Python (không dùng biến `$args` PowerShell).
- Mọi tiến trình có exit-code và timeout riêng; script fail-closed với bước lỗi đầu tiên.
- Full pytest yêu cầu tối thiểu **663 trường hợp trong JUnit** (mốc R8.3 = 660 PASS / 3 SKIP), đồng thời các SKIP phải đạt chính sách R8.3.
- CTest yêu cầu báo cáo thực tế có ít nhất 2 ca và 0 ca FAIL.
- Kết quả được lưu ngay sau từng gate để phân tích lỗi ở bước tiếp theo.
- `status=PASS` của Quick/Full chỉ phản ánh phần **tự động**, không nâng `R6_OVERALL_PENDING` thành PASS.

## Chuyển sang R8.5

R8.5 có thể dựa trên log/receipt thống nhất để đối chiếu test trùng, bộ script lịch sử và phạm vi chức năng được bảo vệ; không tự động xóa test vì đổi đường dẫn hoặc trùng tên chức năng.
