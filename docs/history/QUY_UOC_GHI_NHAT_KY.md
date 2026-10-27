# Quy tắc ghi nhật ký phát triển và sự cố

## 1. Phân loại bằng chứng

| Nhãn | Ý nghĩa | Ví dụ |
|---|---|---|
| `XAC_MINH_GIT` | Tồn tại commit hoặc nội dung trong chính repository đã đối chiếu | Commit R5.3 `ff45ccf` |
| `NGUOI_VAN_HANH_BAO_CAO` | Người vận hành dán kết quả và đường dẫn trên Windows; chưa mở tệp evidence gốc trong phiên biên tập | R6 `618 passed, 3 skipped` |
| `MOT_PHAN` | Mới chứng minh một số điều kiện | Benchmark Render Host chưa chứng minh FPS hiển thị |
| `CHUA_KIEM_THU` | Chưa có lần đo đúng phép thử | Native C++ thật sự bận lúc đóng |
| `CHUA_DU_LICH_SU` | Không đủ nguồn để thống kê các lần thử trước | Tổng số lần sửa 07.11 |
| `MIEN_CO_DIEU_KIEN` | Ngoại lệ có người duyệt và phạm vi riêng; không được xem là PASS | Chỉ áp dụng khi có biên bản thực |

Các mã machine-readable lịch sử (`OPERATOR_REPORTED`, `PARTIAL_EVIDENCE`, `NOT_TESTED`, `HISTORY_INCOMPLETE`, `WAIVED`) được giữ lại trong hồ sơ cũ và bằng chứng tự động. Khi ghi nội dung mới, ưu tiên diễn giải tiếng Việt, kèm mã gốc nếu cần đối chiếu.

## 2. Một bản ghi mốc phát triển

- **Mã mốc:** mã phiên hoặc số hiệu đợt, không tự đặt lại mốc cũ.
- **Tình trạng trước → sau:** chức năng, phạm vi, lỗi chưa giải quyết.
- **Căn cứ:** commit chính xác nếu có; đường dẫn tài liệu; ID nhật ký/bằng chứng nếu người vận hành đã cung cấp.
- **Kết quả:** PASS/FAIL/SKIP/CHƯA KIỂM THỬ theo *đúng loại phép thử*.
- **Giới hạn:** điều gì không thể kết luận từ bằng chứng.
- **Nối tiếp:** quyết định/đợt cần thực hiện, không suy diễn đã hoàn thành.

## 3. Một bản ghi sự cố

`ID → Hiện tượng → Bằng chứng có thật → Nguyên nhân (đã xác nhận/chưa xác nhận) → Sửa chữa → Kiểm thử sau sửa → Rủi ro còn lại → Phòng ngừa`.

Phân biệt: **FAIL thực của phần mềm**, **FAIL do bộ kiểm thử**, **bài kiểm thử bị SKIP**, và **điều kiện chưa kiểm thử**. Hai sự cố khác nhau không được gộp vì cùng xảy ra trong một phiên.

Khi phát hiện mô tả cũ sai, ghi một dòng **ĐÍNH CHÍNH** nêu nội dung cũ, lý do, nguồn và ngày; không âm thầm sửa lịch sử để trông như luôn PASS.

## 4. Chú thích và tài liệu nguồn

- Giữ nguyên tên lớp, hàm, tham số, giao thức, mã lỗi và giá trị trả về trong mã; chú thích tiếng Việt giải thích *vì sao* và bất biến kỹ thuật.
- Không xóa cảnh báo liên quan đến byte RAW, fsync, SQLite transaction, lifetime, IPC, thread và giới hạn đo lường.
- Chỉnh docstring có thể đổi `__doc__` khi introspection; không được xem là thay đổi byte-for-byte runtime. R7-C yêu cầu **AST sau khi bỏ docstring giống bản gốc**, đồng thời chạy hồi quy thực trên Windows.
- Mọi thay đổi logic, schema, UI/UX hoặc hợp đồng kiểm thử thuộc phiên chức năng phù hợp, không được lén ghép vào chỉnh chú thích.

## 5. Nguồn tham chiếu

[Kiến trúc hiện hành](../architecture/TONG_QUAN_KIEN_TRUC.md) · [Quy chuẩn code](../development/QUY_CHUAN_CODE.md) · [Nghiệm thu GĐ1](../acceptance/GD1.md) · [Kho tài liệu lịch sử](../archive/README.md).
