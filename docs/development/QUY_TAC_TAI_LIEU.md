# Quy tắc tổ chức và cập nhật tài liệu

## Một nguồn chuẩn cho mỗi chủ đề

- `docs/README.md` là điểm vào; `architecture/` mô tả hiện trạng, `modules/` giải thích chức năng, `development/` hướng dẫn thao tác.
- `decisions/` lưu quyết định theo thời điểm, `acceptance/` lưu bằng chứng và ngoại lệ, `history/` lưu diễn tiến, `archive/` lưu hồ sơ đã thay thế.
- Tài liệu hiện hành viết **tiếng Việt**; chỉ giữ tên API/class/file và thuật ngữ không có tương đương rõ ràng. Thuật ngữ mới phải giải thích ở lần dùng đầu.
- Tài liệu trong archive giữ nguyên nội dung phát biểu lịch sử; chỉ cập nhật đường dẫn tương đối nếu cần để liên kết còn hoạt động. Việc thay đường dẫn phải được ghi vào bản đồ di chuyển.
- Kết luận **CHƯA XÁC MINH** hoặc **NOT_TESTED** phải giữ nguyên; không gộp PASS của fixture/native renderer thành chứng nhận đo lường/hiển thị trên máy thật.

## Khi bổ sung tính năng

Cập nhật trang mô-đun và luồng dữ liệu; nếu thay đổi kiến trúc, cập nhật sơ đồ và ADR. Nhật ký nên liên kết tới commit/test/receipt, không sao chép terminal log dài. Không làm cho tài liệu cũ "biến mất": mọi tài liệu di chuyển được ghi trong [bản đồ R7-B](../standardization/R7B_BAN_DO_DI_CHUYEN.md).

## Bảo toàn lịch sử

Biên bản R6 tự động PASS và những lần FAIL của harness R6 đều phải tồn tại cùng lúc trong sổ sự cố. Tên tài liệu cũ có thể tồn tại dưới dạng **trang chuyển hướng tương thích**, không phải hai nguồn chuẩn có giá trị ngang nhau.
