# Mô-đun thu nhận ảnh màu và độ sâu RGB-D

## Đầu vào và đầu ra

Nguồn đã thử trong GĐ0 là **Orbbec Gemini 2** qua OrbbecSDK v2.10.6. Phần C++20 thu nhận một cặp frame gồm **Color 1920×1080 MJPEG** và **Depth 1280×800 Y16** với bộ đệm sao chép sở hữu bởi ứng dụng. Python tiếp nhận qua pybind11; chỉ thực hiện truy cập thiết bị khi có lệnh.

## Thông tin phải giữ nguyên

| Thuộc tính | Quy tắc |
|---|---|
| Màu/độ sâu | Hai lưới khác kích thước; không tự resize hoặc align |
| Intrinsics/distortion | Đúng với từng stream và mô hình SDK |
| Depth scale | Đơn vị mét trên mỗi đơn vị Y16 (`m/unit`) |
| Depth-to-color | Matrix SDK; translation gốc là **mm**, không ngầm đổi thành mét |
| Timestamps | Do SDK báo; chênh lệch chỉ có ý nghĩa chẩn đoán nếu chưa kiểm clock domain |
| Trạng thái nguồn | `measured=true` là có dữ liệu cảm biến thật, không phải xác nhận kích thước metric |
| Pose camera | Không suy ra camera pose hoặc world pose từ việc đọc frame |

## Hợp đồng thực hiện

`src/scantopath/acquisition/` và nguồn C++ trong `cpp/` sở hữu tương tác native. Python import không tự mở camera; `--self-test` kiểm tra import/buffer không dùng phần cứng; `--once` chỉ dùng khi đã cắm thiết bị và sẵn sàng. Đã có bằng chứng kiểm tra thực trên Windows ở GĐ0, nhưng không suy ra phép đo chuẩn hoặc actuator.

## Giới hạn và lịch sử

Các ghi chép trước có giả định camera cầm tay hoặc cơ cấu quay ở các thời điểm khác nhau. R7-B không chốt cấu hình máy quét mới nếu không có quyết định/bằng chứng hiện hành; xem [sổ cần xác minh](../standardization/R7B_CAN_XAC_MINH.md). Chi tiết các lần thử nằm trong [hồ sơ phần cứng](../archive/README.md).
