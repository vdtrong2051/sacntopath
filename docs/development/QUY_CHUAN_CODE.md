# Quy chuẩn mã nguồn và chú thích

1. **Một trách nhiệm rõ ràng:** tách Qt shell, feature controller, service, provider, storage và native host; không tạo file chỉ để giảm số dòng.
2. **Comment/docstring tiếng Việt:** mô tả tiền/hậu điều kiện, đơn vị, nguồn, thread/process ownership và bất biến khó thấy; không giải thích lại những dòng mã hiển nhiên.
3. **Giữ nguyên định danh lập trình:** Tên class/hàm/file/API giữ như source đang chạy, tiếng Việt ở tài liệu và phần diễn giải.
4. **Quản lý lỗi:** phân biệt invalid input, timeout, cancelled, host loss; không để truy cập IO/native chặn Qt event loop.
5. **An toàn dữ liệu:** dữ liệu RAW chỉ đọc nếu không có lệnh ghi; không tự migrate SQLite; xử lý đường dẫn có giới hạn và từ chối symlink bất thường ở nơi cần.
6. **Regression:** không thay assertion cũ chỉ để làm xanh kết quả. Nếu hợp đồng thật đổi, ghi ADR/căn cứ và lập kiểm thử thay thế trước khi dỡ test cũ ở R8.

R7-B không tự động chuyển toàn bộ comment tiếng Anh sang tiếng Việt hoặc thay runtime. R7-C sẽ kiểm kê, chỉnh những chú thích cần thiết theo từng mô-đun có so sánh AST/hành vi.
