# GĐ1 — Danh mục sự cố và bài học được bảo toàn (R7)

**Phân lớp chứng cứ:** nhật ký Windows do operator cung cấp = `OPERATOR_REPORTED`; commit/docs trên GitHub = `VERIFIED`. Root cause chỉ ghi chắc chắn nếu log/hành vi trực tiếp hỗ trợ. Số attempt tổng thể cho các giai đoạn cũ có thể `HISTORY_INCOMPLETE`.

| ID | Triệu chứng và nguyên nhân | Cách giải quyết / kiểm chứng | Phòng ngừa |
|---|---|---|---|
| INC-GD1-07-ARCH | 07.11/07.12 refactor: Windows `python -c` quoting, QObject parent/relative import, harness kiểm thử lặp lỗi theo risk register; chi tiết attempt `HISTORY_INCOMPLETE` | [07.12 risk register](../../archive/GD1/07/07_12_CONSOLIDATION_RISK_REGISTER.md) | Tránh `python -c` phức tạp, test import Qt ở cây thật, kiểm tra lifecycle |
| INC-GD1-08-VTK | Qt/VTK in-process crash, lỗi lifecycle | [08.02 crash repair](../../archive/GD1/08/08_02_CRASH_REPAIR.md); R4 chọn B isolated có điều kiện | Native fault isolation + GUI process survival |
| INC-GD1-R5-001 | `test_r53_live_click_emits_uv_only_in_select_mode`: `_ready_tools` cần frame đã ACK, fixture để revision=-1; cùng lúc UI chỉ chữ, thao tác khó | Rework fixture có frame hợp lệ, giữ no-frame guard, toolbar SVG; focused 16 PASS theo operator | Test event lifecycle thực và HMI, không tháo chốt an toàn |
| INC-GD1-R5-002 | Full R5.3 617 PASS, 1 FAIL: R5.2 test kiểm chuỗi `LiveViewer3DController(` trong bootstrap khi R5.3 dùng subclass | Compatibility repair trong factory; không sửa test cũ; R6 sau đó full 618 PASS | R8 thay brittle string assertion bằng kiểm tra hành vi/contract |
| INC-GD1-R5-003 | R5.2 shell 511 dòng vượt giới hạn `<500`, full regression 2 FAIL | Tách bootstrap, sửa deprecated `QImage.mirrored`, focused/legacy sau sửa | Giữ composition root gọn; tránh chất thêm logic vào shell |
| INC-GD1-R6-RUNNER-001 | R6 đầu tiên: `Start-Process -ArgumentList` nhận NULL vì tham số hàm tên `$args` đụng biến tự động PowerShell | Vá runner, lần kế tiếp subprocess đã chạy; khẳng định nguyên nhân từ script | Không dùng automatic variables làm tham số PS; unit test wrapper thật trên PS 5.1 |
| INC-GD1-R6-RUNNER-002 | R6 lần 2: chương trình in PASS nhưng status FAIL/`exit_code` trống; CTest báo `Missing -C <config>` | Dùng `.ExitCode` thực, `ctest -C Release`; lượt kế 14/14 PASS | Kiểm thử exit-code zero/nonzero, loại generator multi-config |

## Rủi ro không được biến thành incident đã xảy ra

- `AR-03` / close while genuine native busy: **NOT_TESTED**, không phải crash đã tái hiện. Controlled process `SIGTERM` hoặc `kill()` **không bằng** native C++ segfault.
- GPU/VRAM & physical present latency: **NOT_MEASURED**; benchmark completed-render và Qt frame copy không thay số đo hiển thị.
- Quyền tạo symlink trên Windows: 3 skipped; không ghi thành PASS cho đường tấn công symlink.

## Quy tắc bản ghi sự cố mới

Bản ghi sau này phải gồm `incident_id`, `symptom`, `first_seen`, `root_cause_status`, `attempts` (kèm report path), `resolution`, `linked_regression`, `prevention`, `unverified_scope`. Nếu không có bằng chứng, dùng `HISTORY_INCOMPLETE`/`UNCONFIRMED`, không tự sinh số attempt.
