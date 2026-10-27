# Quy trình Git và áp dụng bản vá

## Quy trình đã thống nhất

```text
Kiểm tra HEAD/branch sạch
    → ZIP _setup ngoài repository
    → apply.ps1 (bảo vệ baseline + backup)
    → verify.ps1 (kiểm tra nội dung và hồi quy)
    → HMI Windows nếu tác động giao diện
    → người vận hành duyệt
    → publish.ps1 / commit và push đúng nhánh
```

Không tự merge vào `main`. Không dùng `git reset --hard` để chữa lỗi patch; nếu cần hoàn tác, dùng cơ chế backup và kiểm tra đúng phạm vi thay đổi.

Với tài liệu đã chuyển nơi, Git có thể nhận diện rename tự động qua độ tương đồng; nếu cần ghi lịch sử rõ, dùng `git mv` khi thực thi. Không thay lịch sử commit hoặc xóa bản ghi FAIL đã được lưu. R7-B có [bản đồ đường dẫn](../standardization/R7B_BAN_DO_DI_CHUYEN.md) để tra cứu.
