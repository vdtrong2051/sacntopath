# R8.5 — Kiểm toán, tinh gọn có kiểm soát và khóa hệ thống kiểm thử

**Baseline:** `feat/gd1-desktop-ui@4a2df5938d8e82a3c7790acb2a251003d9224511` (sau R8.4).

## 1. Kết quả đối chiếu GitHub trước khi triển khai

- Repository có **80 file `test_*.py`** thuộc sáu nhóm `unit`, `integration`, `contracts`, `ui`, `native`, `performance` và **27 script** Python/PowerShell.
- Không có cặp file test/script nào có cùng Git blob SHA ở baseline. **Không suy ra** các test có cùng mục đích là bản sao tương đương về hành vi.
- `scripts/verify_gd1_r3_5.ps1` vẫn được R8.2 kiểm tra đường dẫn; các script R4/R5 lưu phép đối chứng A/B, native và benchmark. Các nguồn gọi nằm trong `_setup` hoặc lệnh vận hành thủ công không có trong GitHub nên không thể kết luận chúng vô dụng.
- Vì thiếu bằng chứng chứng minh file nào không còn giá trị, **R8.5 không tự xóa bất kỳ script/test lịch sử nào**. Danh sách ứng viên được xuất để rà soát trước khi tạo việc xóa riêng.

## 2. Thành phần thực thi R8.5

- `scripts/r8_5_audit.py`: so sánh mọi tên hàm test tại baseline với working tree, kiểm tra thiếu test/script, kiểm tra nhóm test, import chéo, hash file, tham chiếu tĩnh tới script, dấu hiệu trùng AST và kiểm tra trạng thái R6 `PENDING`.
- `tests/contracts/quality/test_gd1_r8_5_audit.py`: kiểm thử chức năng kiểm toán và nguyên tắc không xóa chỉ dựa vào heuristic.
- `scripts/r8_4_verify.py`: chèn `R8_5_AUDIT` vào các chế độ `Quick`, `Full`, `Acceptance` và thêm test R8.5 vào bộ Quick.
- `docs/development/QUY_TRINH_KIEM_THU.md`: bổ sung cách chạy và điều kiện nghiệm thu.

Mỗi lần chạy `scripts/verify.ps1` xuất `R85_AUDIT.json`, `R85_TESTS.csv`, `R85_SCRIPTS.csv`, `R85_CANDIDATES.csv`, `R85_BAO_CAO.md` trong thư mục bằng chứng **ngoài repository**.

## 3. Cổng nghiệm thu và giới hạn

| Nội dung | Điều kiện |
|---|---|
| Mốc đầu vào | Commit R8.4 phải là tổ tiên của HEAD |
| Tên test | Tất cả tên hàm test cũ từ baseline vẫn hiện diện |
| Cấu trúc | Sáu nhóm và 80 test / 27 script baseline không bị xóa |
| Công cụ R8.5 | Quét tĩnh PASS và có báo cáo ứng viên |
| Regression | `scripts/verify.ps1 -Profile Full` PASS, gồm pytest, JUnit policy và CTest Release |
| Truy vết | Có commit và evidence lưu riêng; không tạo bằng chứng giả |
| Gỡ mã dư | **0 xóa tự động**; chỉ xóa khi chứng minh được call graph, hợp đồng thay thế và hậu kiểm |
| GĐ1 tổng thể | **PENDING_08_06_6** cho đến khi các phần nghiệm thu HMI/native còn mở được xử lý |

Không đồng nhất `Full automated=PASS` với việc đã kiểm HMI thật. Các ca DPI 100/125/150, native busy close, native fault, GPU/VRAM và độ trễ input-to-physical-present vẫn phải được nghiệm thu hoặc phê duyệt ngoại lệ tại 08.06.6.

## 4. Lệnh chuẩn

```powershell
.\scripts\verify.ps1 -Profile Quick
.\scripts\verify.ps1 -Profile Full
.\scripts\verify.ps1 -Profile Acceptance
```

R8.5 **khóa hạ tầng kiểm thử**, không tự khóa GĐ1 hay thay đổi quyết định R6. Nếu `Full` không đạt thì R8.5 chưa được nghiệm thu.
