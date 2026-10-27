# GĐ1 / R6 — Ma trận trạng thái nghiệm thu (chưa đóng R6 tổng thể)

**Ngày ghi nhận:** 27/10/2026. **Nhánh:** `feat/gd1-desktop-ui`. **HEAD trước R7:** `ff45ccf87ce770e25eedf6e12df6bb5aaa958734`. **Nguồn:** người vận hành dán PowerShell log R6, không phải máy Windows do R7 độc lập truy cập.

## Kết quả tự động — OPERATOR_REPORTED, đủ để khóa riêng phần automated

| Gate | Quan sát từ log | Kết quả |
|---|---|---|
| Architecture import boundary 07.11 | 0 violations | PASS |
| Quality 07.12 | 0 errors | PASS |
| Full Python / Qt | 618 passed, 3 skipped; symlink privilege x3 | PASS WITH 3 DOCUMENTED SKIPS |
| JUnit policy | 621 cases, 0 failed, 3 expected skips | PASS |
| CTest Release | `core_smoke`, `rgbd_contract_smoke` | 2/2 PASS |
| PLY points / PLY mesh / OBJ | 3 fixtures, one PID, source unchanged | PASS |
| Frame transport | 100 submitted camera events; latest revision confirmed, coalesced renders | PASS |
| Native Qt / VTK probe R5.3 | Picking, icon, grid, Inspector | PASS |
| Resident benchmark | 1k/100k/1m points; 20 cycles | `MEASURED_PASS` (không phải FPS thực của màn hình) |
| Receipts | geometry, transport, native, benchmark | 4/4 PASS |
| Git status | clean; HEAD đúng R5.3 | PASS |

**Tổng:** `AUTOMATED_PASS`, 14/14 cổng, **theo log operator**. Folder evidence được log: `_setup/ScanToPath_R6_Auto_Acceptance/evidence/R6_20261027T150605Z_19408`. Thư mục này ở Windows ngoài repository; R7 không đọc được artifact gốc từ GitHub và không sao chép giả nó vào repo.

**Ba SKIP:** `tests/test_gd1_07_2_numbered_storage.py:195`, `tests/test_gd1_r4_3_transport_lifecycle.py:197`, `tests/test_raw_storage.py:221`; nguyên nhân quyền tạo symlink Windows. Không gọi những đường bảo vệ symlink tương ứng là đã được kiểm thử thực địa.

## Điều kiện còn mở — KHÔNG đánh dấu PASS tự động

| Hạng mục | Trạng thái | Bằng chứng cần |
|---|---|---|
| Bộ test HMI đã ban hành | NOT_TESTED / chưa có bảng tổng hợp ký nhận ở lượt R7 | Checklist operator PASS/FAIL từng ca, ảnh nếu cần |
| DPI màn 100%, 125%, 150% | NOT_TESTED | Ảnh / ghi nhận tỷ lệ, clipped widget, focus/tooltip |
| Thoát khi native C++ **thực sự đang bận** | NOT_TESTED | Trace chứng minh worker busy, thời điểm close, PID dọn xong |
| Lỗi native C++ thực (thay vì kill process) | NOT_TESTED | Controlled fault-injection subprocess, xác nhận parent sống |
| GPU/VRAM & tổng tài nguyên Qt + host | PARTIAL_EVIDENCE | Số liệu có phương pháp/công cụ, driver và môi trường |
| Độ trễ input→present màn hình / FPS thực tế | NOT_TESTED | Phân biệt Qt frame-copy, completed-render và physical presentation |
| HMI reopen/close nhiều lần | PARTIAL_EVIDENCE | Thao tác vận hành thật / process count; benchmark resident 20 cycles không thay thế HMI |

**Quyết định hiện hành:** `R6_AUTOMATED_PASS / R6_OVERALL_PENDING`. **Không miễn kiểm thử mặc định**. GĐ1 Final Freeze **chỉ sau R7, R8 và mốc 08.06.6** với mọi ngoại lệ được quyết định rõ.

## Sự cố của harness R6 cần giữ nguyên lịch sử

- `INC-GD1-R6-RUNNER-001`: tham số `$args` trùng biến tự động PowerShell → mọi subprocess không khởi chạy. Bản sửa đổi tên tham số, lưu thất bại gốc.
- `INC-GD1-R6-RUNNER-002`: exit code rỗng khiến tool in PASS bị ghi FAIL; CTest thiếu `-C Release`. Bản sửa lấy code trực tiếp từ process và gọi CTest Release. Sau đó 14/14 PASS.

Chi tiết: [Incident register](../history/GD1/INCIDENT_REGISTER.md) · [master log](../history/DEVELOPMENT_MASTER_LOG.md).
