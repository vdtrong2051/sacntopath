# Tra cứu hồ sơ cũ đã loại khỏi cây làm việc

**Mục đích:** giữ `docs/` gọn nhưng không xóa dấu vết nghiên cứu, kiểm thử hoặc quyết định.

**Mốc Git trước tinh gọn:** `08ef856a04d61f20db1e26b2ceeb399065db902f` (`feat/gd1-desktop-ui`, R7-C).

- [Duyệt toàn bộ hồ sơ cũ trên GitHub](https://github.com/vdtrong2051/sacntopath/tree/08ef856a04d61f20db1e26b2ceeb399065db902f/docs/archive)
- [Danh mục R7-A trước khi chuyển](https://github.com/vdtrong2051/sacntopath/blob/08ef856a04d61f20db1e26b2ceeb399065db902f/docs/standardization/R7A_DANH_MUC_91_TAI_LIEU.csv)
- [Bản đồ R7-B của 80 tài liệu](https://github.com/vdtrong2051/sacntopath/blob/08ef856a04d61f20db1e26b2ceeb399065db902f/docs/standardization/R7B_BAN_DO_DI_CHUYEN.csv)
- [Những hồ sơ quan trọng giữ tại chỗ](README.md)

## Chính sách tra cứu

1. Tài liệu chuẩn để phát triển hiện tại vẫn nằm tại `architecture/`, `modules/`, `development/`, `acceptance/`, `decisions/` và `history/`.
2. Hồ sơ theo từng phiên, bản tổng hợp R7-A/R7-B và trang tài liệu bị thay thế chỉ được gỡ khỏi **working tree**, không viết lại Git history.
3. Một số liên kết trong tài liệu còn lại được thay bằng đường dẫn tới commit Git cố định; có thể xem và khôi phục nguyên văn, không phụ thuộc nhánh `main`.
4. Nhật ký và quyết định có giá trị chứng cứ quan trọng được giữ cục bộ. Xóa không đồng nghĩa phủ nhận các kết luận lịch sử.

## Phục hồi một hồ sơ khi cần

Chạy tại gốc repository và thay `DUONG_DAN_CU` bằng đường dẫn hiện trong commit lịch sử:

```powershell
git show "08ef856a04d61f20db1e26b2ceeb399065db902f:DUONG_DAN_CU"
```

Muốn lưu lại một tệp, chuyển đầu ra tới đường dẫn mong muốn và kiểm tra định dạng UTF-8.

**Giới hạn:** Git không phải bản sao lưu độc lập. Không được rewrite/force-push lịch sử đã ghim trước khi kiểm tra chính sách lưu trữ.
