# R7-D — Báo cáo tinh gọn và kiểm tra thành phần dư thừa

**Baseline:** `08ef856a04d61f20db1e26b2ceeb399065db902f`. **Phạm vi:** `docs/`, không sửa runtime/tests/RAW/SQLite.

## Quyết định được thực hiện

- Trước tinh gọn: **129 tệp** trong `docs/`, gồm **126 Markdown**.
- Loại khỏi working tree: **74 tệp** (68 hồ sơ archive và 6 tệp kiểm kê trung gian R7-A/B).
- Giữ lại **12 hồ sơ lịch sử quan trọng** và các tài liệu chuẩn, nhật ký, ADR, bằng chứng nghiệm thu.
- Bổ sung **2 trang chỉ mục ngắn**; kết quả dự kiến: **57 tệp Markdown**, giảm 69 Markdown so với hiện trạng.
- Cập nhật liên kết Markdown của các tệp giữ lại tới hồ sơ Git cố định, không tạo một lớp archive lồng thêm.

## Nguyên tắc không xóa nhầm

1. Mọi tệp bị gỡ đều phải tồn tại nguyên byte trong commit Git trước tinh gọn.
2. Tài liệu cũ được gỡ vì **không còn là nguồn hướng dẫn hiện hành**, không được tự gán "trùng nội dung 100%".
3. Bảng CSV chi tiết tệp đã xóa, SHA-256 và đường dẫn phục hồi nằm trong thư mục `evidence` ngoài repository.
4. Các trang tương thích `docs/INDEX.md`, `docs/modules/VIEWER3D.md` v.v. được giữ vì test R7 cũ còn gọi; không xóa trước R8.
5. **Không xóa runtime, compatibility facade hoặc tests** ở R7-D. Những thành phần này phải có phân tích caller/contract tại R8 trước khi gỡ.
6. R6 **14/14 cổng tự động PASS**, R6 tổng thể **PENDING**; tinh gọn tài liệu không thay đổi trạng thái nghiệm thu.

## Kiểm chứng

Kiểm tra đủ 74 tệp, Git hash, liên kết nội bộ, phạm vi Git diff, các kiểm thử R7 và full regression Windows trước khi commit.
[Tra cứu các hồ sơ đã gỡ](../HO_SO_CU_VA_TRUY_VET.md).
